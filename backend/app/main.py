from __future__ import annotations

import json
import logging
import math
import os
import re
import secrets
import smtplib
import ssl
from contextlib import contextmanager
from collections.abc import Mapping
from datetime import date, datetime, timezone
from decimal import Decimal
from email.message import EmailMessage
from pathlib import Path
from threading import Lock
from tempfile import TemporaryFile
from collections.abc import Iterator
from typing import Annotated, Literal
from uuid import uuid4
from urllib.parse import unquote, urlsplit

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, Response, UploadFile
from fastapi import Path as PathParameter
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from pydantic import AfterValidator, BaseModel, EmailStr, Field, TypeAdapter, field_validator, model_validator

from app.media import VIDEO_FORMATS, upload_video, video_response
from app.location import MarketContext, resolve_market
from app.catalog_backup import BackupError, create_archive, validate_engineering_image
from app import analytics

APP_PATH = Path(__file__).resolve().parent
CONFIGURED_DATA_DIRECTORY = os.getenv("STYL_DATA_DIR")
DATA_DIRECTORY = Path(CONFIGURED_DATA_DIRECTORY) if CONFIGURED_DATA_DIRECTORY else APP_PATH / "data"
DATA_PATH = DATA_DIRECTORY / "products.json"
ACCESSORIES_PATH = DATA_DIRECTORY / "accessories.json"
HERO_PATH = DATA_DIRECTORY / "hero.json"
INQUIRIES_PATH = DATA_DIRECTORY / "inquiries"
INQUIRY_RECIPIENT = "styl@stylfitness.com"
INQUIRY_RECIPIENTS_ADAPTER = TypeAdapter(list[EmailStr])
logger = logging.getLogger(__name__)
UPLOAD_PATH = DATA_DIRECTORY / "uploads" if CONFIGURED_DATA_DIRECTORY else APP_PATH / "uploads"
ADMIN_TOKEN = os.getenv("STYL_ADMIN_TOKEN", "")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "STYL_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]
CATALOG_LOCK = Lock()
ACCESSORIES_LOCK = CATALOG_LOCK
HERO_LOCK = CATALOG_LOCK
BACKUP_LOCK = Lock()
PUBLIC_IMAGE_PATH = APP_PATH.parents[1] / "frontend" / "public" / "images"
# Accessory IDs start above this so they don't collide with product IDs in the shared cart.
ACCESSORY_ID_OFFSET = 1000
MAX_IMAGE_SIZE = 8 * 1024 * 1024
IMAGE_EXTENSIONS = {
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
CATALOG_CATEGORIES = (
    "Strength", "Racks", "Multi trainers", "Benches", "Cardio", "Recovery",
    "Accessories", "General", "Bar", "Handle", "Strap", "Upper frame",
    "Hardware", "Storage", "Performance",
)
CATEGORY_ALIASES = {"bench": "Benches"}

UPLOAD_PATH.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="STYL API",
    version="0.1.0",
    description="Lightweight API for catalog and inquiry operations.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.exception_handler(RequestValidationError)
async def validation_error_response(_request: Request, error: RequestValidationError) -> JSONResponse:
    # JSON numeric overflow must remain a validation error, not fail error-response serialization.
    details = jsonable_encoder(error.errors(), custom_encoder={
        float: lambda value: value if math.isfinite(value) else str(value),
    })
    return JSONResponse(status_code=422, content={"detail": details})


class InquiryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=100)
    company: str | None = Field(default=None, max_length=300)
    message: str = Field(min_length=1, max_length=10000)
    source: Literal["website", "inquiry", "retail"] = "website"
    analytics: object = Field(default=None, exclude=True)


class CatalogOrderRequest(BaseModel):
    model_config = {"extra": "forbid"}
    ids: list[Annotated[int, Field(strict=True, ge=1)]] = Field(max_length=10000)
    expectedIds: list[Annotated[int, Field(strict=True, ge=1)]] = Field(max_length=10000)

    @model_validator(mode="after")
    def unique_order_ids(self) -> CatalogOrderRequest:
        if len(set(self.ids)) != len(self.ids) or len(set(self.expectedIds)) != len(self.expectedIds):
            raise ValueError("Listing order must not contain duplicate IDs.")
        return self


class CompatibilityPayload(BaseModel):
    uprightSize: str = Field(default="", max_length=300)
    holeDiameter: str = Field(default="", max_length=300)
    holeSpacing: str = Field(default="", max_length=300)
    models: str = Field(default="", max_length=1000)
    limitations: str = Field(default="", max_length=2000)


class ProvenancePayload(BaseModel):
    sourceType: str = Field(default="", max_length=200)
    marketplaceUrl: str = Field(default="", max_length=2000)
    listingId: str = Field(default="", max_length=300)
    capturedDate: str = Field(default="", max_length=10)
    notes: str = Field(default="", max_length=10000)

    @field_validator("*")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("marketplaceUrl")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if value:
            parsed = urlsplit(value)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError("Source URL must be an HTTP or HTTPS URL.")
        return value

    @field_validator("capturedDate")
    @classmethod
    def validate_date(cls, value: str) -> str:
        if value and date.fromisoformat(value).isoformat() != value:
            raise ValueError("Use a valid date in YYYY-MM-DD format.")
        return value


def validate_price_range(value: Decimal) -> Decimal:
    numeric = float(value)
    if not math.isfinite(numeric) or Decimal(str(numeric)) != value:
        raise ValueError("Price is too large to preserve its decimal value.")
    return value


Price = Annotated[Decimal, Field(ge=0, decimal_places=2, allow_inf_nan=False), AfterValidator(validate_price_range)]


class MarketPricesPayload(BaseModel):
    CAD: Price | None = None
    USD: Price | None = None


class MarketMsrpsPayload(MarketPricesPayload):
    model_config = {"extra": "forbid"}


