"""Pure, read-only catalog fact projection and deterministic answer plans.

The caller supplies its current *public* catalog and publication-filtered
``approvedKnowledge``. This module neither publishes knowledge nor reads files,
configuration, a database, or a provider. Prices come only from the supplied
market-specific live fields. It deliberately has no dependency on support_ai.

``resolve_items(evidence, question)`` may reuse the caller's existing resolver.
Alternatively ``requests`` is a list of ``{ref, fields, compatibility?, slots?,
requestId?, targetRef?}``. Slots are customer observations, never catalog facts. Pending
slots round-trip as ``{ref: {requestId: {fields, compatibility, slots, missing}}}``.
Persist ``CatalogPlan.to_dict()`` and validate against current evidence before
displaying a restored plan. This is an integrity check, not authentication.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from typing import Callable


SCHEMA_VERSION = 1
MAX_ITEMS = 8
MAX_TEXT = 12000
MAX_VALUE = 16000
TOPICS = frozenset({"products", "pricing", "compatibility", "customer_service"})
FIELD_STATUSES = frozenset({"answered", "unknown", "conflicted", "scope_disabled", "not_applicable"})
COMPATIBILITY_STATUSES = frozenset({
    "listed_requirements", "known_mismatch", "conditional_match",
    "requirements_match_not_verified", "insufficient_data", "conflicting_evidence",
})


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    topic: str = "products"
    paths: tuple[str, ...] = ()
    query: str = ""
    labels: tuple[str, ...] = ()


def _spec(key: str, label: str, *paths: str, query: str = "",
          labels: tuple[str, ...] = (), topic: str = "products") -> FieldSpec:
    return FieldSpec(key, label, topic, paths or (key,), query, labels)


_SPECS = [
    _spec("name", "Name", query=r"\b(?:name|called)\b"),
    _spec("category", "Category", query=r"\bcategory\b"),
    _spec("brand", "Brand", query=r"\bbrand\b", labels=("brand",)),
    _spec("description", "Description", query=r"\b(?:describe|description|tell me about)\b"),
    _spec("shortDescription", "Overview", query=r"\boverview\b"),
    _spec("features", "Features", query=r"\bfeatures?\b"),
    _spec("price.current", "Price", "price", topic="pricing",
          query=r"\b(?:prices?|costs?|how much)\b|价格|多少钱"),
    _spec("price.msrp", "MSRP", "msrp", topic="pricing", query=r"\b(?:msrp|list price|retail price)\b"),
    _spec("colourOptions", "Colour options", "colourOptions", "colorOptions",
          query=r"\bcolou?rs?\b|颜色", labels=("colour options", "color options", "colours", "colors", "colour", "color")),
    _spec("colour.availableOptions", "Available colour choices", "colourOptions", "colorOptions",
          query=r"\bavailable\s+colou?r(?:s|\s+(?:options|choices))?\b|"
                r"\bcolou?r(?:s|\s+options|\s+choices)?\s+(?:are\s+)?available\b|"
                r"\b(?:what|which)\s+colou?r\s+(?:options|choices)\b",
          labels=("available colour options", "available color options", "available colours", "available colors",
                  "colour options", "color options")),
    _spec("colour.parts", "Colours by component", "colourParts", "colorParts",
          query=r"\b(?:frame|handles?|grips?|padding|upholstery|pins?|bolts?|rollers?|pads?)\s+colou?rs?\b|"
                r"\bcolou?rs?\s+(?:of|for)\s+(?:the\s+)?(?:frame|handles?|grips?|padding|upholstery|pins?|bolts?|rollers?|pads?)\b"),
    _spec("finish", "Finish", query=r"\b(?:finish|coating)\b", labels=("finish", "coating")),
    _spec("material", "Material", query=r"\b(?:materials?|made of|made from)\b|材质|材料",
          labels=("material", "materials")),
    _spec("material.parts", "Materials by component", "materialParts",
          query=r"\b(?:frame|handles?|grips?|padding|upholstery)\s+(?:materials?|made of|made from)\b|"
                r"\bmaterials?\s+(?:of|for)\s+(?:the\s+)?(?:frame|handles?|grips?|padding|upholstery)\b|"
                r"\b(?:are|is)\s+(?:the\s+)?(?:frame|handles?|grips?|padding|upholstery)\s+made\b"),
    _spec("dimensions", "Dimensions", query=r"\b(?:dimensions?|size)\b|尺寸"),
    _spec("dimensions.length", "Length", "length", "dimensions.length", query=r"\blength\b|长度", labels=("length",)),
    _spec("dimensions.width", "Width", "width", "dimensions.width", query=r"\bwidth\b|宽度", labels=("width",)),
    _spec("dimensions.height", "Height", "height", "dimensions.height", query=r"\b(?:height|tall)\b|高度", labels=("height",)),
    _spec("dimensions.depth", "Depth", "depth", "dimensions.depth", query=r"\bdepth\b", labels=("depth",)),
    _spec("weight.own", "Own weight", "weight", "ownWeight",
          query=r"\b(?:weights?|weigh|weighs|heavy|mass)\b|重量|多重",
          labels=("own weight", "net weight", "product weight", "item weight", "weight")),
    _spec("capacity.safeLoad", "Published load capacity", "capacity.safeLoad", "safeLoad",
          query=r"\b(?:capacity|load rating|safe load|maximum load|weight limit|weight capacity|"
                r"(?:maximum|max|rated) user weight|supported weight|"
                r"how much (?:weight )?can .{0,45}?(?:hold|support|carry|handle|bear)|"
                r"how much weight .{0,30}?(?:hold|support|carry|handle|bear)|"
                r"what weight .{0,30}?(?:hold|support|carry|handle|bear)|"
                r"(?:hold|support|carry|handle|bear) (?:how much|what) weight|"
                r"loads?(?!\s+(?:pins?|increments?|steps?|bearing)\b))\b|承重",
          labels=("safe load", "load capacity", "weight capacity", "maximum load", "max load", "load rating",
                  "weight limit", "maximum user weight", "max user weight", "rated user weight", "supported weight")),
    _spec("resistance.stacks", "Resistance stacks", "resistance.stacks", "weightStacks",
          query=r"\b(?:stacks?|resistance)\b", labels=("weight stacks", "weight stack", "resistance stacks", "resistance stack")),
    _spec("resistance.increments", "Resistance increments", "resistance.increments", "weightIncrements",
          query=r"\b(?:increments?|weight steps?)\b", labels=("weight increments", "stack increments", "increments", "increment")),
    _spec("included", "Included", "included", "includes", query=r"\b(?:included|includes|come with|comes with|what comes|package contents|what(?: is|'s) in (?:the )?(?:box|package))\b|包含|配件清单",
          labels=("included", "includes", "package contents")),
    _spec("components", "Components", query=r"\bcomponents?\b", labels=("components",)),
    _spec("sellingUnit", "Selling unit", "sellingUnit", "saleUnit",
          query=r"\b(?:selling unit|sale unit|sold individually|sold as|each|pair|pairs|single|set)\b|一对|单个",
          labels=("selling unit", "sale unit", "sold as")),
    _spec("packageQuantity", "Package quantity", query=r"\b(?:package quantity|how many|quantity|pieces)\b",
          labels=("package quantity", "quantity per package")),
    _spec("modelSku", "Model / SKU", "modelSku", "sku", query=r"\b(?:sku|model number|model code)\b|型号", labels=("model / sku", "sku", "model number")),
    _spec("stockStatus", "Published stock status", query=r"\b(?:stock|availability|available now)\b|库存|有货", labels=("stock status", "availability")),
    _spec("warranty", "Published product warranty", query=r"\bwarranty\b|保修", labels=("warranty",)),
    _spec("notes", "Published notes", query=r"\b(?:notes|published use|intended use)\b", labels=("notes", "intended use")),
]
_COMPONENTS = ("frame", "handle", "grip", "padding", "upholstery", "pin", "bolt", "roller", "pad")
for _component in _COMPONENTS:
    _SPECS.append(_spec(f"material.{_component}", f"{_component.capitalize()} material",
                        f"materialParts.{_component}"))
    _SPECS.append(_spec(f"colour.{_component}", f"{_component.capitalize()} colour",
                        f"colourParts.{_component}", f"colorParts.{_component}"))
for _key, _label, _query, _labels in [
    ("uprightSize", "Upright size", r"\b(?:uprights?|rack\s*posts?|post size)\b|立柱", ("upright size", "rack post size", "post size", "uprights")),
    ("holeDiameter", "Hole diameter", r"\b(?:holes?|hole diameter)\b|孔径", ("hole diameter", "mounting hole diameter")),
    ("holeSpacing", "Hole spacing", r"\b(?:hole spacing|hole pitch)\b", ("hole spacing", "hole pitch")),
    ("pinDiameter", "Pin diameter", r"\bpin diameter\b", ("pin diameter",)),
    ("pinLength", "Pin length", r"\bpin length\b", ("pin length",)),
    ("pinDimensions", "Pin dimensions", r"\bpin (?:size|dimensions?)\b", ("pin size", "pin dimensions")),
    ("models", "Documented models", r"\b(?:documented models|compatible models)\b", ("compatible models", "documented models")),
    ("limitations", "Compatibility limitations", r"\b(?:limitations|restrictions)\b", ("limitations", "compatibility limitations")),
    ("requiredDepth", "Required depth", r"\b(?:required depth|minimum depth|internal depth)\b", ("required depth", "minimum depth", "required internal depth")),
]:
    _SPECS.append(_spec(f"compat.{_key}", _label, f"compatibility.{_key}", f"compat.{_key}",
                        topic="compatibility", query=_query, labels=_labels))

FIELD_REGISTRY = {entry.key: entry for entry in _SPECS}
# All other current public fields are transport, presentation, or availability
# metadata, not independent specification facts. No alternate catalog is stored.
NON_FACT_METADATA = {
    "id": "canonical identity", "type": "canonical identity", "ref": "canonical identity",
    "slug": "navigation", "url": "navigation", "canonicalUrl": "navigation",
    "currency": "part of market-specific money", "market": "market eligibility",
    "prices": "private/other-market prices; never projected", "msrps": "private/other-market prices",
    "missingPriceMarkets": "private market availability", "provenance": "private provenance",
    "image": "presentation, never visual fact inference", "photos": "presentation, never visual fact inference",
    "featured": "presentation ordering", "publicationStatus": "publication eligibility",
    "approvedKnowledge": "upstream-approved evidence container", "catalogVersion": "source version",
    "revision": "source version", "sourceHash": "source version", "aliases": "resolution metadata",
}
ALIASES = {path: spec.key for spec in _SPECS for path in spec.paths}
ALIASES.update({key: key for key in FIELD_REGISTRY})
ALIASES.update({key.split(".", 1)[1]: key for key in FIELD_REGISTRY if key.startswith("compat.")})
ALIASES.update({"color": "colourOptions", "colour": "colourOptions", "weight": "weight.own",
                "colourOptions": "colourOptions", "colorOptions": "colourOptions",
                "price": "price.current", "msrp": "price.msrp", "capacity": "capacity.safeLoad",
                "capacity.safe_load": "capacity.safeLoad", "compatibility.required_depth": "compat.requiredDepth",
                "compatibility.hole_diameter": "compat.holeDiameter",
                "compatibility.upright_labels": "compat.uprightSize", "resistance.stack_max": "resistance.stacks"})
CONSTRAINTS = ("uprightSize", "holeDiameter", "holeSpacing", "requiredDepth")
SLOT_NAMES = frozenset((*CONSTRAINTS, "model", "variant"))
FIT_QUERY = re.compile(r"\b(?:fit|fits|fitting|compatible|compatibility|work with|works with|mount on)\b|适配|兼容", re.I)
_REFERENCE = re.compile(r"(?:product|accessory):[1-9]\d{0,15}\Z")
_COLOURS = frozenset({
    "black", "white", "red", "blue", "green", "yellow", "orange", "grey", "gray", "silver",
    "gold", "teal", "purple", "pink", "brown", "beige", "ivory", "navy", "charcoal", "graphite",
    "bronze", "copper", "burgundy", "maroon",
})
_COLOUR_WORD = r"(?:" + "|".join(sorted(_COLOURS, key=len, reverse=True)) + ")"
_FINISH_COLOUR = re.compile(
    rf"\b({_COLOUR_WORD}(?:\s*(?:/|and|or|,|&)\s*{_COLOUR_WORD})*)"
    r"\s+(?:finish|powder[- ]coat(?:ing|ed)?(?:\s+finish)?)\b", re.I,
)
_COLOUR_COMPONENT = r"(frame|handles?|grips?|padding|upholstery|pins?|bolts?|rollers?|pads?)"
_PART_COLOUR = re.compile(
    rf"\b({_COLOUR_WORD}(?:\s*(?:/|and|or|,|&)\s*{_COLOUR_WORD})*)"
    rf"\s+(?:(?:padded|rubber|foam|steel|plastic|leather|vinyl|metal)\s+)*{_COLOUR_COMPONENT}\b", re.I,
)


class _DescriptiveColour(str):
    """An explicitly described finish is not an exhaustive list of options."""


def _json_copy(value: object) -> object:
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _present(value: object) -> bool:
    if value is None or value == "" or value == [] or value == {}:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().lower() not in {"unknown", "not published", "tbd", "n/a", "not applicable"}
    return not isinstance(value, bool)


def _path(item: dict, path: str) -> object:
    current: object = item
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _safe_value(value: object) -> bool:
    try:
        return len(json.dumps(value, allow_nan=False)) <= MAX_VALUE
    except (TypeError, ValueError, OverflowError):
        return False


def _normal(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).casefold()).strip(" .")


def _money(value: object, currency: object) -> dict | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        return None
    if currency not in ("CAD", "USD"):
        return None
    try:
        amount = Decimal(str(value))
        cents = amount * 100
        if not amount.is_finite() or amount < 0 or cents != cents.to_integral_value() or amount > Decimal("1e12"):
            return None
        return {"amountMinor": int(cents), "currency": currency}
    except InvalidOperation:
        return None


def _source(item: dict, key: str, locator: str, value: object, doc: dict | None = None) -> dict:
    kind = "approved_knowledge" if doc is not None else "public_catalog"
    origin = doc if doc is not None else item
    source_hash = str(origin.get("sourceHash") or _hash(origin if doc is not None else {
        **{path: _path(item, path) for spec in _SPECS for path in spec.paths},
        "ref": item["ref"], "currency": item.get("currency"),
    }))
    source = {
        "ref": item["ref"], "field": key, "kind": kind, "locator": locator,
        "sourceId": str(origin.get("sourceId") or item["ref"]),
        "sourceHash": source_hash, "revision": str(origin.get("revision", origin.get("catalogVersion", ""))),
        "valueHash": _hash(value),
    }
    source["id"] = "catalog:" + _hash(source)
    return source


def _sentences(text: str) -> list[str]:
    return [part.strip(" •-\t") for part in re.split(r"[;\n]+|(?<=[.!?])\s+(?=[A-Z])", text) if part.strip()]


_NON_ASSERTION = re.compile(
    r"\b(?:not|no|never|without|neither|nor|cannot|can't|isn't|aren't|doesn't|don't|wasn't|weren't|"
    r"if|unless|assuming|suppose|hypothetical|hypothetically|could|would|might|may|should|"
    r"previously|formerly|historically|discontinued|obsolete|superseded|"
    r"example|example-only|imagine|pretend|ignore|claim|say|tell|assert|assume|instruct\w*)\b|"
    r"\b(?:old|older|previous|earlier|legacy|prior|former)\s+(?:model|version|variant|design|spec\w*)\b|"
    r"\bused to\b|\b(?:was|were)\s+(?:rated|made|listed|specified|available)\b|[?]",
    re.I,
)


def _own_subject(value: str, item: dict | None) -> bool:
    subject = re.sub(r"^(?:the|this)\s+", "", value.strip(), flags=re.I)
    subject = re.sub(r"(?:['’]s|:)\s*$", "", subject).strip()
    choices = {"it", "item", "product", "unit"}
    if item:
        choices.update(_normal(name) for name in _names(item))
        words = set(re.findall(r"\w+", str(item.get("name", "")).casefold()))
        choices.update(words & {"bench", "bar", "rack", "trainer", "attachment"})
    return _normal(subject) in choices


def _extract(text: str, item: dict | None = None) -> list[tuple[str, object]]:
    """Extract explicit labels, not plausible attributes or unrelated numbers."""
    result: list[tuple[str, object]] = []
    blocked_heading = False
    for sentence in _sentences(text):
        if sentence.endswith(":"):
            blocked_heading = bool(_NON_ASSERTION.search(sentence))
        if blocked_heading or _NON_ASSERTION.search(sentence):
            continue
        start = len(result)
        for spec in _SPECS:
            if spec.topic == "pricing":
                continue
            for label in sorted(spec.labels, key=len, reverse=True):
                separator = r"(?::|=|\bis\b|\bare\b)"
                if spec.key.startswith(("weight.", "capacity.", "dimensions.", "compat.", "resistance.")):
                    separator = rf"(?:{separator}|\s+(?=(?:approximately\s+|about\s+)?\d))"
                match = re.search(rf"(?<![\w]){re.escape(label)}\s*{separator}\s*(.+)", sentence, re.I)
                if not match:
                    continue
                before = sentence[:match.start()].lower()
                if spec.key == "weight.own":
                    prefix = re.sub(r"^(?:specifications?|specs?)\s*:\s*", "", before, flags=re.I).strip()
                    if prefix and not _own_subject(prefix, item):
                        continue
                if spec.key.startswith("dimensions.") and re.search(r"(?:required|minimum|internal|hole|upright)\s*$", before):
                    continue
                if spec.key == "material" and re.search(r"(?:frame|handles?|grips?|padding|upholstery)\s*$", before):
                    continue
                value = match.group(1).strip().rstrip(".")
                # Stop at another explicit labeled specification on this line.
                all_labels = [re.escape(label) for entry in _SPECS for label in entry.labels]
                value = re.split(r"\s+(?:" + "|".join(all_labels) + r")\s*:", value, maxsplit=1, flags=re.I)[0].strip(" ,")
                if value:
                    result.append((spec.key, value))
                break
        weigh = re.search(r"\bweighs?\s+((?:approximately|about|approx\.?|~)?\s*\d+(?:\.\d+)?\s*(?:kg|kgs|kilograms?|lb|lbs|pounds?))\b", sentence, re.I)
        if weigh and _own_subject(sentence[:weigh.start()], item):
            result.append(("weight.own", weigh.group(1).strip()))
        part = re.search(r"\b(frame|handles?|grips?|padding|upholstery)\s+(?:material\s*:\s*|(?:is|are)\s+made\s+(?:of|from)\s+)(.+)", sentence, re.I)
        if part:
            result.append(("material.parts", {part.group(1).lower().rstrip("s"): part.group(2).rstrip(".")}))
        sentence_patterns = [
            ("colourOptions", r"\b(?:available colou?rs?\s+include|colou?r options\s+include)\s+(.+)"),
            ("colour.availableOptions", r"\b(?:available colou?rs?\s+include|colou?r options\s+include)\s+(.+)"),
            ("material", r"\b(?:item|product|bench|bar|rack|trainer|attachment|it)\s+is\s+made\s+(?:of|from)\s+(.+)"),
            ("included", r"\b(?:comes? with|includes|package contains)\s+(.+)"),
            ("sellingUnit", r"\bsold\s+(?:as|in)\s+((?:a\s+)?(?:pair|set)|individually|each)\b"),
            ("capacity.safeLoad", rf"\brated\s+(?:for|to hold|to support)\s+({_NUMBER}\s*(?:kg|lbs?|kilograms?|pounds?))\b"),
            ("resistance.stacks", rf"\b((?:dual|two|2|single|one|1)\s+{_NUMBER}\s*(?:kg|lbs?)\s+(?:weight\s+)?stacks?)\b"),
            ("resistance.increments", rf"\b({_NUMBER}\s*(?:kg|lbs?)\s+(?:per-stack\s+)?increments?)\b"),
        ]
        for key, pattern in sentence_patterns:
            match = re.search(pattern, sentence, re.I)
            if match and not any(known_key == key for known_key, _ in result[start:]):
                result.append((key, match[1].strip().rstrip(".")))
        colours = []
        finishes = []
        for match in _FINISH_COLOUR.finditer(sentence):
            prefix = sentence[:match.start()]
            if re.search(r"\b(?:not|no|never|without|unavailable|discontinued|previously|formerly|example)\b", prefix, re.I):
                continue
            component_names = _COLOUR_COMPONENT
            component = re.search(rf"\b{component_names}(?:\s+(?:has|have|with|a|an|features?))*\s*$", prefix, re.I)
            component = component or re.match(
                rf"\s+(?:on|for)\s+(?:the\s+)?{component_names}\b", sentence[match.end():], re.I)
            if component:
                result.append(("colour.parts", {component[1].lower().rstrip("s"): match[1]}))
                continue
            if re.search(rf"\b{component_names}\b", prefix, re.I):
                continue
            colours.append(match[1])
            finishes.append(match[0])
        if colours and not any(key == "colourOptions" for key, _ in result[start:]):
            result.append(("colourOptions", _DescriptiveColour(" and ".join(dict.fromkeys(colours)))))
        if finishes and not any(key == "finish" for key, _ in result[start:]):
            result.append(("finish", " and ".join(dict.fromkeys(finishes))))
        for match in _PART_COLOUR.finditer(sentence):
            if not re.search(r"\b(?:not|no|never|without|unavailable|discontinued|previously|formerly|example)\b",
                             sentence[:match.start()], re.I):
                result.append(("colour.parts", {match[2].lower().rstrip("s"): match[1]}))
    return result


def _comparable(value: object, key: str) -> object:
    if key in {"colourOptions", "colour.availableOptions"}:
        text = " ".join(value) if isinstance(value, list) and all(isinstance(v, str) for v in value) else str(value)
        tokens = re.findall(r"\w+", text.casefold())
        modifiers = {"and", "or", "matte", "gloss", "glossy", "satin", "textured", "powder", "coated", "coat", "coating", "finish", "finishes"}
        if tokens and set(tokens) <= _COLOURS | modifiers and set(tokens) & _COLOURS:
            return tuple(sorted({"grey" if token == "gray" else token for token in tokens if token in _COLOURS}))
    if isinstance(value, (dict, list)):
        return _hash(value)
    text = _normal(value).replace("×", "x").replace("–", "-")
    if key == "sellingUnit":
        return {"a pair": "pair", "a set": "set", "individually": "each"}.get(text, text)
    if key in {"weight.own", "capacity.safeLoad"}:
        magnitude = re.sub(r"^(?:approximately|approx\.?|about|~)\s*", "", text)
        match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(kg|kilograms?|g|grams?|lb|lbs|pounds?)", magnitude)
        if match:
            scale = Decimal("1") if match[2].startswith(("kg", "kilogram")) else Decimal(".001") if match[2].startswith("g") else Decimal(".45359237")
            return ("mass", Decimal(match[1]) * scale)
    if key.startswith(("compat.", "dimensions.")):
        parsed = _measurement(value)
        if parsed:
            numbers, unit, scope, semantic = parsed
            if unit in {"mm", "cm", "in"}:
                scale = {"mm": Decimal(1), "cm": Decimal(10), "in": Decimal("25.4")}[unit]
                return ("measurement", tuple(n * scale for n in numbers), scope, semantic)
    return text


def project_facts(item: dict, allowed_topics: list[str] | None = None) -> dict[str, dict]:
    """Project every registry key, retaining missing values as explicit unknown."""
    topics = TOPICS if allowed_topics is None else set(allowed_topics)
    claims: dict[str, list[dict]] = {key: [] for key in FIELD_REGISTRY}

    def add(key: str, value: object, locator: str, doc: dict | None = None, state: str = "answered") -> None:
        if key not in FIELD_REGISTRY or not _safe_value(value):
            return
        if state == "answered" and not _present(value):
            return
        evidence = _source(item, key, locator, value, doc)
        candidate = {"value": _json_copy(value), "evidence": evidence, "status": state,
                     "partial": isinstance(value, _DescriptiveColour)}
        if candidate not in claims[key]:
            claims[key].append(candidate)
        if key in {"material.parts", "colour.parts"} and isinstance(value, dict):
            for component, content in value.items():
                name = str(component).casefold().rstrip("s")
                if name in _COMPONENTS:
                    add(f"{key.split('.')[0]}.{name}", content, f"{locator}.{component}", doc, state)

    for key, spec in FIELD_REGISTRY.items():
        for path in spec.paths:
            value = _path(item, path)
            if key.startswith("price."):
                value = _money(value, item.get("currency"))
            if isinstance(value, str) and value.strip().lower() in {"n/a", "not applicable"}:
                add(key, None, path, state="not_applicable")
            elif _present(value):
                add(key, value, path)
    for path in ("description", "shortDescription", "features", "notes", "dimensions", "material", "included"):
        raw = item.get(path)
        text = "\n".join(raw) if isinstance(raw, list) and all(isinstance(v, str) for v in raw) else raw
        if isinstance(text, str):
            for key, value in _extract(text, item):
                add(key, value, path)
    docs = item.get("approvedKnowledge", [])
    for doc in docs if isinstance(docs, list) else []:
        if not isinstance(doc, dict) or not isinstance(doc.get("sourceId"), str) or not doc["sourceId"]:
            continue
        if (doc.get("approval", "approved") != "approved" or doc.get("approved") is False
                or doc.get("state") in {"pending", "rejected", "expired", "stale", "withdrawn", "unknown"}
                or doc.get("status") in {"pending", "rejected", "expired", "stale", "withdrawn"}):
            continue
        topic = doc.get("topic", "products")
        if topic not in topics:
            continue
        locator = str(doc.get("location") or doc.get("locator") or "approvedKnowledge")
        explicit = ALIASES.get(str(doc.get("key", "")))
        if explicit and FIELD_REGISTRY[explicit].topic != "pricing" and FIELD_REGISTRY[explicit].topic == topic:
            state = doc.get("state", "known")
            if state == "not_applicable":
                add(explicit, None, locator, doc, "not_applicable")
            elif state in ("known", "answered") and not _NON_ASSERTION.search(str(doc.get("text", ""))):
                add(explicit, doc.get("value"), locator, doc)
        if (isinstance(doc.get("text"), str) and topic in {"products", "compatibility"}
                and doc.get("state") != "not_applicable"):
            for key, value in _extract(doc["text"], item):
                if FIELD_REGISTRY[key].topic in topics:
                    add(key, value, locator, doc)
    result = {}
    for key, candidates in claims.items():
        fact: dict = {"key": key, "status": "unknown", "value": None, "evidenceIds": [], "sources": []}
        if FIELD_REGISTRY[key].topic not in topics:
            fact["status"] = "scope_disabled"
        elif candidates:
            # Disagreement is a field conflict, never silently settled by order.
            comparable = {(entry["status"], _comparable(entry["value"], key)) for entry in candidates}
            preferred = candidates[0]
            if key == "colourOptions" and all(c["status"] == "answered" for c in candidates):
                complete = [c for c in candidates if not c["partial"]]
                complete_values = {_comparable(c["value"], key) for c in complete}
                if len(complete_values) == 1:
                    complete_colours = next(iter(complete_values))
                    if isinstance(complete_colours, tuple) and all(
                        isinstance(colours := _comparable(c["value"], key), tuple)
                        and set(colours) <= set(complete_colours) for c in candidates
                    ):
                        comparable = {("answered", complete_colours)}
                        preferred = complete[0]
            parts = {}
            parts_conflict = False
            if key in {"material.parts", "colour.parts"} and all(c["status"] == "answered" and isinstance(c["value"], dict) for c in candidates):
                for candidate in candidates:
                    for part, material in candidate["value"].items():
                        if part in parts and _normal(parts[part]) != _normal(material):
                            parts_conflict = True
                        parts[part] = material
                if not parts_conflict:
                    comparable = {("answered", _hash(parts))}
            if len(comparable) > 1:
                fact["status"] = "conflicted"
                fact["candidates"] = [{"value": c["value"], "status": c["status"],
                                       "evidenceIds": [c["evidence"]["id"]]} for c in candidates]
            else:
                fact.update(status=preferred["status"], value=parts or preferred["value"])
                if key == "colourOptions" and preferred["partial"]:
                    fact["claimScope"] = "described_finish"
            fact["sources"] = [c["evidence"] for c in candidates]
            fact["evidenceIds"] = list(dict.fromkeys(c["evidence"]["id"] for c in candidates))
        result[key] = fact
    return result


def requested_fields(question: str) -> list[str]:
    """Recognize catalog fields without treating a load question as own weight."""
    text = re.sub(r"\bweight[\s-]+bench(?:es)?\b", "bench", question, flags=re.I)
    capacity = FIELD_REGISTRY["capacity.safeLoad"].query
    fields = []
    if re.search(capacity, text, re.I):
        fields.append("capacity.safeLoad")
        text = re.sub(capacity, " ", text, flags=re.I)
    for key, spec in FIELD_REGISTRY.items():
        if key == "capacity.safeLoad" or not spec.query:
            continue
        if re.search(spec.query, text, re.I):
            fields.append(key)
    if "resistance.stacks" in fields or "resistance.increments" in fields:
        without_stacks = re.sub(r"\b(?:weight stacks?|stack weights?|weight increments?|weight steps?)\b", "", text, flags=re.I)
        if not re.search(FIELD_REGISTRY["weight.own"].query, without_stacks, re.I):
            fields = [key for key in fields if key != "weight.own"]
    if "resistance.increments" in fields:
        without_increments = re.sub(r"\b(?:(?:weight|resistance)\s+)?(?:stacks?\s+)?increments?\b", "", text, flags=re.I)
        if not re.search(FIELD_REGISTRY["resistance.stacks"].query, without_increments, re.I):
            fields = [key for key in fields if key != "resistance.stacks"]
    if "weight.own" in fields:
        without_own_question = re.sub(
            r"\bhow much(?:(?!\band\b|\bplus\b|[?;]).){0,80}\b(?:weigh|weight)\b", "", text, flags=re.I)
        if not re.search(FIELD_REGISTRY["price.current"].query, without_own_question, re.I):
            fields = [key for key in fields if key != "price.current"]
    if "price.msrp" in fields and not re.search(r"\b(?:current|selling|sale)\s+price\b|\bprice\s+and\b", text, re.I):
        fields = [key for key in fields if key != "price.current"]
    if "compat.holeSpacing" in fields:
        fields = [key for key in fields if key != "compat.holeDiameter" or re.search(r"\bdiameter\b", text, re.I)]
    if "compat.requiredDepth" in fields:
        fields = [key for key in fields if key != "dimensions.depth"]
    if any(key.startswith(("dimensions.", "compat.")) for key in fields):
        fields = [key for key in fields if key != "dimensions" or re.search(r"\bdimensions?\b", text, re.I)]
    if "material.parts" in fields and not re.search(r"\boverall material\b", text, re.I):
        fields = [key for key in fields if key != "material"]
    if "colour.parts" in fields and not re.search(r"\b(?:overall|available)\s+colou?rs?\b", text, re.I):
        fields = [key for key in fields if key != "colourOptions"]
    if "colour.availableOptions" in fields:
        fields = [key for key in fields if key != "colourOptions"]
    components = list(dict.fromkeys(match[0].casefold().rstrip("s")
                                    for match in re.finditer(_COLOUR_COMPONENT, text, re.I)
                                    if (match.start() == 0 or not text[match.start() - 1].isalnum())
                                    and (match.end() == len(text) or not text[match.end()].isalnum())))
    for family, group, general in (("material", "material.parts", "material"),
                                    ("colour", "colour.parts", "colourOptions")):
        if components and (group in fields or general in fields):
            fields = [key for key in fields if key != group and
                      (key != general or re.search(r"\boverall\b", text, re.I))]
            fields.extend(f"{family}.{name}" for name in components if name in _COMPONENTS)
        elif not components and re.search(rf"\b(?:component|parts?)\s+{'materials?' if family == 'material' else 'colou?rs?'}\b", text, re.I):
            fields = [key for key in fields if key != general]
            fields.append(group)
    if len(fields) > 1:
        fields = [key for key in fields if key != "description"]
    return list(dict.fromkeys(fields))


def _names(item: dict) -> list[str]:
    names = [str(item.get("name", "")), str(item.get("modelSku", ""))]
    brand = item.get("brand")
    if isinstance(brand, str) and brand.strip() and names[0].casefold().startswith(brand.casefold() + " "):
        names.append(names[0][len(brand):].strip())
    aliases = item.get("aliases", [])
    if isinstance(aliases, list):
        names.extend(alias for alias in aliases if isinstance(alias, str))
    return [name for name in names if re.search(r"[^\W_]", name)]


def _mentions(item: dict, question: str) -> bool:
    return any(re.search(_name_pattern(name), question, re.I) for name in _names(item))


def _name_pattern(name: str) -> str:
    tokens = re.findall(r"[^\W_]+", name)
    return r"(?<!\w)" + r"[\W_]+".join(re.escape(token) for token in tokens) + r"(?!\w)"


def mask_item_mentions(question: str, items: list[dict]) -> str:
    """Mask resolved titles/aliases with spaces without inventing customer data."""
    masked = question
    names = sorted({name for item in items for name in _names(item)}, key=len, reverse=True)
    for name in names:
        if not re.findall(r"[^\W_]+", name):
            continue
        masked = re.sub(_name_pattern(name), lambda match: " " * len(match[0]), masked, flags=re.I)
    return masked


def _resolve(evidence: list[dict], question: str, resolver: Callable | None) -> list[dict]:
    found = resolver(evidence, question) if resolver else [item for item in evidence if _mentions(item, question)]
    refs = {entry.get("ref") if isinstance(entry, dict) else entry for entry in found or []}
    return [item for item in evidence if item["ref"] in refs]


def _valid_slot(value: object) -> bool:
    if isinstance(value, str):
        return 0 < len(value) <= 500
    if isinstance(value, dict):
        return (set(value) <= {"value", "unit", "semantic", "scope", "tolerance", "raw"}
                and isinstance(value.get("value"), (str, int, float, list))
                and _safe_value(value) and len(json.dumps(value)) <= 1200)
    return False


_NUMBER = r"(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)"
_UNIT = r'(?:mm|cm|inches|inch|in\b|["″”]|millimet(?:er|re)s?)'


def _customer_slots(question: str) -> dict:
    slots = {}
    upright = re.search(rf"(?<!\w)({_NUMBER}\s*{_UNIT}?\s*[x×]\s*{_NUMBER}\s*{_UNIT}?)(?!\w)", question, re.I)
    if upright:
        slots["uprightSize"] = upright[1].strip()
    for name, pattern in (
        ("holeDiameter", rf"({_NUMBER}\s*{_UNIT})\s*(?:diameter\s*)?holes?"),
        ("holeSpacing", rf"({_NUMBER}\s*{_UNIT})\s*(?:hole\s*)?(?:spacing|pitch)"),
        ("requiredDepth", rf"({_NUMBER}\s*{_UNIT})\s*(?:(internal|inside|overall|external)\s*)?depth"),
    ):
        match = re.search(pattern, question, re.I)
        if match:
            slots[name] = match[0].strip()
    for name, label in (
        ("holeDiameter", r"(?:holes?|hole diameter)"),
        ("holeSpacing", r"(?:hole spacing|hole pitch)"),
        ("requiredDepth", r"(?:(?:internal|inside|overall|external)\s+)?depth"),
    ):
        match = re.search(rf"\b{label}\s*(?::|=|is|are|of)?\s*{_NUMBER}\s*{_UNIT}", question, re.I)
        if match:
            slots[name] = match[0].strip()
    if re.search(r"\b(?:calipers?|measured|measurement)\b", question, re.I):
        clauses = re.split(r";|,|\band\b|\bwith\b", question, flags=re.I)
        slots = {
            key: value if any(value in clause and re.search(r"\bnominal\b", clause, re.I) for clause in clauses)
            else {"value": value, "semantic": "measured"}
            for key, value in slots.items()
        }
    return slots


def parse_customer_slots(question: str, resolved_items: list[dict] | None = None) -> dict:
    """Extract only explicit customer measurement labels and raw observations.

    A bare ``1 inch`` does not identify a hole diameter. Only a single missing
    pending slot can supply that context in ``build_plan``; model suggestions
    alone cannot assign an unlabeled measurement to a dimension.
    """
    if not isinstance(question, str) or len(question) > 12000:
        raise ValueError("Invalid customer measurement text.")
    return _customer_slots(mask_item_mentions(question, resolved_items or []))


def _decimal(number: str) -> Decimal:
    if "/" not in number:
        return Decimal(number)
    whole, fraction = number.split(" ", 1) if " " in number else ("0", number)
    numerator, denominator = fraction.split("/")
    return Decimal(whole) + Decimal(numerator) / Decimal(denominator)


def _measurement(value: object) -> tuple[list[Decimal], str, str, str] | None:
    raw = value
    semantic, scope = "nominal", ""
    unit_hint = ""
    if isinstance(value, dict):
        raw = value.get("value", value.get("labels", ""))
        semantic = str(value.get("semantic", "nominal"))
        scope = str(value.get("scope", ""))
        unit_hint = str(value.get("unit", ""))
        if value.get("tolerance") is not None:
            semantic = "measured"
    text = str(raw).lower().replace("″", '"').replace("”", '"').replace("×", "x")
    if re.search(r"(?<!\w)-\s*\d", text):
        return None
    if re.search(r"\b(?:measured|caliper|actual)\b", text):
        semantic = "measured"
    if re.search(r"\b(?:approximately|approx|about)\b|[~±]", text):
        semantic = "approximate"
    if not scope:
        scope = "internal" if re.search(r"\b(?:inside|internal|usable)\b", text) else "overall" if re.search(r"\b(?:overall|external|outside)\b", text) else ""
    units = re.findall(_UNIT, text)
    normalized_units = [("mm" if unit.startswith(("mm", "millimet")) else "cm" if unit == "cm" else "in") for unit in units]
    if len(set(normalized_units)) > 1:
        return None
    unit = normalized_units[0] if normalized_units else unit_hint
    try:
        values = [_decimal(number) for number in re.findall(_NUMBER, text)]
    except (InvalidOperation, ZeroDivisionError):
        return None
    if not values:
        return None
    return values, unit, scope, semantic


def _compare_measurement(required: object, supplied: object, key: str) -> str:
    # Multiple published nominal labels are alternatives, not unit equivalence.
    if isinstance(required, dict) and isinstance(required.get("labels"), list):
        labels = required["labels"]
    elif isinstance(required, dict):
        labels = [required]
    else:
        labels = re.split(r"\s+/\s+|\s+or\s+", str(required))
    outcomes = []
    for label in labels:
        left, right = _measurement(label), _measurement(supplied)
        if left is None or right is None:
            outcomes.append("unresolved")
            continue
        a, ua, sa, ma = left
        b, ub, sb, mb = right
        if ma != "nominal" or mb != "nominal":
            outcomes.append("unresolved")
            continue
        if key == "requiredDepth" and (not sa or not sb or sa != sb):
            outcomes.append("unresolved")
            continue
        if len(a) != len(b):
            outcomes.append("unresolved")
            continue
        if not ua or not ub:
            outcomes.append("conditional" if key == "uprightSize" and a == b else "unresolved")
            continue
        scale = {"in": Decimal("25.4"), "mm": Decimal(1), "cm": Decimal(10)}
        if ua not in scale or ub not in scale:
            outcomes.append("unresolved")
            continue
        am = [number * scale[ua] for number in a]
        bm = [number * scale[ub] for number in b]
        if am == bm or (key == "requiredDepth" and len(am) == 1 and bm[0] >= am[0]):
            outcomes.append("match")
        elif key == "uprightSize" and ua != ub:
            outcomes.append("unresolved")
        else:
            outcomes.append("mismatch")
    if "match" in outcomes:
        return "match"
    if "conditional" in outcomes:
        return "conditional"
    if "unresolved" in outcomes:
        return "unresolved"
    return "mismatch"


def _compatibility(facts: dict[str, dict], slots: dict) -> dict:
    published = [key for key in FIELD_REGISTRY if key.startswith("compat.") and facts[key]["status"] != "unknown"]
    required = [name for name in CONSTRAINTS if facts[f"compat.{name}"]["status"] in {"answered", "conflicted"}]
    if facts["compat.models"]["status"] == "answered" and re.search(r"\bonly\b", str(facts["compat.models"]["value"]), re.I):
        required.append("model")
    value: dict = {"status": "insufficient_data", "required": required, "missing": [],
                  "mismatches": [], "uncertain": [], "evidenceIds": []}
    for key in published:
        value["evidenceIds"].extend(facts[key]["evidenceIds"])
    value["evidenceIds"] = list(dict.fromkeys(value["evidenceIds"]))
    if any(facts[key]["status"] == "conflicted" for key in published):
        value["status"] = "conflicting_evidence"
        return value
    if not required:
        if facts["compat.models"]["status"] == "answered" and not slots.get("model"):
            value["missing"] = ["model"]
        return value
    outcomes = {}
    models = facts["compat.models"]
    limitations = facts["compat.limitations"]
    model = _normal(slots.get("model", ""))
    if models["status"] == "answered" and re.search(r"\bonly\b", str(models["value"]), re.I):
        if not model:
            value["missing"].append("model")
        elif model not in _normal(models["value"]):
            outcomes["model"] = "mismatch"
    if model and limitations["status"] == "answered" and re.search(
        r"\b(?:not compatible with|does not fit|not for|excludes)\s+" + re.escape(model) + r"(?!\w)",
        _normal(limitations["value"]),
    ):
        outcomes["model"] = "mismatch"
    for key in required:
        if key == "model":
            continue
        if not _present(slots.get(key)):
            value["missing"].append(key)
        else:
            outcomes[key] = _compare_measurement(facts[f"compat.{key}"]["value"], slots[key], key)
    value["mismatches"] = [key for key, state in outcomes.items() if state == "mismatch"]
    value["uncertain"] = [key for key, state in outcomes.items() if state == "unresolved"]
    if value["mismatches"]:
        value["status"] = "known_mismatch"
    elif value["missing"]:
        value["status"] = "listed_requirements"
    elif value["uncertain"]:
        value["status"] = "insufficient_data"
    elif "conditional" in outcomes.values() or facts["compat.limitations"]["status"] == "answered" or facts["compat.models"]["status"] == "answered":
        value["status"] = "conditional_match"
    else:
        value["status"] = "requirements_match_not_verified"
    return value


def _clean_requests(requests: list[dict], lookup: dict[str, dict]) -> list[dict]:
    if not isinstance(requests, list) or not requests or len(requests) > MAX_ITEMS:
        raise ValueError("A plan requires one to eight bounded item requests.")
    result = []
    ids = set()
    for request in requests:
        if not isinstance(request, dict) or set(request) - {"ref", "fields", "compatibility", "slots", "requestId", "targetRef"}:
            raise ValueError("Invalid item request.")
        ref = request.get("ref")
        if ref not in lookup:
            raise ValueError("Unknown catalog reference.")
        fields = request.get("fields", [])
        if not isinstance(fields, list) or len(fields) > len(FIELD_REGISTRY) or any(not isinstance(k, str) or k not in ALIASES for k in fields):
            raise ValueError("Unknown field request.")
        keys = list(dict.fromkeys(ALIASES[key] for key in fields))
        compat = request.get("compatibility", False)
        slots = request.get("slots", {})
        if not isinstance(compat, bool) or not isinstance(slots, dict) or set(slots) - SLOT_NAMES or any(not _valid_slot(v) for v in slots.values()):
            raise ValueError("Invalid customer slots.")
        target = request.get("targetRef")
        if target is not None and (not compat or target not in lookup or target == ref):
            raise ValueError("Invalid compatibility target.")
        identity = [ref, keys, compat] + ([target] if target else [])
        identifier = request.get("requestId") or "request:" + _hash(identity)[:20]
        if not isinstance(identifier, str) or len(identifier) > 100 or not identifier or (ref, identifier) in ids:
            raise ValueError("Invalid or duplicate request identity.")
        ids.add((ref, identifier))
        clean = {"ref": ref, "requestId": identifier, "fields": keys, "compatibility": compat, "slots": deepcopy(slots)}
        if target:
            clean["targetRef"] = target
        result.append(clean)
    return result


def _display(value: object) -> str:
    if isinstance(value, dict) and set(value) == {"amountMinor", "currency"}:
        return f"{value['currency']} ${Decimal(value['amountMinor']) / 100:,.2f}"
    if isinstance(value, list):
        return "; ".join(_display(part) for part in value)
    if isinstance(value, dict):
        return "; ".join(f"{key}: {_display(part)}" for key, part in value.items())
    return str(value)


def _field_sentence(name: str, key: str, value: object, claim_scope: str | None = None) -> str:
    content = _display(value).strip()
    if claim_scope == "described_finish":
        return (f"The published information for {name} describes a {content} finish. "
                "That describes the finish, not a confirmed list of available colour choices.")
    if key == "weight.own":
        content = re.sub(r"^approx\.?\s*", "approximately ", content, flags=re.I)
    if key == "sellingUnit":
        content = {"each": "an individual item", "pair": "a pair", "set": "a set"}.get(content.casefold(), content)
    templates = {
        "price.current": "The current listed price for {name} is {content}",
        "price.msrp": "The listed MSRP for {name} is {content}",
        "weight.own": "{name} weighs {content}",
        "brand": "The brand for {name} is {content}",
        "dimensions": "The listed dimensions for {name} are {content}",
        "material": "{name} is listed as being made from {content}",
        "included": "Here is what comes with {name}: {content}",
        "sellingUnit": "{name} is sold as {content}",
        "colourOptions": "The listed colour options for {name} are {content}",
        "modelSku": "The listed model or SKU for {name} is {content}",
        "stockStatus": "Our catalog currently shows {name} as {content}",
        "warranty": "For {name}, the listed warranty says: {content}",
        "features": "Features listed for {name} include {content}",
        "packageQuantity": "The package quantity listed for {name} is {content}",
    }
    if key == "stockStatus":
        content = content.lower()
    sentence = templates.get(key, FIELD_REGISTRY[key].label + ": {content}").format(name=name, content=content)
    return sentence if sentence.endswith((".", "!", "?")) else sentence + "."


def _render(items: list[dict], clarification: str | None = None) -> tuple[str, bool]:
    if clarification:
        return {
            "item": "Which product or accessory would you like me to check?",
            "assignment": "Which details would you like for each item? I don't want to assign a specification to the wrong product.",
            "limit": "Please narrow this to eight items or fewer so I can keep every requested detail together.",
        }[clarification], True
    blocks = []
    for item in items:
        lines = [f"Here's what's published for {item['name']}:"]
        compat = item.get("compatibility")
        if compat:
            state = compat["status"]
            lines.append({
                "listed_requirements": "These are the published requirements.",
                "known_mismatch": "Your equipment does not match a published compatibility requirement. Do not modify mounting parts to force a fit.",
                "conditional_match": "The supplied labels are consistent with the listed requirements, subject to the published limitations. Fit is not verified.",
                "requirements_match_not_verified": "The supplied measurements match the listed requirements, but fit is not verified for your exact model and variant.",
                "insufficient_data": "The published information and supplied measurements aren't enough to confirm fit.",
                "conflicting_evidence": "The published compatibility details disagree; our team needs to confirm them before advising on fit.",
            }[state])
            if compat.get("targetRef"):
                lines.append(f"Target: {compat['targetName']}. Published labels and any customer measurements are compared; no tested fit is claimed.")
        for fact in item["fields"]:
            label = FIELD_REGISTRY[fact["key"]].label
            state = fact["status"]
            if state == "answered":
                lines.append(_field_sentence(item["name"], fact["key"], fact["value"], fact.get("claimScope")))
                continue
            detail = {
                "unknown": "not published in the available information",
                "conflicted": "published sources disagree; our team needs to confirm",
                "scope_disabled": "not available in the enabled support topics",
                "not_applicable": "explicitly listed as not applicable",
            }[state]
            lines.append(f"{label}: {detail}.")
        if compat:
            needed = list(dict.fromkeys(compat["missing"] + compat["uncertain"]))
            if needed:
                labels = [FIELD_REGISTRY[f"compat.{key}"].label.lower() if f"compat.{key}" in FIELD_REGISTRY else key for key in needed]
                lines.append("Could you share your equipment's " + ", ".join(labels) + "? Keep nominal labels, measured values and internal/overall dimensions separate.")
        blocks.append(lines)
    text = "\n\n".join("\n".join(lines) for lines in blocks)
    if len(items) == 1 and len(items[0]["fields"]) == 1 and items[0].get("compatibility") is None:
        text = "\n".join(blocks[0][1:])
    if len(text) <= MAX_TEXT:
        return text, False
    # Whole facts only; compatibility warnings precede detail, never cut mid-fact.
    output = []
    remaining = MAX_TEXT - 220
    for item, lines in zip(items, blocks):
        count = 1 + bool(item.get("compatibility")) + bool((item.get("compatibility") or {}).get("targetRef"))
        summary = lines[:count]
        for line in summary:
            output.append(line)
            remaining -= len(line) + 2
    for item, lines in zip(items, blocks):
        count = 1 + bool(item.get("compatibility")) + bool((item.get("compatibility") or {}).get("targetRef"))
        details = lines[count:]
        for line in details:
            if len(line) + 2 <= remaining:
                output.append(line)
                remaining -= len(line) + 2
    output.append("This answer is partial because the requested information is too long to display together. Please narrow the items or fields; the full plan retains all requested fields.")
    return "\n".join(output), True


@dataclass
class CatalogPlan:
    status: str
    items: list[dict] = field(default_factory=list)
    references: list[dict] = field(default_factory=list)
    pending_slots: dict = field(default_factory=dict)
    needs_human: bool = False
    requested_scopes: list[str] = field(default_factory=list)
    text: str = ""
    requests: list[dict] = field(default_factory=list)
    human_scopes: list[dict] = field(default_factory=list)
    clarification: str | None = None
    limited: bool = False
    schema_version: int = SCHEMA_VERSION

    @property
    def item_references(self) -> tuple[str, ...]:
        """Response item identities, distinct from the evidence reference rows."""
        return tuple(dict.fromkeys(item["ref"] for item in self.items))

    def to_dict(self) -> dict:
        return deepcopy({
            "schemaVersion": self.schema_version, "status": self.status, "items": self.items,
            "references": self.references, "itemReferences": list(self.item_references),
            "pendingSlots": self.pending_slots, "needsHuman": self.needs_human,
            "requestedScopes": self.requested_scopes, "text": self.text, "requests": self.requests,
            "humanScopes": self.human_scopes, "clarification": self.clarification, "limited": self.limited,
        })

    @classmethod
    def from_dict(cls, value: dict) -> CatalogPlan:
        expected = {"schemaVersion", "status", "items", "references", "itemReferences", "pendingSlots", "needsHuman",
                    "requestedScopes", "text", "requests", "humanScopes", "clarification", "limited"}
        if (not isinstance(value, dict) or set(value) != expected or type(value["schemaVersion"]) is not int
                or value["schemaVersion"] != SCHEMA_VERSION or value["status"] not in {"complete", "partial", "clarification", "unavailable"}
                or not isinstance(value["text"], str) or len(value["text"]) > MAX_TEXT
                or type(value["needsHuman"]) is not bool or type(value["limited"]) is not bool
                or value["clarification"] not in {None, "item", "assignment", "limit"}):
            raise ValueError("Invalid catalog plan boundary.")
        for key, maximum in (("items", MAX_ITEMS), ("requests", MAX_ITEMS), ("references", 1500),
                             ("itemReferences", MAX_ITEMS),
                             ("requestedScopes", len(TOPICS)), ("humanScopes", MAX_ITEMS * (len(FIELD_REGISTRY) + 1))):
            if not isinstance(value[key], list) or len(value[key]) > maximum:
                raise ValueError("Unbounded catalog plan.")
        if not isinstance(value["pendingSlots"], dict) or len(value["pendingSlots"]) > MAX_ITEMS:
            raise ValueError("Invalid pending slots.")
        _validate_shape(value)
        copied = _json_copy(value)
        return cls(copied["status"], copied["items"], copied["references"], copied["pendingSlots"],
                   copied["needsHuman"], copied["requestedScopes"], copied["text"], copied["requests"],
                   copied["humanScopes"], copied["clarification"], copied["limited"], copied["schemaVersion"])


def _validate_shape(plan: dict) -> None:
    """Strict bounded nested schema at the persistence/model trust boundary."""
    def shape(value: object, keys: set[str]) -> dict:
        if not isinstance(value, dict) or set(value) != keys:
            raise ValueError("Invalid catalog plan object.")
        return value

    def strings(value: object, maximum: int, choices: set | frozenset | None = None) -> None:
        if (not isinstance(value, list) or len(value) > maximum
                or any(not isinstance(v, str) or len(v) > 2000 or (choices is not None and v not in choices) for v in value)):
            raise ValueError("Invalid catalog plan list.")

    if len(json.dumps(plan, allow_nan=False)) > 4_000_000:
        raise ValueError("Catalog plan exceeds its persistence budget.")
    strings(plan["requestedScopes"], len(TOPICS), TOPICS)
    for entry in plan["items"]:
        shape(entry, {"ref", "name", "requestId", "fields", "compatibility"})
        if (not isinstance(entry["ref"], str) or not _REFERENCE.fullmatch(entry["ref"])
                or not isinstance(entry["name"], str) or len(entry["name"]) > 200
                or not isinstance(entry["requestId"], str) or len(entry["requestId"]) > 100
                or not isinstance(entry["fields"], list) or len(entry["fields"]) > len(FIELD_REGISTRY)):
            raise ValueError("Invalid catalog plan item.")
        for fact in entry["fields"]:
            if not isinstance(fact, dict):
                raise ValueError("Invalid catalog plan field.")
            keys = {"key", "status", "value", "evidenceIds"}
            if fact.get("status") == "conflicted":
                keys.add("candidates")
            if "claimScope" in fact:
                keys.add("claimScope")
                if fact.get("key") != "colourOptions" or fact.get("status") != "answered" or fact["claimScope"] != "described_finish":
                    raise ValueError("Invalid catalog fact scope.")
            shape(fact, keys)
            if (fact["key"] not in FIELD_REGISTRY or fact["status"] not in FIELD_STATUSES
                    or not _safe_value(fact["value"])
                    or (fact["status"] != "answered" and fact["value"] is not None)):
                raise ValueError("Invalid catalog plan fact.")
            strings(fact["evidenceIds"], 200)
            if "candidates" in fact:
                if not isinstance(fact["candidates"], list) or not 2 <= len(fact["candidates"]) <= 200:
                    raise ValueError("Invalid catalog conflict.")
                for candidate in fact["candidates"]:
                    shape(candidate, {"value", "status", "evidenceIds"})
                    if candidate["status"] not in {"answered", "not_applicable"} or not _safe_value(candidate["value"]):
                        raise ValueError("Invalid conflict candidate.")
                    strings(candidate["evidenceIds"], 200)
        compatibility = entry["compatibility"]
        if compatibility is not None:
            keys = {"status", "required", "missing", "mismatches", "uncertain", "evidenceIds"}
            if "targetRef" in compatibility:
                keys |= {"targetRef", "targetName", "targetEvidenceIds"}
                if (not isinstance(compatibility["targetRef"], str) or not _REFERENCE.fullmatch(compatibility["targetRef"])
                        or not isinstance(compatibility["targetName"], str) or len(compatibility["targetName"]) > 200):
                    raise ValueError("Invalid compatibility target identity.")
                strings(compatibility["targetEvidenceIds"], 1200)
            shape(compatibility, keys)
            if compatibility["status"] not in COMPATIBILITY_STATUSES:
                raise ValueError("Invalid compatibility assertion.")
            for key in ("required", "missing", "mismatches", "uncertain"):
                strings(compatibility[key], len(SLOT_NAMES), SLOT_NAMES)
            strings(compatibility["evidenceIds"], 1200)
    for source in plan["references"]:
        shape(source, {"id", "ref", "field", "kind", "locator", "sourceId", "sourceHash", "revision", "valueHash"})
        if (any(not isinstance(v, str) or len(v) > 2000 for v in source.values())
                or source["field"] not in FIELD_REGISTRY or source["kind"] not in {"public_catalog", "approved_knowledge"}):
            raise ValueError("Invalid catalog evidence.")
    strings(plan["itemReferences"], MAX_ITEMS)
    if plan["itemReferences"] != list(dict.fromkeys(item["ref"] for item in plan["items"])):
        raise ValueError("Response references do not match catalog plan items.")
    if plan["requests"]:
        lookup = {request.get("ref"): {} for request in plan["requests"] if isinstance(request, dict)}
        _clean_requests(plan["requests"], lookup)
    for ref, scoped in plan["pendingSlots"].items():
        if not isinstance(ref, str) or not _REFERENCE.fullmatch(ref) or not isinstance(scoped, dict) or len(scoped) > MAX_ITEMS:
            raise ValueError("Invalid pending product.")
        for identifier, pending in scoped.items():
            keys = {"fields", "compatibility", "slots", "missing"}
            target = {}
            lookup = {ref: {}}
            if isinstance(pending, dict) and "targetRef" in pending:
                keys.add("targetRef")
                target = {"targetRef": pending["targetRef"]}
                lookup[pending["targetRef"]] = {}
            shape(pending, keys)
            _clean_requests([{"ref": ref, "requestId": identifier, "fields": pending["fields"],
                              "compatibility": pending["compatibility"], "slots": pending["slots"], **target}], lookup)
            strings(pending["missing"], len(SLOT_NAMES), SLOT_NAMES)
    for scope in plan["humanScopes"]:
        shape(scope, {"ref", "requestId", "field", "reason"})
        if (any(not isinstance(v, str) or len(v) > 200 for v in scope.values())
                or scope["field"] not in {*FIELD_REGISTRY, "compatibility"}
                or scope["reason"] not in FIELD_STATUSES | COMPATIBILITY_STATUSES):
            raise ValueError("Invalid handoff scope.")


def _assemble(requests: list[dict], lookup: dict[str, dict], allowed_topics: list[str],
              clarification: str | None = None) -> CatalogPlan:
    if clarification and requests:
        raise ValueError("Clarification plans cannot contain substantive item requests.")
    requests = deepcopy(requests)
    for request in list(requests):
        target_ref = request.get("targetRef")
        if target_ref:
            source_facts = project_facts(lookup[request["ref"]], allowed_topics)
            target_facts = project_facts(lookup[target_ref], allowed_topics)
            target_fields = [f"compat.{key}" for key in CONSTRAINTS
                             if source_facts[f"compat.{key}"]["status"] in {"answered", "conflicted"}
                             and target_facts[f"compat.{key}"]["status"] in {"answered", "conflicted", "not_applicable"}]
            target_request = next((entry for entry in requests if entry["ref"] == target_ref), None)
            if target_request is None:
                requests.extend(_clean_requests([{"ref": target_ref, "fields": target_fields or ["name"]}], lookup))
            else:
                target_request["fields"] = list(dict.fromkeys(target_request["fields"] + target_fields))
    if len(requests) > MAX_ITEMS:
        return clarification_plan("limit")
    plan = CatalogPlan("clarification" if clarification else "complete", requests=deepcopy(requests),
                       clarification=clarification)
    sources = {}
    unresolved = False
    for request in requests:
        item = lookup[request["ref"]]
        facts = project_facts(item, allowed_topics)
        keys = list(request["fields"])
        colour_requested = "colourOptions" in keys or "colour.availableOptions" in keys
        if colour_requested and facts["colour.parts"]["status"] in {"answered", "conflicted"}:
            keys.append("colour.parts")
        if ("colour.availableOptions" in keys and facts["colour.availableOptions"]["status"] == "unknown"
                and facts["finish"]["status"] in {"answered", "conflicted"}):
            keys.append("finish")
        for family in ("material", "colour"):
            group = f"{family}.parts"
            if group in keys and facts[group]["status"] == "conflicted":
                children = [f"{family}.{name}" for name in _COMPONENTS
                            if facts[f"{family}.{name}"]["status"] in {"answered", "conflicted", "not_applicable"}]
                if children:
                    keys = [key for key in keys if key != group] + children
        compat = None
        if request["compatibility"]:
            if "compatibility" in allowed_topics:
                slots = deepcopy(request["slots"])
                target_ref = request.get("targetRef")
                target_ids = []
                target_conflict = False
                if target_ref:
                    target_facts = project_facts(lookup[target_ref], allowed_topics)
                    slots.setdefault("model", lookup[target_ref]["name"])
                    for name in CONSTRAINTS:
                        key = f"compat.{name}"
                        slots.pop(name, None)
                        if facts[key]["status"] not in {"answered", "conflicted"}:
                            continue
                        target_fact = target_facts[key]
                        target_conflict |= target_fact["status"] == "conflicted"
                        if target_fact["status"] == "answered":
                            if name in request["slots"]:
                                consistent = _compare_measurement(target_fact["value"], request["slots"][name], name)
                                if consistent == "mismatch":
                                    target_conflict = True
                                    continue
                                slots[name] = request["slots"][name]
                            else:
                                slots[name] = target_fact["value"]
                            target_ids.extend(target_fact["evidenceIds"])
                            for source in target_fact["sources"]:
                                sources[source["id"]] = source
                        elif target_fact["status"] == "unknown" and name in request["slots"]:
                            slots[name] = request["slots"][name]
                compat = _compatibility(facts, slots)
                if target_ref:
                    compat.update(targetRef=target_ref, targetName=lookup[target_ref]["name"],
                                  targetEvidenceIds=list(dict.fromkeys(target_ids)))
                    if target_conflict:
                        compat.update(status="conflicting_evidence", missing=[], uncertain=[])
                keys.extend(key for key in facts if key.startswith("compat.") and facts[key]["status"] != "unknown")
                if not keys:
                    keys.append("compat.uprightSize")
            else:
                keys.append("compat.uprightSize")
        elif "compatibility" in allowed_topics and not any(
            other.get("targetRef") == request["ref"] and other["compatibility"] for other in requests
        ) and any(
            key in {f"compat.{name}" for name in (*CONSTRAINTS, "models", "limitations")} for key in keys
        ):
            listed = [f"compat.{name}" for name in CONSTRAINTS
                      if facts[f"compat.{name}"]["status"] in {"answered", "conflicted"}]
            if listed:
                compat = _compatibility(facts, {})
                compat.update(status="listed_requirements", missing=[], uncertain=[])
                keys.extend(listed)
        keys = list(dict.fromkeys(keys))
        fields = []
        for key in keys:
            fact = deepcopy(facts[key])
            for source in fact.pop("sources"):
                sources[source["id"]] = source
            fields.append(fact)
            if fact.get("claimScope") == "described_finish":
                unresolved = True
            topic = FIELD_REGISTRY[key].topic
            if topic not in plan.requested_scopes:
                plan.requested_scopes.append(topic)
            if fact["status"] not in {"answered", "not_applicable"}:
                unresolved = True
                plan.human_scopes.append({"ref": item["ref"], "requestId": request["requestId"], "field": key, "reason": fact["status"]})
        if compat:
            if compat["status"] in {"insufficient_data", "conflicting_evidence", "known_mismatch"}:
                plan.human_scopes.append({"ref": item["ref"], "requestId": request["requestId"], "field": "compatibility", "reason": compat["status"]})
            missing = list(dict.fromkeys(compat["missing"] + compat["uncertain"]))
            if missing:
                unresolved = True
                plan.pending_slots.setdefault(item["ref"], {})[request["requestId"]] = {
                    "fields": request["fields"], "compatibility": True, "slots": deepcopy(request["slots"]), "missing": missing,
                }
                if request.get("targetRef"):
                    plan.pending_slots[item["ref"]][request["requestId"]]["targetRef"] = request["targetRef"]
            if compat["status"] not in {"requirements_match_not_verified", "conditional_match", "listed_requirements"}:
                unresolved = True
        plan.items.append({"ref": item["ref"], "name": item["name"], "requestId": request["requestId"],
                           "fields": fields, "compatibility": compat})
    plan.references = list(sources.values())
    plan.needs_human = bool(plan.human_scopes)
    plan.text, plan.limited = _render(plan.items, clarification)
    if not clarification and (unresolved or plan.limited):
        plan.status = "partial" if any(f["status"] == "answered" for i in plan.items for f in i["fields"]) else "unavailable"
    return plan


def _catalog(evidence: list[dict]) -> dict[str, dict]:
    lookup = {}
    for item in evidence:
        if not isinstance(item, dict) or not isinstance(item.get("ref"), str) or not _REFERENCE.fullmatch(item["ref"]):
            raise ValueError("Invalid public catalog identity.")
        if item["ref"] in lookup:
            raise ValueError("Duplicate public catalog identity.")
        if item.get("publicationStatus") == "draft":
            continue
        if not isinstance(item.get("name"), str) or not item["name"].strip() or len(item["name"]) > 200:
            raise ValueError("Invalid public catalog name.")
        lookup[item["ref"]] = item
    return lookup


def clarification_plan(reason: str = "item") -> CatalogPlan:
    """Create a fixed, claim-free clarification suitable for normal validation."""
    if reason not in {"item", "assignment", "limit"}:
        raise ValueError("Unknown clarification reason.")
    return _assemble([], {}, [], reason)


def _identity_overview(question: str, evidence: list[dict]) -> bool:
    match = re.fullmatch(r"\s*(?:what\s+(?:is|are)|what['’]s)\s+(?:the\s+)?(.+?)\s*[?!.]*", question, re.I)
    if not match:
        return False
    subject = _normal(match[1]).rstrip("?")
    return subject in {"it", "this", "that"} or any(
        subject == _normal(name) for item in evidence for name in _names(item)
    )


def _directional_items(question: str, selected: list[dict]) -> tuple[dict, dict, int] | None:
    mentions = [(item, match.start(), match.end()) for item in selected for name in _names(item)
                for match in re.finditer(_name_pattern(name), question, re.I)]
    for verb in re.finditer(r"\b(?:fits?|compatible with|works? with|mount(?:s)? (?:on|to))\b", question, re.I):
        before = [mention for mention in mentions if mention[2] <= verb.start()]
        after = [mention for mention in mentions if mention[1] >= verb.end()]
        if not before or not after:
            continue
        source = max(before, key=lambda mention: mention[2])
        target = min(after, key=lambda mention: mention[1])
        if (source[0]["ref"] != target[0]["ref"]
                and not re.search(r"[?;]|\band\b", question[verb.end():target[1]], re.I)):
            return source[0], target[0], verb.end()
    return None


def is_direct_requirements_question(question: str) -> bool:
    return bool(re.search(
        r"^\s*(?:what|which)(?:\s+(?:is|are))?\s+(?:the\s+)?"
        r"(?:(?:published|listed|compatible|required|mounting)\s+)*"
        r"(?:uprights?(?:\s+size)?|rack\s+post(?:s|\s+size)?|post\s+size|"
        r"holes?(?:\s+(?:diameter|size|spacing|pitch))?|pin\s+(?:diameter|length|dimensions?|size)|"
        r"internal\s+depth|required\s+depth|compatibility\s+(?:requirements|limitations)|requirements)\b",
        question, re.I,
    ))


def build_plan(question: str, evidence: list[dict], allowed_topics: list[str],
               item_ref: str | None = None, history: list[dict] | None = None,
               pending: dict | None = None, requests: list[dict] | None = None,
               resolve_items: Callable | None = None) -> CatalogPlan | None:
    """Build a provider-free plan, or return None for non-catalog intent.

    Explicit requests are caller-validated routing suggestions only: unknown
    refs/keys/slot shapes are rejected, and no suggested answer is accepted.
    """
    if not isinstance(question, str) or len(question) > 12000 or not set(allowed_topics) <= TOPICS:
        raise ValueError("Invalid catalog question or topic scope.")
    lookup = _catalog(evidence)
    evidence = list(lookup.values())
    if requests is not None:
        return _assemble(_clean_requests(requests, lookup), lookup, allowed_topics)
    selected = _resolve(evidence, question, resolve_items)
    mention_items = selected or ([lookup[item_ref]] if item_ref in lookup else [])
    masked_question = mask_item_mentions(question, mention_items)
    fields = ["description"] if _identity_overview(question, evidence) else requested_fields(masked_question)
    fit = bool(FIT_QUERY.search(masked_question)) and not is_direct_requirements_question(masked_question)
    observations = parse_customer_slots(question, mention_items) if pending else {}
    if pending:
        prior = []
        for ref, scoped in pending.items():
            if (ref not in lookup or not isinstance(scoped, dict)
                    or (selected and ref not in {i["ref"] for i in selected})
                    or (not selected and item_ref in lookup and ref != item_ref)):
                continue
            for identifier, saved in scoped.items():
                if isinstance(saved, dict):
                    request = {"ref": ref, "requestId": identifier, "fields": saved.get("fields", []),
                               "compatibility": saved.get("compatibility", True), "slots": saved.get("slots", {})}
                    if saved.get("targetRef") in lookup:
                        request["targetRef"] = saved["targetRef"]
                    prior.append(request)
        bare_measurement = bool(re.fullmatch(
            rf"\s*(?:(?:about|approx(?:imately)?\.?|nominal(?:ly)?)\s+)?{_NUMBER}"
            rf"(?:\s*[x×]\s*{_NUMBER})?\s*(?:{_UNIT})?\s*[.!?]?\s*",
            masked_question, re.I,
        ))
        if not observations and not fields and bare_measurement and _measurement(masked_question) and len(prior) == 1:
            saved = pending[prior[0]["ref"]][prior[0]["requestId"]]
            missing = saved.get("missing", [])
            if len(missing) == 1 and missing[0] in CONSTRAINTS:
                observation = masked_question.strip()
                observations = {missing[0]: observation if observation == question.strip()
                                else {"value": observation, "raw": question.strip()}}
        if prior and observations:
            if len(prior) > 1 and not selected:
                return _assemble([], lookup, allowed_topics, "assignment")
            for request in prior:
                request["slots"] = {**request["slots"], **observations}
                request["fields"] = list(dict.fromkeys(request["fields"] + [
                    key for key in fields if not key.startswith("compat.") and key != "dimensions.depth"
                ]))
            return _assemble(_clean_requests(prior, lookup), lookup, allowed_topics)
    if not fields and not fit:
        return None
    if not selected and item_ref in lookup:
        selected = [lookup[item_ref]]
    if not selected and history:
        for message in reversed(history[-12:]):
            if message.get("role") == "user":
                selected = _resolve(evidence, str(message.get("text", message.get("content", ""))), resolve_items)
                if selected:
                    break
            elif message.get("role") == "model" and isinstance(message.get("catalogRefs"), str):
                references = json.loads(message["catalogRefs"])
                if (not isinstance(references, list) or not references
                        or any(not isinstance(ref, str) or ref not in lookup for ref in references)):
                    return clarification_plan("item")
                selected = [lookup[ref] for ref in dict.fromkeys(references)]
                break
    if not selected and len(evidence) == 1:
        selected = evidence
    if not selected:
        return _assemble([], lookup, allowed_topics, "item")
    if len(selected) > MAX_ITEMS:
        return _assemble([], lookup, allowed_topics, "limit")
    if fit and len(selected) == 2:
        directional = _directional_items(question, selected)
        if directional:
            source, target, target_start = directional
            request = {"ref": source["ref"], "fields": [key for key in fields if key.startswith("compat.")], "compatibility": True,
                       "targetRef": target["ref"], "slots": parse_customer_slots(question[target_start:], selected)}
            routed = [request]
            for clause in re.split(r";|\?|\band\b", question, flags=re.I):
                extra = [key for key in requested_fields(mask_item_mentions(clause, selected)) if not key.startswith("compat.")]
                if not extra:
                    continue
                owners = _resolve(selected, clause, resolve_items)
                if len(owners) != 1:
                    return clarification_plan("assignment")
                owner = next((entry for entry in routed if entry["ref"] == owners[0]["ref"]), None)
                if owner is None:
                    routed.append({"ref": owners[0]["ref"], "fields": extra})
                else:
                    owner["fields"].extend(extra)
            return _assemble(_clean_requests(routed, lookup), lookup, allowed_topics)
    routed = []
    if len(selected) > 1:
        if not re.search(r"\b(?:compare|comparison|versus|vs|both|each|all|and|or)\b|[,;&]", question, re.I):
            reason = "assignment" if len(fields) > 1 and all(_mentions(item, question) for item in selected) else "item"
            return clarification_plan(reason)
        clauses = re.split(r";|\?|\band\b|\bversus\b|\bvs\.?\b|\bto\b", question, flags=re.I)
        per_clause = [(clause, _resolve(selected, clause, resolve_items),
                       requested_fields(mask_item_mentions(clause, selected))) for clause in clauses]
        local = [(clause, items, keys) for clause, items, keys in per_clause if len(items) == 1 and keys]
        if len(local) == len(selected) and {items[0]["ref"] for _, items, _ in local} == {i["ref"] for i in selected}:
            leading = []
            for clause, items, keys in per_clause:
                if len(items) == 1 and keys:
                    routed.append({"ref": items[0]["ref"], "fields": leading + keys,
                                   "compatibility": bool(FIT_QUERY.search(mask_item_mentions(clause, selected)))
                                   and not is_direct_requirements_question(mask_item_mentions(clause, selected)),
                                   "slots": parse_customer_slots(clause, selected)})
                    leading = []
                elif not items and keys:
                    if routed:
                        routed[-1]["fields"].extend(keys)
                    else:
                        leading.extend(keys)
        else:
            mentions = [match for item in selected for name in _names(item)
                        for match in re.finditer(_name_pattern(name), question, re.I)]
            prefix = question[:min(match.start() for match in mentions)] if mentions else ""
            suffix = question[max(match.end() for match in mentions):] if mentions else ""
            shared = set(fields) <= set(requested_fields(prefix)) or set(fields) <= set(requested_fields(suffix))
            explicit_comparison = bool(re.search(r"\b(?:compare|both|each|all|comparison)\b", question, re.I))
            if not shared and not explicit_comparison and (local or len(fields) > 1):
                return _assemble([], lookup, allowed_topics, "assignment")
    if not routed:
        routed = [{"ref": item["ref"], "fields": fields, "compatibility": fit,
                   "slots": parse_customer_slots(question, selected) if len(selected) == 1 else {}} for item in selected]
    return _assemble(_clean_requests(routed, lookup), lookup, allowed_topics)


def validate_plan(plan: CatalogPlan | dict, evidence: list[dict], allowed_topics: list[str]) -> bool:
    """Reject altered facts, evidence IDs/versions, rendering or fit assertions."""
    try:
        candidate = CatalogPlan.from_dict(plan.to_dict() if isinstance(plan, CatalogPlan) else plan)
        if not set(allowed_topics) <= TOPICS:
            return False
        lookup = _catalog(evidence)
        requests = _clean_requests(candidate.requests, lookup) if candidate.requests else []
        if not requests and candidate.clarification is None:
            return False
        expected = _assemble(requests, lookup, allowed_topics, candidate.clarification)
        return candidate.to_dict() == expected.to_dict()
    except (KeyError, TypeError, ValueError, OverflowError, InvalidOperation, AttributeError, RecursionError, IndexError):
        return False
