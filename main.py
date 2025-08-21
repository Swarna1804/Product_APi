import json
import os
import re
from datetime import datetime, date
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, Query, HTTPException, Depends
from pydantic import BaseModel, Field, validator

from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey, Text, Date
from sqlalchemy.orm import sessionmaker, relationship, declarative_base, Session
from sqlalchemy.exc import SQLAlchemyError

# -------------------------------------------------------------------
# FastAPI App
# -------------------------------------------------------------------
app = FastAPI(title="Product APIs – Step 1 to Step 7")

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
    product_id = Column(String, unique=True, nullable=False)
    product_name = Column(String, nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    category_name = Column(String)
    description_text = Column(Text)
    price = Column(Float)
    currency = Column(String)
    processor = Column(String)
    memory = Column(String)
    release_date = Column(Date)
    average_rating = Column(Float)
    rating_count = Column(Integer)

    brand = relationship("Brand", back_populates="products")


# Create tables
Base.metadata.create_all(bind=engine)

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
        start_date = datetime.strptime(release_date_start, "%Y-%m-%d").date() if release_date_start else None
        end_date = datetime.strptime(release_date_end, "%Y-%m-%d").date() if release_date_end else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    filtered = []
    for p in products:
        if p.get("releaseDate"):
            try:
                product_date = datetime.strptime(p["releaseDate"], "%Y-%m-%d").date()
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


def map_product_fields(item: Dict[str, Any]) -> Dict[str, Any]:
    """Map keys to project-required JSON structure"""
    return {
        "product_id": item.get("productId"),
        "product_name": item.get("productName"),
        "brand_name": item.get("brandName"),
        "category_name": item.get("category"),
        "description_text": item.get("description"),
        "price": item.get("price"),
        "currency": item.get("currency"),
        "processor": item.get("processor"),
        "memory": item.get("memory"),
        "release_date": item.get("releaseDate"),
        "average_rating": item.get("averageRating"),
        "rating_count": item.get("ratingCount"),
    }


# -------------------------------------------------------------------
# Endpoints Step 1–5
# -------------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "Backend running. Use /step1 ... /step7."}


@app.get("/step1")
def step1():
    data = load_source_data()
    return [map_product_fields(item) for item in data if isinstance(item, dict) and not is_malformed(item)]


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

    products = [map_product_fields(item) for item in electronics if isinstance(item, dict) and not is_malformed(item)]
    products = filter_products(products, release_date_start, release_date_end, brands)
    products = paginate(products, page_size, page_number)

    brand_lookup = {b.get("name"): b for b in brands_data if isinstance(b, dict)}
    merged = []
    for p in products:
        brand_info = brand_lookup.get(p["brand_name"])
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
            merged.append({**p, "brand": {"name": p["brand_name"], "yearFounded": None, "companyAge": None, "address": None}})
    return merged


# -------------------------------------------------------------------
# Step 6: DB Endpoint
# -------------------------------------------------------------------
@app.get("/step6")
def step6(page_size: int = Query(..., gt=0), page_number: int = Query(..., gt=0),
          brands: Optional[str] = None, release_date_start: Optional[str] = None, release_date_end: Optional[str] = None,
          db: Session = Depends(get_db)):
    try:
        query = db.query(Product).join(Brand)
        if brands:
            query = query.filter(Brand.name.in_([b.strip() for b in brands.split(",")]))
        if release_date_start:
            query = query.filter(Product.release_date >= release_date_start)
        if release_date_end:
            query = query.filter(Product.release_date <= release_date_end)
        total = query.count()
        products = query.offset((page_number - 1) * page_size).limit(page_size).all()

        result = []
        for p in products:
            brand = p.brand
            company_age = datetime.now().year - brand.year_founded if brand.year_founded else None
            address_str = ", ".join(filter(None, [brand.street, brand.city, brand.state, brand.postal_code, brand.country]))
            result.append({
                "product_id": p.product_id,
                "product_name": p.product_name,
                "brand_name": brand.name,
                "category_name": p.category_name,
                "description_text": p.description_text,
                "price": p.price,
                "currency": p.currency,
                "processor": p.processor,
                "memory": p.memory,
                "release_date": p.release_date.isoformat() if p.release_date else None,
                "average_rating": p.average_rating,
                "rating_count": p.rating_count,
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


# -------------------------------------------------------------------
# Step 7: CRUD with Validation
# -------------------------------------------------------------------
class BrandSchema(BaseModel):
    name: str = Field(..., min_length=1)
    year_founded: Optional[int] = None
    company_age: Optional[int] = None
    address: Optional[str] = None


class ProductSchema(BaseModel):
    product_name: str = Field(..., min_length=1)
    brand: BrandSchema
    category_name: str = Field(..., min_length=1)
    description_text: Optional[str] = None
    price: float = Field(..., gt=0)
    currency: str = Field(..., min_length=1)
    processor: Optional[str] = None
    memory: Optional[str] = None
    release_date: date
    average_rating: float = Field(..., ge=0, le=5)
    rating_count: int = Field(..., ge=0)

# CREATE
@app.post("/step7/create", status_code=201)
def create_product(product: ProductSchema, db: Session = Depends(get_db)):
    brand = db.query(Brand).filter(Brand.name == product.brand.name).first()
    if not brand:
        brand = Brand(
            name=product.brand.name,
            year_founded=product.brand.year_founded,
            street=None, city=None, state=None, postal_code=None, country=None
        )
        db.add(brand)
        db.commit()
        db.refresh(brand)

    db_product = Product(
        product_id=f"P{int(datetime.now().timestamp())}",  # unique ID
        product_name=product.product_name,
        brand_id=brand.id,
        category_name=product.category_name,
        description_text=product.description_text,
        price=product.price,
        currency=product.currency,
        processor=product.processor,
        memory=product.memory,
        release_date=product.release_date,
        average_rating=product.average_rating,
        rating_count=product.rating_count
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return {"message": "Product created successfully", "product_id": db_product.product_id}


# UPDATE
@app.put("/step7/update/{product_id}")
def update_product(product_id: str, product: ProductSchema, db: Session = Depends(get_db)):
    db_product = db.query(Product).filter(Product.product_id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    brand = db.query(Brand).filter(Brand.name == product.brand.name).first()
    if not brand:
        brand = Brand(
            name=product.brand.name,
            year_founded=product.brand.year_founded
        )
        db.add(brand)
        db.commit()
        db.refresh(brand)

    db_product.product_name = product.product_name
    db_product.brand_id = brand.id
    db_product.category_name = product.category_name
    db_product.description_text = product.description_text
    db_product.price = product.price
    db_product.currency = product.currency
    db_product.processor = product.processor
    db_product.memory = product.memory
    db_product.release_date = product.release_date
    db_product.average_rating = product.average_rating
    db_product.rating_count = product.rating_count

    db.commit()
    return {"message": "Product updated successfully"}


# DELETE
@app.delete("/step7/delete/{product_id}", status_code=204)
def delete_product(product_id: str, db: Session = Depends(get_db)):
    db_product = db.query(Product).filter(Product.product_id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(db_product)
    db.commit()
    return
