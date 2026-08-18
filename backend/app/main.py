from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

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


PRODUCTS = [
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
        "features": [
            "Heavy-duty stability frame",
            "Modular training configuration",
            "Designed for long-term reliability",
        ],
    },
]


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "service": "styl-api"}


@app.get("/api/products")
def get_products() -> dict[str, list[dict[str, object]]]:
    return {"items": PRODUCTS}


@app.get("/api/products/{slug}")
def get_product_by_slug(slug: str) -> dict[str, object]:
    for product in PRODUCTS:
        if product["slug"] == slug:
            return {"item": product}

    raise HTTPException(status_code=404, detail="Product not found")


@app.get("/api/categories")
def get_categories() -> dict[str, list[str]]:
    return {"items": ["Strength", "Cardio", "Performance"]}


@app.post("/api/inquiries")
def create_inquiry(request: InquiryRequest) -> dict[str, str]:
    return {
        "status": "received",
        "message": f"Thank you, {request.name}. Our team will contact you shortly.",
    }
