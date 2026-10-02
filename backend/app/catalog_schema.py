"""Bounded merchant-authored facts, separate from offers and verified fit claims."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import unicodedata
from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import HTTPException
from pydantic import (
    BaseModel, BeforeValidator, ConfigDict, Field, ValidationError, ValidationInfo,
    field_validator, model_validator,
)

logger = logging.getLogger(__name__)


def fact_text(value: object, *, allow_prose_whitespace: bool = False) -> object:
    if isinstance(value, str):
        if any(
            unicodedata.category(character) in ("Cc", "Cf", "Cs")
            and not (allow_prose_whitespace and character in "\r\n\t")
            for character in value
        ):
            raise ValueError("Catalog fact text must not contain control or formatting characters.")
        return value.strip()
    return value

LengthUnit = Literal["mm", "cm", "m", "in", "ft"]
MeasurementKind = Literal[
    "length", "width", "height", "depth", "diameter", "weight",
    "load_capacity", "resistance", "increment",
]
MeasurementScope = Literal[
    "overall", "product", "rack", "upright", "smith_bar", "usable_storage",
    "mounting", "shaft", "insertion", "stack", "drive", "socket_opening",
]
Revision = Annotated[str, Field(strict=True, pattern=r"^[0-9a-f]{64}$")]
Label = Annotated[str, Field(strict=True, min_length=1, max_length=300)]
OptionLabel = Annotated[str, Field(strict=True, min_length=1, max_length=100), BeforeValidator(fact_text)]
Note = Annotated[str, Field(strict=True, max_length=2000)]
Amount = Annotated[str, Field(strict=True, min_length=1, max_length=64, pattern=r"^[0-9]+(?:\.[0-9]+)?$")]


class FactsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    @field_validator("*", mode="before")
    @classmethod
    def clean_text(cls, value: object, info: ValidationInfo) -> object:
        if info.field_name == "amount":
            return value
        return fact_text(value, allow_prose_whitespace=info.field_name in ("note", "packageNote", "limitations"))


class CatalogOptions(FactsModel):
    colors: list[OptionLabel] = Field(default_factory=list, max_length=24)
    sizes: list[OptionLabel] = Field(default_factory=list, max_length=24)
    finish: str = Field(default="", max_length=300)
    note: Note = ""

    @field_validator("colors", "sizes")
    @classmethod
    def unique_options(cls, values: list[str]) -> list[str]:
        if len({value.casefold() for value in values}) != len(values):
            raise ValueError("Option labels must be unique, ignoring case and surrounding spaces.")
        return values


class CatalogMeasurement(FactsModel):
    kind: MeasurementKind
    scope: MeasurementScope
    amount: Amount
    unit: Literal["mm", "cm", "m", "in", "ft", "kg", "lb"]
    qualifier: Literal["exact", "approximate", "nominal"] = "exact"
    note: Note = ""

    @field_validator("amount")
    @classmethod
    def positive_decimal(cls, value: str) -> str:
        amount = Decimal(value)
        if not amount.is_finite() or amount <= 0:
            raise ValueError("Measurement amount must be a positive finite decimal string.")
        return value

    @model_validator(mode="after")
    def matching_unit_family(self) -> CatalogMeasurement:
        mass = self.kind in ("weight", "load_capacity", "resistance", "increment")
        if mass != (self.unit in ("kg", "lb")):
            raise ValueError("Measurement unit does not match its kind.")
        return self


class CatalogMaterial(FactsModel):
    component: Label
    value: Label


class CatalogConstraint(FactsModel):
    attribute: Literal[
        "uprightSize", "holeDiameter", "holeSpacing", "requiredDepth",
        "mountingSpan", "shaftDiameter", "insertionLength", "driveSize",
        "openingSize", "barbellDiameter",
    ]
    operator: Literal["listed", "eq", "min", "max"]
    value: Label
    unit: Literal["", "mm", "cm", "m", "in", "ft"] = ""


class CatalogInterface(FactsModel):
    kind: Literal[
        "rack_mount", "shelf_mount", "plate_storage", "selector_pin",
        "socket_drive", "barbell_receiver",
    ]
    role: Literal["provides", "requires", "accepts"]
    constraints: list[CatalogConstraint] = Field(default_factory=list, max_length=24)
    limitations: Note = ""


class CatalogComponent(FactsModel):
    name: Label
    quantity: Annotated[int, Field(strict=True, ge=1, le=1_000_000)] | None = None
    status: Literal["included", "excluded", "unknown"]


class CatalogFacts(FactsModel):
    schemaVersion: Literal[1] = 1
    reviewed: bool = False
    options: CatalogOptions = Field(default_factory=CatalogOptions)
    measurements: list[CatalogMeasurement] = Field(default_factory=list, max_length=64)
    materials: list[CatalogMaterial] = Field(default_factory=list, max_length=32)
    interfaces: list[CatalogInterface] = Field(default_factory=list, max_length=16)
    components: list[CatalogComponent] = Field(default_factory=list, max_length=64)
    packageNote: str = Field(default="", max_length=4000)

    @field_validator("schemaVersion", mode="before")
    @classmethod
    def integer_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("Schema version must be an integer.")
        return value


class CatalogSchemaPayload(BaseModel):
    schemaVersion: Literal[1, 2] = 1
    expectedRevision: Revision | None = None
    catalogFacts: CatalogFacts | None = None

    @field_validator("schemaVersion", mode="before")
    @classmethod
    def integer_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("Schema version must be an integer.")
        return value

    @model_validator(mode="before")
    @classmethod
    def server_owned_review_time(cls, value: object) -> object:
        if isinstance(value, dict) and "catalogFactsReviewedAt" in value:
            raise ValueError("Catalog facts review time is server-managed.")
        if isinstance(value, dict) and (
            value.get("schemaVersion") == 2 or value.get("expectedRevision") is not None or "catalogFacts" in value
        ):
            if set(value).difference(cls.model_fields):
                raise ValueError("Unknown catalog request fields are not allowed in schema 2.")
        return value


def catalog_revision(item: Mapping[str, object]) -> str:
    raw = json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def require_catalog_revision(
    item: Mapping[str, object], expected: str | None, *, metadata_edit: bool = False,
) -> None:
    required = item.get("schemaVersion", 1) != 1 or metadata_edit
    if (required and expected is None) or (expected is not None and expected != catalog_revision(item)):
        raise HTTPException(
            status_code=409,
            detail="This catalog item changed or requires a current revision. Reload it before saving or deleting; your edits have not been applied.",
        )


def catalog_schema_fields(request: CatalogSchemaPayload, previous: Mapping[str, object]) -> dict[str, object]:
    fields: dict[str, object] = {}
    if request.schemaVersion == 2 or request.expectedRevision is not None or "catalogFacts" in request.model_fields_set:
        fields["schemaVersion"] = 2
    if "catalogFacts" in request.model_fields_set:
        facts = request.catalogFacts.model_dump() if request.catalogFacts is not None else None
        fields["catalogFacts"] = facts
        if facts and facts["reviewed"]:
            if facts != previous.get("catalogFacts") or not previous.get("catalogFactsReviewedAt"):
                fields["catalogFactsReviewedAt"] = datetime.now(timezone.utc).isoformat()
        else:
            fields["catalogFactsReviewedAt"] = None
    elif not previous and fields.get("schemaVersion") == 2:
        fields["catalogFacts"] = None
    return fields


def public_catalog_facts(item: Mapping[str, object]) -> dict[str, object] | None:
    raw = item.get("catalogFacts")
    if not isinstance(raw, dict) or raw.get("reviewed") is not True:
        return None
    try:
        return CatalogFacts.model_validate(raw).model_dump()
    except ValidationError:
        # Unknown/private keys in restored or manually edited metadata never publish.
        logger.warning("Reviewed catalog facts failed validation and were omitted from the public projection.")
        return None


_LEGACY_COMPONENTS = frozenset(("frame", "handle", "grip", "padding", "upholstery", "pin", "bolt", "roller", "pad"))
_LEGACY_COMPATIBILITY = frozenset((
    "uprightSize", "holeDiameter", "holeSpacing", "pinDiameter", "pinLength",
    "pinDimensions", "models", "limitations", "requiredDepth",
))
_LEGACY_NESTED_FIELDS = {
    "dimensions": frozenset(("length", "width", "height", "depth")),
    "capacity": frozenset(("safeLoad",)),
    "resistance": frozenset(("stacks", "increments")),
    "compatibility": _LEGACY_COMPATIBILITY,
    "compat": _LEGACY_COMPATIBILITY,
}
_LEGACY_VALUE_FIELDS = (
    "colorOptions", "ownWeight", "safeLoad", "weightStacks", "weightIncrements",
    "length", "width", "height", "depth", "includes", "components",
)


def _legacy_public_value(value: object) -> object:
    if isinstance(value, str):
        if len(value) > 16000:
            return None
        try:
            fact_text(value, allow_prose_whitespace=True)
        except ValueError:
            return None
        return value
    if type(value) is int:
        return value if value.bit_length() <= 256 else None
    if type(value) is float:
        return value if math.isfinite(value) else None
    if isinstance(value, list) and len(value) <= 64:
        if all(not isinstance(entry, (dict, list)) and _legacy_public_value(entry) is not None for entry in value):
            return list(value)
    return None


def public_legacy_catalog_fields(item: Mapping[str, object]) -> dict[str, object]:
    """Preserve pre-typed catalog fact paths without forwarding arbitrary nested data."""
    result: dict[str, object] = {}
    for key in (*_LEGACY_VALUE_FIELDS, "brand", "finish", "saleUnit", "sku", "aliases", "dimensions"):
        raw = item.get(key)
        if key in ("brand", "finish", "saleUnit", "sku") and not isinstance(raw, str):
            continue
        if key == "aliases" and (not isinstance(raw, list) or any(not isinstance(alias, str) for alias in raw)):
            continue
        value = _legacy_public_value(raw)
        if value is not None:
            result[key] = value
    for key, allowed in _LEGACY_NESTED_FIELDS.items():
        raw = item.get(key)
        if not isinstance(raw, dict):
            continue
        values = {
            field: value for field, raw_value in raw.items()
            if field in allowed and (value := _legacy_public_value(raw_value)) is not None
        }
        if values:
            result[key] = values
    for key in ("materialParts", "colourParts", "colorParts"):
        raw = item.get(key)
        if not isinstance(raw, dict):
            continue
        values = {
            field: value for field, raw_value in raw.items()
            if isinstance(field, str) and field.casefold().rstrip("s") in _LEGACY_COMPONENTS
            and (value := _legacy_public_value(raw_value)) is not None
        }
        if values:
            result[key] = values
    return result
