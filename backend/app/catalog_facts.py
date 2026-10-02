"""Meaning-preserving adapters for public, reviewed catalogFacts v1.

These facts describe a listing, never an offer, selectable SKU, tested pairing,
or inferred force. Empty reviewed option lists mean unspecified, not deletion.
Interface rows remain separately attributed statements, not alternative verified
configurations. Typed constraints intentionally do not enter the legacy fit math.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import re

from app.catalog_schema import public_catalog_facts


KINDS = {
    "length": "length", "width": "width", "height": "height", "depth": "depth",
    "diameter": "diameter", "weight": "own weight", "load_capacity": "load capacity",
    "resistance": "resistance", "increment": "increment",
}
SCOPES = {
    "overall": "Overall", "product": "Product", "rack": "Rack", "upright": "Upright",
    "smith_bar": "Smith bar", "usable_storage": "Usable storage", "mounting": "Mounting",
    "shaft": "Shaft", "insertion": "Insertion", "stack": "Stack", "drive": "Drive",
    "socket_opening": "Socket opening",
}
INTERFACES = {
    "rack_mount": "Rack mount", "shelf_mount": "Shelf mount",
    "plate_storage": "Plate storage", "selector_pin": "Selector pin",
    "socket_drive": "Socket drive", "barbell_receiver": "Barbell receiver",
}
ATTRIBUTES = {
    "uprightSize": "upright size", "holeDiameter": "mating hole / bore diameter",
    "holeSpacing": "hole spacing", "requiredDepth": "required depth",
    "mountingSpan": "mounting span", "shaftDiameter": "shaft diameter",
    "insertionLength": "insertion length", "driveSize": "drive size",
    "openingSize": "opening size", "barbellDiameter": "barbell diameter",
}
OPERATORS = {"eq": "equal to", "min": "minimum", "max": "maximum", "listed": "listed"}
OPTION_LABEL = re.compile(
    r"\b(colou?r(?:s| options| choices)?|sizes?|size options|size choices|finish|coating)\s*:\s*",
    re.I,
)
SCOPE_PATTERNS = {
    "overall": r"\boverall\b", "product": r"\b(?:product|item|own)\b",
    "rack": r"\brack\b", "upright": r"\buprights?\b",
    "smith_bar": r"\bsmith(?:[\s-]+bar)?\b",
    "usable_storage": r"\b(?:usable|storage|loadable)\b",
    "mounting": r"\bmounting\b", "shaft": r"\bshaft\b",
    "insertion": r"\binsertion\b", "stack": r"\bstacks?\b",
    "drive": r"\bdrive\b", "socket_opening": r"\bsocket[\s-]+opening\b",
}
INTERFACE_PATTERNS = {
    "rack_mount": r"\b(?:rack|upright)\b", "shelf_mount": r"\bshel(?:f|ves)\b",
    "plate_storage": r"\bplate(?:s| storage)?\b", "selector_pin": r"\b(?:selector|pin|machine|mating|bore)\b",
    "socket_drive": r"\b(?:socket|drive)\b", "barbell_receiver": r"\b(?:barbell|receiver)\b",
}
ATTRIBUTE_PATTERNS = {
    "uprightSize": r"\bupright(?:s| size)?\b", "holeDiameter": r"\b(?:hole(?: diameter| size)?|bore)\b",
    "holeSpacing": r"\bhole (?:spacing|pitch)\b", "requiredDepth": r"\b(?:required|minimum|internal) depth\b",
    "mountingSpan": r"\bmounting span\b", "shaftDiameter": r"\bshaft (?:diameter|size)\b",
    "insertionLength": r"\binsertion (?:length|depth)\b", "driveSize": r"\bdrive(?: size)?\b",
    "openingSize": r"\bopening(?: size| diameter)?\b", "barbellDiameter": r"\bbarbell (?:size|diameter)\b",
}
MEASUREMENT_ALIASES = {
    "length": "dimensions.length", "width": "dimensions.width", "height": "dimensions.height",
    "depth": "dimensions.depth", "weight": "weight.own", "load_capacity": "capacity.safeLoad",
    "resistance": "resistance.stacks", "increment": "resistance.increments",
}


def registry_entries() -> list[tuple[str, str, str]]:
    """Return bounded (canonical key, human label, allowed topic) registrations."""
    entries = [
        ("sizeOptions", "Listed size choices (not package contents)", "products"),
        ("options.note", "Option notes", "products"),
        ("package.components", "Package component inclusion / exclusion", "products"),
        ("package.note", "Package notes", "products"),
    ]
    entries.extend((f"measurements.{scope}.{kind}", f"{label} {KINDS[kind]}", "products")
                   for scope, label in SCOPES.items() for kind in KINDS)
    entries.extend((f"interface.{attr}", f"Published interface {label}", "compatibility")
                   for attr, label in ATTRIBUTES.items())
    for kind, label in INTERFACES.items():
        entries.append((f"interface.{kind}", f"{label} interface statements", "compatibility"))
        entries.append((f"interface.{kind}.limitations", f"{label} limitations", "compatibility"))
        entries.extend((f"interface.{kind}.{attr}", f"{label} {name}", "compatibility")
                       for attr, name in ATTRIBUTES.items())
    return entries


def public_facts(item: dict, topics: set[str] | list[str]) -> dict | None:
    """Strictly validate first, then strip disabled topics and review metadata."""
    facts = public_catalog_facts(item)
    if facts is None or not {"products", "compatibility"}.intersection(topics):
        return None
    if "products" not in topics:
        for key in ("options", "measurements", "materials", "components", "packageNote"):
            facts.pop(key, None)
    if "compatibility" not in topics:
        facts.pop("interfaces", None)
    return facts


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def source(ref: str, key: str, locator: str, value: object, raw: object) -> dict:
    """Hash this canonical value and its actual public typed source, not its owner."""
    result = {
        "ref": ref, "field": key, "kind": "public_catalog", "locator": locator,
        "sourceId": f"{ref}#catalogFacts", "sourceHash": _hash({"schemaVersion": 1, "fact": raw}),
        "revision": "", "valueHash": _hash(value),
    }
    result["id"] = "catalog:" + _hash(result)
    return result


def typed_claims(item: dict, topics: set[str] | list[str]) -> list[dict]:
    """Yield key/value/locator/raw claims; caller overrides only matching keys."""
    facts = public_facts(item, topics)
    if not facts:
        return []
    claims = []

    def add(key: str, value: object, locator: str, raw: object) -> None:
        if value not in ("", [], {}):
            claims.append({"key": key, "value": value, "locator": f"catalogFacts.{locator}", "raw": raw})

    options = facts.get("options", {})
    for key, field in (("colourOptions", "colors"), ("colour.availableOptions", "colors"),
                       ("sizeOptions", "sizes"), ("finish", "finish"), ("options.note", "note")):
        add(key, options.get(field, ""), f"options.{field}", options.get(field, ""))
    for index, row in enumerate(facts.get("measurements", [])):
        qualifier = "" if row["qualifier"] == "exact" else row["qualifier"] + " "
        value = f"{qualifier}{row['amount']} {row['unit']}"
        if row["note"]:
            value += f" ({row['note']})"
        add(f"measurements.{row['scope']}.{row['kind']}", value, f"measurements.{index}", row)
        if row["scope"] in {"overall", "product"} and row["kind"] in MEASUREMENT_ALIASES:
            add(MEASUREMENT_ALIASES[row["kind"]], value, f"measurements.{index}", row)
        elif row["scope"] == "stack" and row["kind"] in {"resistance", "increment"}:
            add(MEASUREMENT_ALIASES[row["kind"]], value, f"measurements.{index}", row)
    materials = defaultdict(list)
    for row in facts.get("materials", []):
        materials[row["component"]].append(row)
    for component, rows in materials.items():
        for row in rows:
            add("material.parts", {component: row["value"]}, f"materials.{component}", row)
    for kind in INTERFACES:
        rows = [(index, row) for index, row in enumerate(facts.get("interfaces", [])) if row["kind"] == kind]
        grouped = defaultdict(list)
        for index, row in rows:
            prefix = f"Statement {index + 1}: {row['role']}"
            pieces = []
            for constraint in row["constraints"]:
                detail = f"{prefix} {ATTRIBUTES[constraint['attribute']]} {OPERATORS[constraint['operator']]} {constraint['value']}"
                if constraint["unit"]:
                    detail += " " + constraint["unit"]
                if row["limitations"]:
                    detail += f"; limitations: {row['limitations']}"
                grouped[constraint["attribute"]].append((detail, row))
                pieces.append(detail)
            if row["limitations"]:
                grouped["limitations"].append((f"{prefix}; limitations: {row['limitations']}", row))
            grouped[""].append(("; ".join(pieces) or prefix + (
                f"; limitations: {row['limitations']}" if row["limitations"] else ""), row))
        for attribute, values in grouped.items():
            key = f"interface.{kind}" + (f".{attribute}" if attribute else "")
            add(key, [value for value, _ in values], f"interfaces.{kind}.{attribute or 'statements'}",
                [row for _, row in values])
    for attribute in ATTRIBUTES:
        entries = [entry for entry in claims if entry["key"].startswith("interface.")
                   and entry["key"].endswith("." + attribute)]
        add(f"interface.{attribute}", [
            f"{INTERFACES[entry['key'].split('.')[1]]}: {value}"
            for entry in entries for value in entry["value"]
        ], f"interfaces.{attribute}", [entry["raw"] for entry in entries])
    components = facts.get("components", [])
    add("package.components", [
        f"{row['name']}: {row['status']}" + (
            f" (quantity {row['quantity']})" if row["quantity"] is not None else "")
        for row in components
    ], "components", components)
    add("package.note", facts.get("packageNote", ""), "packageNote", facts.get("packageNote", ""))
    return claims


def legacy_options(value: object, default: str = "colourOptions") -> list[tuple[str, object]]:
    """Reclassify explicit labels; do not mutate data or turn dimensions into colours."""
    if isinstance(value, list):
        grouped = defaultdict(list)
        for entry in value:
            for key, content in legacy_options(entry, default):
                grouped[key].extend(content if isinstance(content, list) else [content])
        return [(key, values) for key, values in grouped.items()]
    if not isinstance(value, str):
        return [(default, value)]
    matches = list(OPTION_LABEL.finditer(value))
    if matches:
        result = []
        if value[:matches[0].start()].strip(" ;,\n"):
            result.extend(legacy_options(value[:matches[0].start()], default))
        for index, match in enumerate(matches):
            label = match[1].casefold()
            key = ("sizeOptions" if label.startswith("size") else "finish" if label in {"finish", "coating"}
                   else "colour.availableOptions" if default == "colour.availableOptions" else "colourOptions")
            end = matches[index + 1].start() if index + 1 < len(matches) else len(value)
            content = value[match.end():end].strip(" ;,\n.")
            if content:
                result.extend(legacy_options(content, key))
        return result
    if default in {"colourOptions", "colour.availableOptions"} and re.search(
        r"\d\s*(?:mm|cm|inches?|inch|kg|lb|[\"″])\b|\bsize(?:s| options| choices)?\b", value, re.I,
    ):
        # A dimensional value establishes size information, not a known colour.
        return [("sizeOptions", value)]
    return [(default, value)]


def legacy_text(text: str) -> tuple[str, list[tuple[str, object]]]:
    """Pull explicitly scoped measurements out before unscoped legacy extraction."""
    clean, claims = [], []
    for sentence in re.split(r"[;\n]+|(?<=[.!?])\s+(?=[A-Z])", text):
        label = re.match(r"\s*([^:=]{1,100})\s*[:=]\s*(.+)", sentence)
        if not label:
            clean.append(sentence)
            continue
        title, value = label.groups()
        option = OPTION_LABEL.match(sentence.strip())
        if option:
            key = "sizeOptions" if option[1].lower().startswith("size") else "finish" if option[1].lower() in {"finish", "coating"} else "colourOptions"
            claims.extend(legacy_options(sentence.strip(), key))
            continue
        kinds = [kind for kind in KINDS if re.search(
            rf"\b{re.escape(kind.replace('_', ' '))}\b", title, re.I)]
        scopes = [scope for scope, pattern in SCOPE_PATTERNS.items() if re.search(pattern, title, re.I)]
        if len(kinds) == 1 and scopes:
            scope = next((scope for scope in scopes if scope not in {"product", "overall", "rack"}), scopes[0])
            # Existing labelled own-weight and stack parsers carry subject and
            # negation guards. Keep their canonical claims and provenance intact.
            if ((kinds[0] == "weight" and scope in {"overall", "product", "stack"})
                    or (scope == "stack" and kinds[0] in {"resistance", "increment"})):
                clean.append(sentence)
            else:
                claims.append((f"measurements.{scope}.{kinds[0]}", value))
        else:
            clean.append(sentence)
    return "\n".join(clean), claims


def requested_fields(question: str, existing: list[str]) -> list[str]:
    """Refine unscoped legacy requests and retain explicit missing-scope questions."""
    fields = list(existing)
    if re.search(r"\bsizes?\b|\bsize (?:options|choices)\b", question, re.I):
        if not re.search(r"\b(?:upright|post|hole|pin|drive|opening|barbell)\b", question, re.I):
            fields.append("sizeOptions")
            fields = [key for key in fields if key != "dimensions" or re.search(r"\bdimensions?\b", question, re.I)]
    if re.search(r"\b(?:options? notes?|choices? notes?)\b", question, re.I):
        fields.append("options.note")
    if re.search(r"\b(?:included|excluded|includes?|components?|come[s]? with|what comes|package|box contents|how many|quantity)\b", question, re.I):
        fields.extend(("package.components", "package.note"))
    for kind in KINDS:
        pattern = r"\b" + ("(?:capacity|load rating|safe load)" if kind == "load_capacity" else
                           "(?:weighs?|weight|mass)" if kind == "weight" else
                           "increments?" if kind == "increment" else re.escape(kind)) + r"\b"
        scoped, unscoped = [], False
        for clause in re.split(r"[?;,]|\band\b|\bplus\b", question, flags=re.I):
            if not re.search(pattern, clause, re.I):
                continue
            if kind == "weight" and re.search(r"\b(?:capacity|load rating|safe load|increments?)\b", clause, re.I):
                continue
            if kind == "weight" and re.search(r"\bstacks?\b", clause, re.I) and not re.search(r"\b(?:own|physical) weight\b", clause, re.I):
                continue
            if kind == "diameter" and re.search(r"\b(?:holes?|bore)\b", clause, re.I):
                continue
            scopes = [scope for scope, scope_pattern in SCOPE_PATTERNS.items() if re.search(scope_pattern, clause, re.I)]
            specific = [scope for scope in scopes if scope not in {"product", "overall"}]
            scoped.extend(specific or scopes)
            unscoped |= not scopes
        if scoped:
            if kind == "weight" and set(scoped) <= {"overall", "product"}:
                continue
            if kind in {"resistance", "increment"} and set(scoped) == {"stack"}:
                continue
            if not unscoped:
                fields = [key for key in fields if key != MEASUREMENT_ALIASES.get(kind) and key != "dimensions"]
            fields.extend(f"measurements.{scope}.{kind}" for scope in scoped)
            if kind in {"height", "width", "length", "depth"} and "upright" in scoped:
                fields = [key for key in fields if key != "compat.uprightSize"]
        elif kind == "diameter" and re.search(pattern, question, re.I) and not re.search(
            r"\b(?:hole|bore|opening|shaft|barbell)\b", question, re.I,
        ):
            fields.append("measurements.product.diameter")
    if re.search(r"\bpin (?:diameter|size)\b", question, re.I):
        fields = [key for key in fields if key not in {"compat.pinDiameter", "compat.pinDimensions", "measurements.product.diameter"}]
        fields.append("measurements.shaft.diameter")
    interface_kinds = [kind for kind, pattern in INTERFACE_PATTERNS.items() if re.search(pattern, question, re.I)]
    attrs = [attr for attr, pattern in ATTRIBUTE_PATTERNS.items() if re.search(pattern, question, re.I)]
    if ("uprightSize" in attrs and not re.search(r"\buprights?\s+size\b", question, re.I)
            and (len(attrs) > 1 or re.search(r"\b(?:width|height|length|depth)\b", question, re.I))):
        attrs.remove("uprightSize")
    if "holeSpacing" in attrs and not re.search(r"\bdiameter\b", question, re.I):
        attrs = [attr for attr in attrs if attr != "holeDiameter"]
    interface_question = bool(attrs) or bool(re.search(r"\b(?:interfaces?|requirements?|limitations?)\b", question, re.I))
    if attrs and not interface_kinds and (re.search(r"\b(?:requir\w*|accepts?|provides?)\b", question, re.I)
                                         or not any(key.startswith("measurements.") for key in fields)):
        fields.extend(f"interface.{attr}" for attr in attrs)
        replaced = {"dimensions", *(f"compat.{attr}" for attr in attrs)}
        if "insertionLength" in attrs:
            replaced.update(("dimensions.length", "measurements.insertion.length"))
        if "requiredDepth" in attrs:
            replaced.add("dimensions.depth")
        fields = [key for key in fields if key not in replaced]
    if interface_question and interface_kinds:
        for kind in interface_kinds:
            local_attrs = attrs
            if len(interface_kinds) > 1:
                clauses = [clause for clause in re.split(r"[?;,]|\band\b", question, flags=re.I)
                           if re.search(INTERFACE_PATTERNS[kind], clause, re.I)]
                local_attrs = [attr for attr in attrs if any(re.search(ATTRIBUTE_PATTERNS[attr], clause, re.I)
                                                            for clause in clauses)]
            fields.extend(f"interface.{kind}.{attr}" for attr in local_attrs)
            if not local_attrs:
                fields.append(f"interface.{kind}")
        fields = [key for key in fields if key not in {f"compat.{attr}" for attr in attrs}]
        # Rack-shaped legacy requests remain eligible as fallbacks, while socket,
        # selector-pin and receiver requirements never masquerade as rack holes.
        if set(interface_kinds) - {"rack_mount", "shelf_mount"}:
            fields = [key for key in fields if not key.startswith("compat.") and key != "dimensions"]
    # Without item evidence, existing questions retain existing field identities,
    # including their unknown safeguards. expand_fields upgrades known reviewed
    # equivalents later; genuinely new shaft/socket/bore scopes remain distinct.
    for key in existing:
        if not key.startswith("compat."):
            continue
        attr = key.split(".", 1)[1]
        equivalent = {f"interface.{attr}", f"interface.rack_mount.{attr}", f"interface.shelf_mount.{attr}"}
        if not (set(interface_kinds) - {"rack_mount", "shelf_mount"}) and equivalent.intersection(fields):
            fields = [field for field in fields if field not in equivalent]
            fields.append(key)
        if attr in {"pinDiameter", "pinDimensions"} and not re.search(r"\bshaft\b", question, re.I):
            fields = [field for field in fields if field not in {"measurements.shaft.diameter", "measurements.product.diameter"}]
            fields.append(key)
    return list(dict.fromkeys(fields))


def expand_fields(keys: list[str], facts: dict[str, dict]) -> list[str]:
    """Select known scoped facts without replacing a specifically requested scope."""
    result = []
    known = lambda key: facts[key]["status"] in {"answered", "conflicted", "not_applicable"}
    for key in keys:
        if key.startswith("interface.") and key.count(".") == 1 and not known(key):
            legacy = f"compat.{key.split('.')[1]}"
            if legacy in facts and known(legacy):
                result.append(legacy)
                continue
        if key.startswith("measurements.") and not known(key):
            _, scope, kind = key.split(".")
            alias = MEASUREMENT_ALIASES.get(kind)
            if (scope in {"overall", "product"} and alias and known(alias)
                    and not any(source["locator"].startswith("catalogFacts.") for source in facts[alias]["sources"])):
                result.append(alias)
                continue
            if scope == "shaft" and kind == "diameter" and known("compat.pinDiameter"):
                result.append("compat.pinDiameter")
                continue
        if key.startswith(("interface.rack_mount.", "interface.shelf_mount.")) and not known(key):
            attr = key.rsplit(".", 1)[1]
            legacy = f"compat.{attr}"
            if legacy in facts and known(legacy):
                result.append(legacy)
                continue
        related = []
        if key in MEASUREMENT_ALIASES.values():
            kind = next(kind for kind, alias in MEASUREMENT_ALIASES.items() if alias == key)
            scopes = ("overall", "product") if key == "weight.own" else SCOPES
            related = [f"measurements.{scope}.{kind}" for scope in scopes if known(f"measurements.{scope}.{kind}")]
        elif key == "dimensions":
            related = [field for field in facts if field.startswith("measurements.")
                       and field.rsplit(".", 1)[-1] in {"length", "width", "height", "depth", "diameter"} and known(field)]
        elif key in {"colourOptions", "colour.availableOptions"} and not known(key):
            related = [field for field in ("sizeOptions", "finish", "options.note") if known(field)]
        elif key == "material" and known("material.parts"):
            related = ["material.parts"]
        elif key in {"included", "components"} and known("package.components"):
            related = ["package.components"]
        elif key.startswith("compat."):
            attr = key.split(".", 1)[1]
            related = [field for field in facts if field.startswith(("interface.rack_mount.", "interface.shelf_mount."))
                       and field.endswith("." + attr) and known(field)]
            if key == "compat.pinDiameter" and known("measurements.shaft.diameter"):
                related = ["measurements.shaft.diameter"]
        if related:
            # Preserve unknown colours alongside the known, differently-typed sizes.
            if key in {"colourOptions", "colour.availableOptions"}:
                result.append(key)
            elif key not in {"included", "components", "compat.pinDiameter"} and known(key) and not any(source["locator"].startswith("catalogFacts.")
                                        for source in facts[key]["sources"]):
                result.append(key)
            result.extend(related)
        else:
            result.append(key)
    # Optional contextual fields are useful when populated, not mandatory unknowns.
    result = [key for key in result if key not in {"package.components", "package.note", "options.note"}
              or known(key) or facts[key]["status"] == "scope_disabled"]
    if any(key in {"sizeOptions", "colourOptions", "colour.availableOptions"} for key in result) and known("options.note"):
        result.append("options.note")
    return list(dict.fromkeys(result))