class CatalogIdentityPayload(BaseModel):
    name: str = Field(max_length=200)
    category: str = Field(max_length=300)
    price: Price | None = None
    prices: MarketPricesPayload | None = None
    msrps: MarketMsrpsPayload | None = None

    @model_validator(mode="after")
    def validate_prices_object(self) -> CatalogIdentityPayload:
        if "prices" in self.model_fields_set and self.prices is None:
            raise ValueError("Prices must be an object with CAD and/or USD values; use null for an unavailable market.")
        if "msrps" in self.model_fields_set and self.msrps is None:
            raise ValueError("MSRPs must be an object with CAD and/or USD values; use null to clear one market.")
        return self

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name is required.")
        return value


class CatalogDetailsPayload(BaseModel):
    photos: list[str] | None = Field(default=None, max_length=12)
    compatibility: CompatibilityPayload | None = None
    provenance: ProvenancePayload | None = None


class ProductSpecificationsPayload(BaseModel):
    modelSku: str = Field(default="", max_length=200)
    dimensions: str = Field(default="", max_length=500)
    material: str = Field(default="", max_length=500)
    weight: str = Field(default="", max_length=500)
    included: str = Field(default="", max_length=4000)
    colourOptions: str = Field(default="", max_length=1000)
    warranty: str = Field(default="", max_length=4000)
    stockStatus: Literal["", "In stock", "Out of stock", "Preorder", "Made to order"] = ""
    publicationStatus: Literal["", "draft", "published"] = "draft"


class ProductPayload(CatalogDetailsPayload, ProductSpecificationsPayload, CatalogIdentityPayload):
    id: int | None = None
    slug: str | None = None
    currency: Literal["CAD", "USD"] = "CAD"
    shortDescription: str = ""
    description: str = ""
    featured: bool = False
    image: str | None = None
    features: list[str] = Field(default_factory=list)


class AccessorySpecificationsPayload(BaseModel):
    shortDescription: str = Field(default="", max_length=1000)
    description: str = Field(default="", max_length=10000)
    features: list[str] = Field(default_factory=list, max_length=50)
    included: str = Field(default="", max_length=4000)
    sellingUnit: Literal["", "Each", "Pair", "Set"] = ""
    packageQuantity: int | None = Field(default=None, ge=1, strict=True)
    colourOptions: str = Field(default="", max_length=1000)
    publicationStatus: Literal["", "draft", "published"] = "draft"

    @field_validator("features")
    @classmethod
    def validate_features(cls, values: list[str]) -> list[str]:
        if any(len(value) > 1000 for value in values):
            raise ValueError("Each feature must be 1000 characters or fewer.")
        return [value.strip() for value in values if value.strip()]


class AccessoryPayload(CatalogDetailsPayload, AccessorySpecificationsPayload, CatalogIdentityPayload):
    dimensions: str = ""
    material: str = ""
    weight: str = ""
    currency: Literal["CAD", "USD"] = "CAD"
    notes: str = ""
    image: str | None = None


class EngineeringCardPayload(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(max_length=2000)
    image: str = Field(min_length=1, max_length=500)

    @field_validator("image")
    @classmethod
    def validate_image(cls, value: str) -> str:
        return validate_engineering_image(value)


class EngineeringPayload(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}
    heading: str = Field(min_length=1, max_length=120)
    intro: str = Field(max_length=1000)
    items: list[EngineeringCardPayload] = Field(min_length=4, max_length=4)


DEFAULT_ENGINEERING = EngineeringPayload(
    heading="Explore our engineering details",
    intro="Our mark, engineered into every piece.",
    items=[
        EngineeringCardPayload(
            title="Signature shield",
            description="Laser-etched into brushed stainless steel on every frame upright.",
            image="/images/brand/logo-plate.jpg",
        ),
        EngineeringCardPayload(
            title="J-hook",
            description="Rubber-lined steel hooks that protect the bar and carry the wordmark.",
            image="/images/brand/j-hook.jpg",
        ),
        EngineeringCardPayload(
            title="Cable swivel plate",
            description="Machined plate and 360° swivel for smooth, tangle-free cable work.",
            image="/images/brand/cable-swivel.jpg",
        ),
        EngineeringCardPayload(
            title="Frame badge",
            description="Brushed steel badge finishing the top crossmember of the multi trainer.",
            image="/images/brand/frame-badge.jpg",
        ),
    ],
)


class HeroPayload(BaseModel):
    model_config = {"extra": "forbid"}
    tag: str = Field(default="", max_length=40)
    number: str = Field(default="", max_length=10)
    eyebrow: str = Field(default="", max_length=60)
    title: str = Field(default="", max_length=80)
    image: str = Field(default="", max_length=500)
    engineering: EngineeringPayload = Field(default_factory=lambda: DEFAULT_ENGINEERING.model_copy(deep=True))


DEFAULT_HERO = HeroPayload(
    tag="Signature", number="01", eyebrow="Pro Elite", title="Series X",
    image="/images/brand/frame-badge.jpg",
)


def require_admin(authorization: str | None = Header(default=None)) -> None:
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="Admin access is not configured.")

    expected = f"Bearer {ADMIN_TOKEN}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Invalid admin token.")


@contextmanager
def locked_catalog() -> Iterator[list[dict[str, object]]]:
    with CATALOG_LOCK:
        products = load_products()
        yield products


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "product"


