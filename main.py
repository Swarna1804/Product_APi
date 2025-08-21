import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, Query, HTTPException

from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from sqlalchemy.exc import SQLAlchemyError

# -------------------------------------------------------------------
# FastAPI App
# -------------------------------------------------------------------
app = FastAPI(title="Product APIs – Step 1 to Step 6")

# -------------------------------------------------------------------
# Config
# -------------------------------------------------------------------
EXTERNAL_API_URL = os.getenv("EXTERNAL_API_URL")  # electronics API
BRANDS_API_URL = os.getenv("BRANDS_API_URL")  # brands API
LOCAL_SAMPLE_PATH = os.getenv("LOCAL_SAMPLE_PATH", "sample_electronics.json")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./products.db")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

REQUIRED_SOURCE_FIELDS = [
    "productId", "productName", "brandName", "category", "description", "price",
    "currency", "processor", "memory", "releaseDate", "averageRating", "ratingCount"
]

# -------------------------------------------------------------------
# Database setup
# -------------------------------------------------------------------
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Brand(Base):
    __tablename__ = "brands"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    year_founded = Column(Integer, nullable=True)
    street = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    country = Column(String, nullable=True)

    products = relationship("Product", back_populates="brand")


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    productId = Column(String, unique=True, nullable=False)
    productName = Column(String, nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    category = Column(String)
    description = Column(Text)
    price = Column(Float)
    currency = Column(String)
    discountPercentage = Column(Float)
    stockQuantity = Column(Integer)
    warehouseLocation = Column(String)
    sku = Column(String)
    processor = Column(String)
    memory = Column(String)
    storageCapacity = Column(String)
    displaySize = Column(String)
    isAvailable = Column(Boolean)
    releaseDate = Column(String)
    lastUpdated = Column(String)
    averageRating = Column(Float)
    ratingCount = Column(Integer)
    warrantyDurationMonths = Column(Integer)
    weight_kg = Column(Float)

    brand = relationship("Brand", back_populates="products")


# create tables if not exist
Base.metadata.create_all(bind=engine)

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def load_source_data() -> List[Dict[str, Any]]:
    if EXTERNAL_API_URL:
        try:
            resp = requests.get(EXTERNAL_API_URL, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Failed to fetch electronics API: {e}")
    else:
        if not os.path.exists(LOCAL_SAMPLE_PATH):
            raise HTTPException(status_code=500, detail="Local sample file not found.")
        with open(LOCAL_SAMPLE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    if not isinstance(data, list):
        raise HTTPException(status_code=502, detail="Electronics API did not return a list.")
    return data


def load_brand_data() -> List[Dict[str, Any]]:
    if not BRANDS_API_URL:
        raise HTTPException(status_code=500, detail="BRANDS_API_URL not configured.")
    try:
        resp = requests.get(BRANDS_API_URL, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch brands API: {e}")
    if not isinstance(data, list):
        raise HTTPException(status_code=502, detail="Brands API did not return a list.")
    return data


def is_malformed(item: Dict[str, Any]) -> bool:
    for k in REQUIRED_SOURCE_FIELDS:
        if k not in item:
            return True
    release_date = item.get("releaseDate")
    if release_date and not (isinstance(release_date, str) and DATE_RE.match(release_date)):
        return True
    price = item.get("price")
    if price is not None and not isinstance(price, (int, float)):
        return True
    avg = item.get("averageRating")
    if avg is not None and not (0 <= avg <= 5):
        return True
    rc = item.get("ratingCount")
    if rc is not None and not (isinstance(rc, int) and rc >= 0):
        return True
    return False


def filter_products(products: List[Dict[str, Any]], release_date_start: Optional[str], release_date_end: Optional[str], brands: Optional[str]) -> List[Dict[str, Any]]:
    try:
        start_date = datetime.strptime(release_date_start, "%Y-%m-%d") if release_date_start else None
        end_date = datetime.strptime(release_date_end, "%Y-%m-%d") if release_date_end else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    filtered = []
    for p in products:
        if p.get("releaseDate"):
            try:
                product_date = datetime.strptime(p["releaseDate"], "%Y-%m-%d")
            except ValueError:
                continue
            if start_date and product_date < start_date:
                continue
            if end_date and product_date > end_date:
                continue
        filtered.append(p)

    if brands:
        brand_list = [b.strip() for b in brands.split(",") if b.strip()]
        filtered = [p for p in filtered if p["brandName"] in brand_list]

    return filtered


def paginate(products: List[Dict[str, Any]], page_size: int, page_number: int) -> List[Dict[str, Any]]:
    start_index = (page_number - 1) * page_size
    end_index = start_index + page_size
    return products[start_index:end_index]

# -------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "Backend running. Use /step1 ... /step6."}


@app.get("/step1")
def step1() -> List[Dict[str, Any]]:
    data = load_source_data()
    return [item for item in data if isinstance(item, dict) and not is_malformed(item)]


@app.get("/step2")
def step2(release_date_start: Optional[str] = None, release_date_end: Optional[str] = None):
    return filter_products(step1(), release_date_start, release_date_end, None)


@app.get("/step3")
def step3(brands: Optional[str] = None, release_date_start: Optional[str] = None, release_date_end: Optional[str] = None):
    return filter_products(step2(release_date_start, release_date_end), None, None, brands)


@app.get("/step4")
def step4(page_size: int = Query(..., gt=0), page_number: int = Query(..., gt=0),
          brands: Optional[str] = None, release_date_start: Optional[str] = None, release_date_end: Optional[str] = None):
    return paginate(step3(brands, release_date_start, release_date_end), page_size, page_number)


@app.get("/step5")
def step5(page_size: int = Query(..., gt=0), page_number: int = Query(..., gt=0),
          brands: Optional[str] = None, release_date_start: Optional[str] = None, release_date_end: Optional[str] = None):
    electronics = load_source_data()
    brands_data = load_brand_data()

    products = [item for item in electronics if isinstance(item, dict) and not is_malformed(item)]
    products = filter_products(products, release_date_start, release_date_end, brands)
    products = paginate(products, page_size, page_number)

    brand_lookup = {b.get("name"): b for b in brands_data if isinstance(b, dict)}
    merged = []
    for p in products:
        brand_info = brand_lookup.get(p["brandName"])
        if brand_info:
            year_founded = brand_info.get("year_founded")
            company_age = datetime.now().year - year_founded if isinstance(year_founded, int) else None
            address = brand_info.get("address", {})
            address_str = ", ".join(filter(None, [
                address.get("street"), address.get("city"), address.get("state"),
                address.get("postal_code"), address.get("country")
            ]))
            merged.append({**p, "brand": {"name": brand_info.get("name"), "yearFounded": year_founded, "companyAge": company_age, "address": address_str}})
        else:
            merged.append({**p, "brand": {"name": p["brandName"]}})
    return merged


@app.get("/step6")
def step6(page_size: int = Query(..., gt=0), page_number: int = Query(..., gt=0),
          brands: Optional[str] = None, release_date_start: Optional[str] = None, release_date_end: Optional[str] = None):
    try:
        db = SessionLocal()
        query = db.query(Product).join(Brand)

        if brands:
            query = query.filter(Brand.name.in_([b.strip() for b in brands.split(",")]))

        if release_date_start:
            query = query.filter(Product.releaseDate >= release_date_start)
        if release_date_end:
            query = query.filter(Product.releaseDate <= release_date_end)

        total = query.count()
        products = query.offset((page_number - 1) * page_size).limit(page_size).all()

        result = []
        for p in products:
            brand = p.brand
            company_age = datetime.now().year - brand.year_founded if brand.year_founded else None
            address_str = ", ".join(filter(None, [brand.street, brand.city, brand.state, brand.postal_code, brand.country]))
            result.append({
                "productId": p.productId,
                "productName": p.productName,
                "brandName": brand.name,
                "category": p.category,
                "description": p.description,
                "price": p.price,
                "currency": p.currency,
                "discountPercentage": p.discountPercentage,
                "stockQuantity": p.stockQuantity,
                "warehouseLocation": p.warehouseLocation,
                "sku": p.sku,
                "processor": p.processor,
                "memory": p.memory,
                "storageCapacity": p.storageCapacity,
                "displaySize": p.displaySize,
                "isAvailable": p.isAvailable,
                "releaseDate": p.releaseDate,
                "lastUpdated": p.lastUpdated,
                "averageRating": p.averageRating,
                "ratingCount": p.ratingCount,
                "warrantyDurationMonths": p.warrantyDurationMonths,
                "weight_kg": p.weight_kg,
                "brand": {
                    "name": brand.name,
                    "yearFounded": brand.year_founded,
                    "companyAge": company_age,
                    "address": address_str
                }
            })

        return {"total": total, "page_number": page_number, "page_size": page_size, "items": result}

    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        db.close()
