from __future__ import annotations

import json
import os
import re
import secrets
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from collections.abc import Iterator
from typing import Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field

APP_PATH = Path(__file__).resolve().parent
CONFIGURED_DATA_DIRECTORY = os.getenv("STYL_DATA_DIR")
DATA_DIRECTORY = Path(CONFIGURED_DATA_DIRECTORY) if CONFIGURED_DATA_DIRECTORY else APP_PATH / "data"
DATA_PATH = DATA_DIRECTORY / "products.json"
ACCESSORIES_PATH = DATA_DIRECTORY / "accessories.json"
HERO_PATH = DATA_DIRECTORY / "hero.json"
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
# Accessory IDs start above this so they don't collide with product IDs in the shared cart.
ACCESSORY_ID_OFFSET = 1000
MAX_IMAGE_SIZE = 8 * 1024 * 1024
IMAGE_EXTENSIONS = {
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

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
)


class InquiryRequest(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    company: str | None = None
    message: str
    source: Literal["website", "inquiry", "retail"] = "website"


class CompatibilityPayload(BaseModel):
    uprightSize: str = Field(default="", max_length=300)
    holeDiameter: str = Field(default="", max_length=300)
    holeSpacing: str = Field(default="", max_length=300)
    models: str = Field(default="", max_length=1000)
    limitations: str = Field(default="", max_length=2000)


class CatalogDetailsPayload(BaseModel):
    photos: list[str] | None = Field(default=None, max_length=12)
    compatibility: CompatibilityPayload | None = None


class ProductPayload(CatalogDetailsPayload):
    id: int | None = None
    slug: str | None = None
    name: str
    category: str
    price: float
    currency: str = "USD"
    shortDescription: str
    description: str
    featured: bool = False
    image: str | None = None
    features: list[str] = Field(default_factory=list)


class AccessoryPayload(CatalogDetailsPayload):
    name: str
    category: str
    dimensions: str = ""
    material: str = ""
    weight: str = ""
    price: float = Field(ge=0)
    currency: str = "USD"
    notes: str = ""
    image: str | None = None


class HeroPayload(BaseModel):
    tag: str = Field(default="", max_length=40)
    number: str = Field(default="", max_length=10)
    eyebrow: str = Field(default="", max_length=60)
    title: str = Field(default="", max_length=80)
    priceLabel: str = Field(default="", max_length=40)
    image: str = Field(default="", max_length=500)


DEFAULT_HERO = HeroPayload(
    tag="Signature",
    number="01",
    eyebrow="Pro Elite",
    title="Series X",
    priceLabel="$2,499",
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
    temporary_path.write_text(json.dumps(items, indent=2), encoding="utf-8")
    temporary_path.replace(path)


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


def accessory_from_payload(accessory_id: int, request: AccessoryPayload, fallback_image: str) -> dict[str, object]:
    return {
        "id": accessory_id,
        "name": request.name.strip(),
        "category": request.category.strip() or "General",
        "dimensions": request.dimensions.strip(),
        "material": request.material.strip(),
        "weight": request.weight.strip(),
        "price": float(request.price),
        "currency": request.currency or "USD",
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
        photos = catalog_photos(previous)
        if request.image:
            photos = list(dict.fromkeys([request.image, *photos]))
        if not photos and fallback_image:
            photos = [fallback_image]

    compatibility = (
        {key: value.strip() for key, value in request.compatibility.model_dump().items()}
        if request.compatibility is not None
        else previous.get("compatibility", CompatibilityPayload().model_dump())
    )
    return {"photos": photos, "image": photos[0] if photos else "", "compatibility": compatibility}


def delete_catalog_images(item: dict[str, object]) -> None:
    for image in catalog_photos(item):
        delete_uploaded_image(image)


def delete_uploaded_image(image: object) -> None:
    image_path = str(image or "")
    if not image_path.startswith("/api/uploads/"):
        return

    if any(image_path in catalog_photos(item) for item in [*load_products(), *load_accessories(), load_hero()]):
        return

    filename = Path(image_path).name
    (UPLOAD_PATH / filename).unlink(missing_ok=True)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": "styl-api"}


@app.get("/api/admin/verify", dependencies=[Depends(require_admin)])
def verify_admin() -> dict[str, str]:
    return {"status": "authorized"}


@app.get("/api/products")
def get_products() -> dict[str, list[dict[str, object]]]:
    return {"items": load_products()}


@app.get("/api/products/{slug}")
def get_product_by_slug(slug: str) -> dict[str, object]:
    for product in load_products():
        if product.get("slug") == slug:
            return {"item": product}

    raise HTTPException(status_code=404, detail="Product not found")


@app.get("/api/categories")
def get_categories() -> dict[str, list[str]]:
    categories = sorted({str(product.get("category", "")).strip() for product in load_products() if product.get("category")})
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
            "category": request.category.strip() or "General",
            "price": float(request.price),
            "currency": request.currency or "USD",
            "shortDescription": request.shortDescription.strip(),
            "description": request.description.strip(),
            "featured": bool(request.featured),
            "image": request.image or "/images/pro-elite.svg",
            "features": [feature.strip() for feature in request.features if feature and feature.strip()],
        }
        product.update(catalog_details(request, {}, "/images/pro-elite.svg"))
        products.append(product)
        save_products(products)
    return {"status": "created", "item": product}


@app.put("/api/products/{product_id}", dependencies=[Depends(require_admin)])
def update_product(product_id: int, request: ProductPayload) -> dict[str, object]:
    with locked_catalog() as products:
        for index, product in enumerate(products):
            if int(product.get("id", 0)) == product_id:
                updated = {
                    "id": product_id,
                    "slug": request.slug or str(product.get("slug")) or slugify(request.name),
                    "name": request.name.strip(),
                    "category": request.category.strip() or "General",
                    "price": float(request.price),
                    "currency": request.currency or str(product.get("currency", "USD")),
                    "shortDescription": request.shortDescription.strip(),
                    "description": request.description.strip(),
                    "featured": bool(request.featured),
                    "image": request.image or str(product.get("image") or "/images/pro-elite.svg"),
                    "features": [feature.strip() for feature in request.features if feature and feature.strip()],
                }
                updated.update(catalog_details(request, product, "/images/pro-elite.svg"))
                products[index] = updated
                save_products(products)
                delete_catalog_images(product)
                return {"status": "updated", "item": updated}

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
def get_accessories() -> dict[str, list[dict[str, object]]]:
    return {"items": load_accessories()}


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
        accessories.append(created)
        write_json_list(ACCESSORIES_PATH, accessories)
    return {"status": "created", "item": created}


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
                accessories[index] = updated
                write_json_list(ACCESSORIES_PATH, accessories)
                delete_catalog_images(existing)
                return {"status": "updated", "item": updated}

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


def load_hero() -> dict[str, object]:
    try:
        data = json.loads(HERO_PATH.read_text(encoding="utf-8"))
        return HeroPayload(**data).model_dump()
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        return DEFAULT_HERO.model_dump()


@app.get("/api/hero")
def get_hero() -> dict[str, object]:
    return {"item": load_hero()}


@app.put("/api/hero", dependencies=[Depends(require_admin)])
def update_hero(request: HeroPayload) -> dict[str, object]:
    with HERO_LOCK:
        previous = load_hero()
        updated = {key: value.strip() for key, value in request.model_dump().items()}
        updated["image"] = updated["image"] or DEFAULT_HERO.image
        write_json_list(HERO_PATH, updated)
        if previous.get("image") != updated["image"]:
            delete_uploaded_image(previous.get("image"))
    return {"status": "updated", "item": updated}


@app.post("/api/inquiries")
def create_inquiry(request: InquiryRequest) -> dict[str, str]:
    return {
        "status": "received",
        "message": f"Thank you, {request.name}. Our team will contact you shortly.",
    }


app.mount("/api/uploads", StaticFiles(directory=UPLOAD_PATH), name="uploads")