def seed_products() -> list[dict[str, object]]:
    products = [
        {
            "id": 1,
            "slug": "pro-elite-series",
            "name": "Pro Elite Series",
            "category": "Strength",
            "price": 2499,
            "currency": "USD",
            "shortDescription": "Premium commercial-grade strength training setup.",
            "description": "A premium strength platform built for controlled, stable, and high-performance training in home and studio spaces.",
            "featured": True,
            "image": "/images/pro-elite.svg",
            "features": [
                "Precision-balanced frame",
                "Industrial-grade resistance system",
                "Low-noise operation",
            ],
        },
        {
            "id": 2,
            "slug": "studio-row-compact",
            "name": "Studio Row Compact",
            "category": "Cardio",
            "price": 1899,
            "currency": "USD",
            "shortDescription": "Compact, quiet, and engineered for modern home studios.",
            "description": "A compact cardio machine designed for clean form, low interference, and daily usability in premium residential spaces.",
            "featured": True,
            "image": "/images/studio-row.svg",
            "features": [
                "Compact footprint",
                "Low-impact cardio training",
                "Smooth full-body motion",
            ],
        },
        {
            "id": 3,
            "slug": "summit-core-rig",
            "name": "Summit Core Rig",
            "category": "Performance",
            "price": 3299,
            "currency": "USD",
            "shortDescription": "High-stability architecture built for performance and durability.",
            "description": "A premium multi-use training rig built for athletes, professionals, and serious home training environments.",
            "featured": False,
            "image": "/images/summit-core.svg",
            "features": [
                "Heavy-duty stability frame",
                "Modular training configuration",
                "Designed for long-term reliability",
            ],
        },
    ]

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(products, indent=2), encoding="utf-8")
    return products


def load_products() -> list[dict[str, object]]:
    try:
        raw = DATA_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return seed_products()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return seed_products()

    if isinstance(data, list):
        return data

    return seed_products()


def save_products(products: list[dict[str, object]]) -> None:
    write_json_list(DATA_PATH, products)


def write_json_list(path: Path, items: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".tmp")
    try:
        temporary_path.write_text(json.dumps(items, indent=2), encoding="utf-8")
        temporary_path.replace(path)
    except OSError:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def seed_accessory(
    accessory_id: int,
    name: str,
    category: str,
    dimensions: str,
    material: str,
    weight: str,
    price: float,
    notes: str,
    image: str,
) -> dict[str, object]:
    return {
        "id": accessory_id,
        "name": name,
        "category": category,
        "dimensions": dimensions,
        "material": material,
        "weight": weight,
        "price": price,
        "currency": "USD",
        "notes": notes,
        "image": f"/images/accessories/{image}.svg",
    }


def seed_accessories() -> list[dict[str, object]]:
    # Placeholder catalog; replace with confirmed supplier specs and pricing via the admin page.
    accessories = [
        seed_accessory(1001, "Lat Pulldown Bar", "Bar", "120 x 4 x 25 cm", "Chrome-plated steel, knurled grips", "4.5 kg", 89, "Wide-grip pulldowns and overhead cable work.", "lat-pulldown-bar"),
        seed_accessory(1002, "Straight Bar", "Bar", "50 x 3 x 12 cm", "Chrome-plated steel, revolving sleeve", "2.0 kg", 59, "Triceps pushdowns, curls, and upright rows.", "straight-bar"),
        seed_accessory(1003, "EZ Curl Bar", "Bar", "60 x 3 x 14 cm", "Chrome-plated steel, angled knurled grips", "2.4 kg", 69, "Wrist-friendly curls and extensions.", "ez-curl-bar"),
        seed_accessory(1004, "Triceps Rope", "Handle", "70 cm length, 3 cm diameter", "Braided nylon, rubber end caps, steel eyelet", "0.8 kg", 39, "Pushdowns, face pulls, and cable crunches.", "triceps-rope"),
        seed_accessory(1005, "V-Bar / Close-Grip Row Handle", "Handle", "28 x 18 x 12 cm", "Solid steel, rubber-coated grips", "1.6 kg", 45, "Seated rows and close-grip pulldowns.", "v-bar"),
        seed_accessory(1006, "Single D-Handle (Pair)", "Handle", "18 x 14 x 4 cm each", "Steel frame, anti-slip rubber grip", "0.5 kg each", 35, "Unilateral presses, flys, and rows.", "d-handle"),
        seed_accessory(1007, "Ankle Strap (Pair)", "Strap", "30 x 9 cm each", "Padded neoprene, hook-and-loop, steel D-ring", "0.2 kg each", 29, "Glute kickbacks, hip abduction, leg raises.", "ankle-strap"),
        seed_accessory(1008, "Nylon Stirrup Handle (Pair)", "Strap", "20 x 12 cm each", "Reinforced nylon webbing, ABS grip tube", "0.15 kg each", 25, "Lightweight option for flys and rotations.", "stirrup-handle"),
        seed_accessory(1009, "Pull-up / Chin-up Handles", "Upper frame", "35 x 12 x 10 cm each", "Powder-coated steel, foam grips", "1.2 kg each", 79, "Neutral-grip pull-ups on the top crossmember.", "pullup-handles"),
        seed_accessory(1010, "Carabiner & Chain Extender Kit", "Hardware", "Carabiner 10 cm, chain 40 cm", "Zinc-plated alloy steel", "0.4 kg", 19, "Quick attachment swaps and cable length tuning.", "carabiner-chain"),
        seed_accessory(1011, "Adjustable Utility Bench", "Bench", "130 x 60 x 45 cm", "Steel frame, high-density foam, PU leather", "28 kg", 399, "Flat, incline, and decline positions for cable presses.", "utility-bench"),
        seed_accessory(1012, "Accessory Storage Rack", "Storage", "60 x 20 x 90 cm", "Powder-coated steel, rubber hook sleeves", "6 kg", 129, "Mounts to the frame to organize attachments.", "storage-rack"),
    ]
    write_json_list(ACCESSORIES_PATH, accessories)
    return accessories


