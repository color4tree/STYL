from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field

DATA_PATH = Path(__file__).resolve().parent / "data" / "products.json"
UPLOAD_PATH = Path(__file__).resolve().parent / "uploads"
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
    allow_origins=["*"],
    allow_credentials=True,
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


class ProductPayload(BaseModel):
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
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(products, indent=2), encoding="utf-8")


def delete_uploaded_image(image: object) -> None:
    image_path = str(image or "")
    if not image_path.startswith("/api/uploads/"):
        return

    filename = Path(image_path).name
    (UPLOAD_PATH / filename).unlink(missing_ok=True)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": "styl-api"}


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


@app.post("/api/uploads/product-image")
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


@app.post("/api/products")
def create_product(request: ProductPayload) -> dict[str, object]:
    products = load_products()
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
    products.append(product)
    save_products(products)
    return {"status": "created", "item": product}


@app.put("/api/products/{product_id}")
def update_product(product_id: int, request: ProductPayload) -> dict[str, object]:
    products = load_products()
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
            products[index] = updated
            save_products(products)
            if product.get("image") != updated["image"]:
                delete_uploaded_image(product.get("image"))
            return {"status": "updated", "item": updated}

    raise HTTPException(status_code=404, detail="Product not found")


@app.delete("/api/products/{product_id}")
def delete_product(product_id: int) -> dict[str, str]:
    products = load_products()
    deleted_product = next(
        (product for product in products if int(product.get("id", 0)) == product_id),
        None,
    )
    filtered = [product for product in products if int(product.get("id", 0)) != product_id]
    if len(filtered) == len(products):
        raise HTTPException(status_code=404, detail="Product not found")

    save_products(filtered)
    if deleted_product:
        delete_uploaded_image(deleted_product.get("image"))
    return {"status": "deleted", "message": f"Product {product_id} deleted."}


@app.post("/api/inquiries")
def create_inquiry(request: InquiryRequest) -> dict[str, str]:
    return {
        "status": "received",
        "message": f"Thank you, {request.name}. Our team will contact you shortly.",
    }


app.mount("/api/uploads", StaticFiles(directory=UPLOAD_PATH), name="uploads")