def load_accessories() -> list[dict[str, object]]:
    try:
        data = json.loads(ACCESSORIES_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return seed_accessories()

    return data if isinstance(data, list) else seed_accessories()


def catalog_categories() -> list[str]:
    categories = {category.casefold(): category for category in CATALOG_CATEGORIES}
    for item in [*load_products(), *load_accessories()]:
        category = normalize_category(str(item.get("category") or ""))
        if category:
            categories.setdefault(category.casefold(), category)
    return sorted(categories.values(), key=str.casefold)


def canonical_category(value: str) -> str:
    normalized = normalize_category(value)
    for category in catalog_categories():
        if category.casefold() == normalized.casefold():
            return category
    raise HTTPException(status_code=422, detail="Choose an existing catalog category.")


def normalize_category(value: str) -> str:
    normalized = " ".join(value.split())
    return CATEGORY_ALIASES.get(normalized.casefold(), normalized)


def stored_prices(item: dict[str, object]) -> dict[str, float | None]:
    result: dict[str, float | None] = {"CAD": None, "USD": None}
    existing = item.get("prices")
    if isinstance(existing, dict):
        for currency in result:
            value = existing.get(currency)
            if value is not None:
                result[currency] = float(value)
    elif item.get("price") is not None:
        currency = str(item.get("currency") or "USD")
        if currency in result:
            result[currency] = float(item["price"])
    return result


def catalog_prices(request: ProductPayload | AccessoryPayload, previous: dict[str, object]) -> dict[str, object]:
    prices = stored_prices(previous)
    currency = request.currency if "currency" in request.model_fields_set else str(previous.get("currency") or request.currency)
    if request.prices is not None:
        for code in request.prices.model_fields_set:
            value = getattr(request.prices, code)
            prices[code] = float(value) if value is not None else None
    elif "price" in request.model_fields_set:
        prices[currency] = float(request.price) if request.price is not None else None
    return {"prices": prices, "currency": currency, "price": prices.get(currency)}


def stored_msrps(item: dict[str, object]) -> dict[str, float | None]:
    existing = item.get("msrps")
    return {
        currency: float(existing[currency]) if isinstance(existing, dict) and existing.get(currency) is not None else None
        for currency in ("CAD", "USD")
    }


def catalog_msrps(request: ProductPayload | AccessoryPayload, previous: dict[str, object]) -> dict[str, object]:
    if request.msrps is None:
        return {"msrps": previous["msrps"]} if "msrps" in previous else {}
    msrps = stored_msrps(previous)
    for currency in request.msrps.model_fields_set:
        value = getattr(request.msrps, currency)
        msrps[currency] = float(value) if value is not None else None
    return {"msrps": msrps}


def admin_catalog_item(item: dict[str, object]) -> dict[str, object]:
    prices = stored_prices(item)
    return {
        **item, "prices": prices, "msrps": stored_msrps(item),
        "category": normalize_category(str(item.get("category") or "")),
        "publicationStatus": item.get("publicationStatus") or "published",
        "missingPriceMarkets": [code for code, amount in prices.items() if amount is None],
    }


def public_catalog_item(item: dict[str, object], market: MarketContext) -> dict[str, object]:
    price = stored_prices(item)[market["currency"]]
    return {
        **{key: value for key, value in item.items() if key not in ("provenance", "prices", "msrps", "missingPriceMarkets")},
        "category": normalize_category(str(item.get("category") or "")),
        "price": price, "currency": market["currency"], "msrp": stored_msrps(item)[market["currency"]],
    }


def visible_in_market(item: dict[str, object], market: MarketContext) -> bool:
    return item.get("publicationStatus") != "draft" and stored_prices(item)[market["currency"]] is not None


def request_market(request: Request, response: Response) -> MarketContext:
    response.headers["Cache-Control"] = "private, no-store"
    return resolve_market(request)


def analytics_catalog(market: Mapping[str, object]) -> list[dict[str, object]]:
    if market.get("currency") not in ("CAD", "USD"):
        raise ValueError("Invalid analytics market currency.")
    result = []
    with CATALOG_LOCK:
        for kind, path in (("product", DATA_PATH), ("accessory", ACCESSORIES_PATH)):
            records = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(records, list):
                raise ValueError("Invalid saved catalog for analytics.")
            for item in records:
                if not isinstance(item, dict):
                    raise ValueError("Invalid saved catalog for analytics.")
                if item.get("publicationStatus") == "draft":
                    continue
                prices = item.get("prices")
                price = prices.get(market["currency"]) if isinstance(prices, dict) else (
                    item.get("price") if item.get("currency", "USD") == market["currency"] else None
                )
                if price is None:
                    continue
                if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price):
                    raise ValueError("Invalid saved analytics catalog price.")
                cents = Decimal(str(price)) * 100
                if cents != cents.to_integral_value() or not 0 <= cents <= 2**53 - 1:
                    raise ValueError("Invalid saved analytics catalog price.")
                if type(item.get("id")) is not int or not 1 <= item["id"] <= 2**53 - 1 or not isinstance(item.get("name"), str) or not isinstance(item.get("category", ""), str):
                    raise ValueError("Invalid saved analytics catalog identity.")
                result.append({
                    "itemType": kind, "itemId": item["id"], "name": item["name"],
                    "category": str(item.get("category", "")), "currency": market["currency"],
                    "priceCents": int(cents),
                })
    return result


def analytics_inquiry_summaries(directory: Path | None = None) -> list[dict[str, object]]:
    """Keep private form fields in the inquiry layer, not the analytics store."""
    directory = directory or INQUIRIES_PATH
    result = []
    if not directory.exists():
        return result
    for path in directory.glob("*.json"):
        if path.stat().st_size > 512 * 1024:
            raise ValueError("Unexpected inquiry record size.")
        inquiry = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(inquiry, dict):
            raise ValueError("Invalid inquiry metadata.")
        result.append({"createdAt": inquiry.get("createdAt")})
    return result


def catalog_provenance(request: CatalogDetailsPayload, previous: dict[str, object]) -> dict[str, object]:
    if "provenance" not in request.model_fields_set:
        return {"provenance": previous["provenance"]} if "provenance" in previous else {}
    return {"provenance": request.provenance.model_dump() if request.provenance else ProvenancePayload().model_dump()}


def accessory_specifications(request: AccessoryPayload, previous: dict[str, object]) -> dict[str, object]:
    fields = {}
    for field in AccessorySpecificationsPayload.model_fields:
        default = "published" if field == "publicationStatus" and previous else getattr(request, field)
        value = getattr(request, field) if field in request.model_fields_set else previous.get(field, default)
        fields[field] = value.strip() if isinstance(value, str) else value
    return fields


def accessory_from_payload(accessory_id: int, request: AccessoryPayload, fallback_image: str) -> dict[str, object]:
    return {
        "id": accessory_id,
        "name": request.name.strip(),
        "category": canonical_category(request.category),
        "dimensions": request.dimensions.strip(),
        "material": request.material.strip(),
        "weight": request.weight.strip(),
        "notes": request.notes.strip(),
        "image": request.image or fallback_image,
    }


def catalog_photos(item: dict[str, object]) -> list[str]:
    photos = item.get("photos")
    values = photos if isinstance(photos, list) else []
    return list(dict.fromkeys(str(value) for value in [item.get("image"), *values] if value))


def catalog_details(
    request: ProductPayload | AccessoryPayload,
    previous: dict[str, object],
    fallback_image: str,
) -> dict[str, object]:
    if request.photos is not None:
        photos = list(dict.fromkeys(photo.strip() for photo in request.photos if photo.strip()))
        if any(not (photo.startswith("/images/") or photo.startswith("/api/uploads/") or photo.startswith("https://")) for photo in photos):
            raise HTTPException(status_code=422, detail="Photos must use an /images/ or /api/uploads/ path, or an HTTPS URL.")
    else:
        previous_photos = previous.get("photos")
        photos = list(previous_photos) if isinstance(previous_photos, list) else catalog_photos(previous)
        if request.image and request.image != previous.get("image"):
            photos = list(dict.fromkeys([request.image, *photos]))
        if not photos and fallback_image:
            photos = [fallback_image]

    compatibility = (
        {key: value.strip() for key, value in request.compatibility.model_dump().items()}
        if request.compatibility is not None
        else previous.get("compatibility", CompatibilityPayload().model_dump())
    )
    image = next((photo for photo in photos if Path(urlsplit(photo).path).suffix.lower() not in VIDEO_FORMATS), "")
    if not image and photos and photos[0].startswith("/api/uploads/") and photos[0].endswith(".mp4"):
        image = photos[0][:-4] + ".poster.jpg"
    return {"photos": photos, "image": image, "compatibility": compatibility}


def delete_catalog_images(item: dict[str, object]) -> None:
    for image in catalog_photos(item):
        delete_uploaded_image(image)


def product_specifications(request: ProductPayload, previous: dict[str, object]) -> dict[str, object]:
    return {
        field: getattr(request, field).strip() if field in request.model_fields_set else previous.get(
            field, ("published" if previous else "draft") if field == "publicationStatus" else "",
        )
        for field in ProductSpecificationsPayload.model_fields
    }


def delete_uploaded_image(image: object) -> None:
    image_path = uploaded_image_reference(image)
    if image_path is None:
        return

    references = {image_path}
    if image_path.endswith(".poster.jpg"):
        references.add(image_path[:-11] + ".mp4")
    try:
        items = [*load_products(), *load_accessories(), load_hero()]
        if any(references.intersection(uploaded_image_reference(photo) for photo in home_media(item)) for item in items):
            return
        (UPLOAD_PATH / Path(image_path).name).unlink(missing_ok=True)
        if image_path.endswith(".mp4"):
            delete_uploaded_image(image_path[:-4] + ".poster.jpg")
    except (OSError, HTTPException):
        # A completed save must not become an error or remove files with unknown references.
        logger.warning("Unable to clean up unreferenced catalog media.")


def uploaded_image_reference(image: object) -> str | None:
    try:
        parsed = urlsplit(str(image or ""))
        path = unquote(parsed.path, errors="strict")
    except (ValueError, UnicodeError):
        return None
    if parsed.scheme or parsed.netloc or not path.startswith("/api/uploads/"):
        return None
    filename = path.removeprefix("/api/uploads/")
    if not filename or filename in (".", "..") or any(character in filename for character in '/\\:'):
        return None
    return path


def home_media(item: dict[str, object]) -> list[str]:
    images = catalog_photos(item)
    engineering = item.get("engineering")
    if isinstance(engineering, dict) and isinstance(engineering.get("items"), list):
        images.extend(str(card["image"]) for card in engineering["items"] if isinstance(card, dict) and card.get("image"))
    return images


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": "styl-api"}


@app.get("/api/admin/catalog-backup", dependencies=[Depends(require_admin)])
def download_catalog_backup() -> StreamingResponse:
    if not BACKUP_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=503, detail="Another catalog backup is being prepared. Please retry shortly.")
    archive = None
    try:
        archive = TemporaryFile(mode="w+b")
        with CATALOG_LOCK:
            create_archive(
                archive, products_path=DATA_PATH, accessories_path=ACCESSORIES_PATH,
                hero_path=HERO_PATH, uploads_path=UPLOAD_PATH, images_path=PUBLIC_IMAGE_PATH,
                default_hero=DEFAULT_HERO.model_dump(), app_version=app.version,
            )
        archive.seek(0, 2)
        size = archive.tell()
        archive.seek(0)
    except BackupError as error:
        if archive is not None:
            archive.close()
        logger.warning("Catalog backup rejected.")
        raise HTTPException(status_code=409, detail=str(error)) from None
    except OSError:
        if archive is not None:
            archive.close()
        logger.error("Unable to prepare catalog backup.")
        raise HTTPException(status_code=503, detail="Unable to prepare the catalog backup. Check server storage and permissions, then retry.") from None
    finally:
        BACKUP_LOCK.release()

    def chunks() -> Iterator[bytes]:
        try:
            while chunk := archive.read(1024 * 1024):
                yield chunk
        finally:
            archive.close()

    filename = f"styl-catalog-backup-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.zip"
    return StreamingResponse(
        chunks(), media_type="application/zip", background=BackgroundTask(archive.close),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(size), "Cache-Control": "no-store, private",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.put("/api/admin/{catalog}/order", dependencies=[Depends(require_admin)])
def update_catalog_order(catalog: Literal["products", "accessories"], request: CatalogOrderRequest, response: Response) -> dict[str, object]:
    path = DATA_PATH if catalog == "products" else ACCESSORIES_PATH
    with CATALOG_LOCK:
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(records, list) or any(
                not isinstance(item, dict) or type(item.get("id")) is not int or item["id"] < 1
                for item in records
            ):
                raise ValueError("Invalid catalog identity.")
            current_ids = [item["id"] for item in records]
            if len(set(current_ids)) != len(current_ids):
                raise ValueError("Duplicate catalog identity.")
        except (OSError, ValueError):
            logger.error("Unable to read saved %s for listing order.", catalog)
            raise HTTPException(status_code=503, detail="Saved catalog data is unavailable or invalid. Listing order was not changed.") from None
        if request.expectedIds != current_ids:
            raise HTTPException(status_code=409, detail="The catalog changed in another session. Refresh listing order and try again; your open form edits are kept.")
        if set(request.ids) != set(current_ids):
            raise HTTPException(status_code=422, detail="Listing order must include every current item exactly once.")
        if request.ids != current_ids:
            by_id = {item["id"]: item for item in records}
            try:
                write_json_list(path, [by_id[identifier] for identifier in request.ids])
            except OSError:
                logger.error("Unable to save %s listing order.", catalog)
                raise HTTPException(status_code=503, detail="Unable to save listing order. Please retry after checking server storage.") from None
    response.headers["Cache-Control"] = "no-store, private"
    return {"status": "saved", "ids": request.ids}


@app.get("/api/admin/verify", dependencies=[Depends(require_admin)])
def verify_admin() -> dict[str, str]:
    return {"status": "authorized"}


@app.get("/api/products")
def get_products(request: Request, response: Response) -> dict[str, object]:
    market = request_market(request, response)
    return {"items": [public_catalog_item(product, market) for product in load_products() if visible_in_market(product, market)], "market": market}


@app.get("/api/market")
def get_market(request: Request, response: Response) -> MarketContext:
    return request_market(request, response)


@app.get("/api/catalog/selection")
def get_catalog_selection(request: Request, response: Response) -> dict[str, object]:
    market = request_market(request, response)
    items = [
        {key: value for key, value in public_catalog_item(item, market).items()
         if key in ("id", "name", "slug", "price", "msrp", "currency", "sellingUnit", "packageQuantity")}
        for item in [*load_products(), *load_accessories()] if visible_in_market(item, market)
    ]
    return {"items": items, "market": market}


@app.get("/api/admin/products", dependencies=[Depends(require_admin)])
def get_admin_products() -> dict[str, list[dict[str, object]]]:
    return {"items": [admin_catalog_item(item) for item in load_products()]}


@app.get("/api/admin/categories", dependencies=[Depends(require_admin)])
def get_admin_categories() -> dict[str, list[str]]:
    return {"items": catalog_categories()}


@app.get("/api/products/{slug}")
def get_product_by_slug(slug: str, request: Request, response: Response) -> dict[str, object]:
    market = request_market(request, response)
    for product in load_products():
        if product.get("slug") == slug and visible_in_market(product, market):
            return {"item": public_catalog_item(product, market), "market": market}

    raise HTTPException(status_code=404, detail="Product not found", headers={"Cache-Control": "private, no-store"})


@app.get("/api/categories")
def get_categories(request: Request, response: Response) -> dict[str, list[str]]:
    market = request_market(request, response)
    categories = sorted({normalize_category(str(product.get("category", ""))) for product in load_products() if product.get("category") and visible_in_market(product, market)})
    return {"items": categories}


@app.post("/api/uploads/product-image", dependencies=[Depends(require_admin)])
async def upload_product_image(image: UploadFile = File(...)) -> dict[str, str]:
    extension = IMAGE_EXTENSIONS.get(image.content_type or "")
    if not extension:
        raise HTTPException(status_code=415, detail="Upload a JPG, PNG, WebP, or GIF image.")

    content = await image.read(MAX_IMAGE_SIZE + 1)
    await image.close()
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="Image must be 8 MB or smaller.")

    filename = f"{uuid4().hex}{extension}"
    (UPLOAD_PATH / filename).write_bytes(content)
    return {"image": f"/api/uploads/{filename}"}


@app.post("/api/uploads/product-video", dependencies=[Depends(require_admin)])
def upload_product_video(video: UploadFile = File(...)) -> dict[str, str]:
    return upload_video(video, UPLOAD_PATH)


@app.post("/api/products", dependencies=[Depends(require_admin)])
def create_product(request: ProductPayload) -> dict[str, object]:
    with locked_catalog() as products:
        next_id = max((int(product.get("id", 0)) for product in products), default=0) + 1
        base_slug = request.slug or slugify(request.name)
        slug = base_slug
        counter = 1
        while any(str(product.get("slug")) == slug for product in products):
            slug = f"{base_slug}-{counter}"
            counter += 1

        product = {
            "id": next_id,
            "slug": slug,
            "name": request.name.strip(),
            "category": canonical_category(request.category),
            "shortDescription": request.shortDescription.strip(),
            "description": request.description.strip(),
            "featured": bool(request.featured),
            "image": request.image or "/images/pro-elite.svg",
            "features": [feature.strip() for feature in request.features if feature and feature.strip()],
        }
        product.update(catalog_details(request, {}, "/images/pro-elite.svg"))
        product.update(catalog_prices(request, {}))
        product.update(catalog_msrps(request, {}))
        product.update(product_specifications(request, {}))
        product.update(catalog_provenance(request, {}))
        products.append(product)
        save_products(products)
    return {"status": "created", "item": admin_catalog_item(product)}


@app.put("/api/products/{product_id}", dependencies=[Depends(require_admin)])
def update_product(product_id: int, request: ProductPayload) -> dict[str, object]:
    with locked_catalog() as products:
        for index, product in enumerate(products):
            if int(product.get("id", 0)) == product_id:
                updated = {
                    "id": product_id,
                    "slug": request.slug or str(product.get("slug")) or slugify(request.name),
                    "name": request.name.strip(),
                    "category": canonical_category(request.category),
                    "shortDescription": request.shortDescription.strip(),
                    "description": request.description.strip(),
                    "featured": bool(request.featured),
                    "image": request.image or str(product.get("image") or "/images/pro-elite.svg"),
                    "features": [feature.strip() for feature in request.features if feature and feature.strip()],
                }
                updated.update(catalog_details(request, product, "/images/pro-elite.svg"))
                updated.update(catalog_prices(request, product))
                updated.update(catalog_msrps(request, product))
                updated.update(product_specifications(request, product))
                updated.update(catalog_provenance(request, product))
                products[index] = updated
                save_products(products)
                delete_catalog_images(product)
                return {"status": "updated", "item": admin_catalog_item(updated)}

    raise HTTPException(status_code=404, detail="Product not found")


@app.delete("/api/products/{product_id}", dependencies=[Depends(require_admin)])
def delete_product(product_id: int) -> dict[str, str]:
    with locked_catalog() as products:
        deleted_product = next(
            (product for product in products if int(product.get("id", 0)) == product_id),
            None,
        )
        filtered = [product for product in products if int(product.get("id", 0)) != product_id]
        if len(filtered) == len(products):
            raise HTTPException(status_code=404, detail="Product not found")

        save_products(filtered)
        if deleted_product:
            delete_catalog_images(deleted_product)
    return {"status": "deleted", "message": f"Product {product_id} deleted."}


@app.get("/api/accessories")
def get_accessories(request: Request, response: Response) -> dict[str, object]:
    market = request_market(request, response)
    return {"items": [public_catalog_item(item, market) for item in load_accessories() if visible_in_market(item, market)], "market": market}


@app.get("/api/accessories/{item_id}")
def get_accessory_by_id(item_id: Annotated[int, PathParameter(ge=1)], request: Request, response: Response) -> dict[str, object]:
    market = request_market(request, response)
    for item in load_accessories():
        if item.get("id") == item_id and visible_in_market(item, market):
            return {"item": public_catalog_item(item, market), "market": market}

    raise HTTPException(status_code=404, detail="Accessory not found", headers={"Cache-Control": "private, no-store"})


@app.get("/api/admin/accessories", dependencies=[Depends(require_admin)])
def get_admin_accessories() -> dict[str, list[dict[str, object]]]:
    return {"items": [admin_catalog_item(item) for item in load_accessories()]}


@app.post("/api/accessories", dependencies=[Depends(require_admin)])
def create_accessory(request: AccessoryPayload) -> dict[str, object]:
    if not request.name.strip():
        raise HTTPException(status_code=422, detail="Name is required.")

    with ACCESSORIES_LOCK:
        accessories = load_accessories()
        highest_id = max((int(item.get("id", 0)) for item in accessories), default=ACCESSORY_ID_OFFSET)
        created = accessory_from_payload(
            max(highest_id, ACCESSORY_ID_OFFSET) + 1,
            request,
            "/images/accessories/straight-bar.svg",
        )
        created.update(catalog_details(request, {}, "/images/accessories/straight-bar.svg"))
        created.update(catalog_prices(request, {}))
        created.update(catalog_msrps(request, {}))
        created.update(accessory_specifications(request, {}))
        created.update(catalog_provenance(request, {}))
        accessories.append(created)
        write_json_list(ACCESSORIES_PATH, accessories)
    return {"status": "created", "item": admin_catalog_item(created)}


@app.put("/api/accessories/{accessory_id}", dependencies=[Depends(require_admin)])
def update_accessory(accessory_id: int, request: AccessoryPayload) -> dict[str, object]:
    if not request.name.strip():
        raise HTTPException(status_code=422, detail="Name is required.")

    with ACCESSORIES_LOCK:
        accessories = load_accessories()
        for index, existing in enumerate(accessories):
            if int(existing.get("id", 0)) == accessory_id:
                updated = accessory_from_payload(accessory_id, request, str(existing.get("image") or ""))
                updated.update(catalog_details(request, existing, "/images/accessories/straight-bar.svg"))
                updated.update(catalog_prices(request, existing))
                updated.update(catalog_msrps(request, existing))
                updated.update(accessory_specifications(request, existing))
                updated.update(catalog_provenance(request, existing))
                accessories[index] = updated
                write_json_list(ACCESSORIES_PATH, accessories)
                delete_catalog_images(existing)
                return {"status": "updated", "item": admin_catalog_item(updated)}

    raise HTTPException(status_code=404, detail="Accessory not found")


@app.delete("/api/accessories/{accessory_id}", dependencies=[Depends(require_admin)])
def delete_accessory(accessory_id: int) -> dict[str, str]:
    with ACCESSORIES_LOCK:
        accessories = load_accessories()
        deleted = next((item for item in accessories if int(item.get("id", 0)) == accessory_id), None)
        if deleted is None:
            raise HTTPException(status_code=404, detail="Accessory not found")

        write_json_list(ACCESSORIES_PATH, [item for item in accessories if item is not deleted])
        delete_catalog_images(deleted)
    return {"status": "deleted", "message": f"Accessory {accessory_id} deleted."}


def unique_home_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise ValueError("Duplicate saved home configuration fields.")
    return fields


def load_hero() -> dict[str, object]:
    try:
        data = json.loads(HERO_PATH.read_text(encoding="utf-8"), object_pairs_hook=unique_home_fields)
        if not isinstance(data, dict) or not {"tag", "number", "eyebrow", "title", "image"}.issubset(data):
            raise ValueError("Invalid saved home configuration.")
        data.pop("priceLabel", None)
        return HeroPayload(**data).model_dump()
    except FileNotFoundError:
        return DEFAULT_HERO.model_dump()
    except (OSError, TypeError, ValueError, RecursionError):
        logger.error("Unable to read saved home configuration.")
        raise HTTPException(status_code=503, detail="Saved home configuration is unavailable or invalid. No changes were made.") from None


@app.get("/api/hero")
def get_hero(response: Response) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    return {"item": load_hero()}


@app.get("/api/admin/hero", dependencies=[Depends(require_admin)])
def get_admin_hero() -> dict[str, object]:
    return {"item": load_hero()}


@app.put("/api/hero", dependencies=[Depends(require_admin)])
def update_hero(request: HeroPayload) -> dict[str, object]:
    with HERO_LOCK:
        previous = load_hero()
        updated = {**previous, **{
            key: value.strip() if isinstance(value, str) else value
            for key, value in request.model_dump(exclude_unset=True).items()
        }}
        if "image" in request.model_fields_set:
            updated["image"] = updated["image"] or DEFAULT_HERO.image
        try:
            write_json_list(HERO_PATH, updated)
        except OSError:
            logger.error("Unable to save home configuration.")
            raise HTTPException(status_code=503, detail="Unable to save home configuration. Check server storage and permissions, then retry.") from None
        for image in set(home_media(previous)) - set(home_media(updated)):
            delete_uploaded_image(image)
    return {"status": "updated", "item": updated}


def send_inquiry_email(request: InquiryRequest, inquiry_id: str) -> str:
    host = os.getenv("STYL_SMTP_HOST", "")
    username = os.getenv("STYL_SMTP_USERNAME", "")
    password = os.getenv("STYL_SMTP_PASSWORD", "")
    if not all((host, username, password)):
        return "unconfigured"

    configured_recipients = os.getenv("STYL_INQUIRY_RECIPIENTS", INQUIRY_RECIPIENT)
    if "\r" in configured_recipients or "\n" in configured_recipients:
        logger.error("Invalid inquiry recipient configuration; email was not sent.")
        raise ValueError("Recipient configuration must be a comma-separated address list.")
    try:
        recipients = list(dict.fromkeys(INQUIRY_RECIPIENTS_ADAPTER.validate_python(
            [address.strip() for address in configured_recipients.split(",")],
        )))
    except ValueError:
        logger.error("Invalid inquiry recipient configuration; email was not sent.")
        raise ValueError("Configure valid inquiry recipient email addresses.") from None

    port = int(os.getenv("STYL_SMTP_PORT", "587"))
    email = EmailMessage()
    email["From"] = os.getenv("STYL_SMTP_FROM", INQUIRY_RECIPIENT)
    email["To"] = ", ".join(recipients)
    email["Reply-To"] = str(request.email)
    email["Subject"] = f"STYL inquiry {inquiry_id}"
    email.set_content(
        f"Inquiry ID: {inquiry_id}\n"
        f"Name: {request.name}\n"
        f"Email: {request.email}\n"
        f"Phone: {request.phone or ''}\n"
        f"Company: {request.company or ''}\n"
        f"Source: {request.source}\n\n"
        f"{request.message}\n"
    )
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=10, context=context) as smtp:
            smtp.login(username, password)
            refused = smtp.send_message(email, to_addrs=recipients)
    else:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.starttls(context=context)
            smtp.login(username, password)
            refused = smtp.send_message(email, to_addrs=recipients)
    if refused:
        raise smtplib.SMTPException("Inquiry recipient refused")
    return "sent"


@app.post("/api/inquiries")
def create_inquiry(request: InquiryRequest) -> dict[str, str]:
    inquiry_id = uuid4().hex
    path = INQUIRIES_PATH / f"{inquiry_id}.json"
    inquiry = {
        **request.model_dump(mode="json"),
        "id": inquiry_id,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "emailStatus": "pending",
    }
    try:
        write_json_list(path, inquiry)
    except OSError:
        logger.error("Unable to save inquiry %s", inquiry_id)
        raise HTTPException(status_code=503, detail="Unable to save your inquiry. Please try again.") from None

    try:
        inquiry["emailStatus"] = send_inquiry_email(request, inquiry_id)
    except (OSError, smtplib.SMTPException, ValueError):
        inquiry["emailStatus"] = "failed"
    if inquiry["emailStatus"] != "sent":
        logger.warning("Inquiry %s saved; email status: %s", inquiry_id, inquiry["emailStatus"])
    try:
        write_json_list(path, inquiry)
    except OSError:
        logger.error("Unable to update email status for saved inquiry %s", inquiry_id)
    return {
        "status": "received",
        "id": inquiry_id,
        "message": f"Thank you, {request.name}. Our team will contact you shortly.",
    }


@app.get("/api/uploads/{filename}.mp4")
def get_uploaded_video(filename: str, range: str | None = Header(default=None)) -> StreamingResponse:
    if not re.fullmatch(r"[a-f0-9]{32}", filename):
        raise HTTPException(status_code=404, detail="Video not found.")
    return video_response(UPLOAD_PATH / f"{filename}.mp4", range)


app.include_router(analytics.make_router(require_admin, ALLOWED_ORIGINS))
app.mount("/api/uploads", StaticFiles(directory=UPLOAD_PATH), name="uploads")
