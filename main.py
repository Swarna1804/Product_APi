import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, Query, HTTPException

app = FastAPI(title="Product APIs – Step 1 to Step 5")
EXTERNAL_API_URL = os.getenv("EXTERNAL_API_URL")  # electronics API
BRANDS_API_URL = os.getenv("BRANDS_API_URL")  # brands API
LOCAL_SAMPLE_PATH = os.getenv("LOCAL_SAMPLE_PATH", "sample_electronics.json")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

REQUIRED_SOURCE_FIELDS = [
    "productId", "productName", "brandName", "category", "description", "price",
    "currency", "processor", "memory", "releaseDate", "averageRating", "ratingCount"
]


def load_source_data() -> List[Dict[str, Any]]:
    """Load electronics data from external API or local JSON file."""
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
    """Load brand data from external API."""
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
    """Step 1: Validate electronics product data."""
    for k in REQUIRED_SOURCE_FIELDS:
        if k not in item:
            return True

    release_date = item.get("releaseDate")
    if release_date is not None and not (
        isinstance(release_date, str) and DATE_RE.match(release_date)
    ):
        return True

    price = item.get("price")
    if price is not None and not isinstance(price, (int, float)):
        return True

    avg = item.get("averageRating")
    if avg is not None and not (isinstance(avg, (int, float)) and 0 <= avg <= 5):
        return True

    rc = item.get("ratingCount")
    if rc is not None and not (isinstance(rc, int) and rc >= 0):
        return True

    return False


def map_to_required_shape(item: Dict[str, Any]) -> Dict[str, Any]:
    """Step 1: Map electronics API data to required shape."""
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


def filter_products(
    products: List[Dict[str, Any]],
    release_date_start: Optional[str],
    release_date_end: Optional[str],
    brands: Optional[str]
) -> List[Dict[str, Any]]:
    """Apply release_date and brand filters."""
    # Date filter
    try:
        start_date = (
            datetime.strptime(release_date_start, "%Y-%m-%d") if release_date_start else None
        )
        end_date = (
            datetime.strptime(release_date_end, "%Y-%m-%d") if release_date_end else None
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    filtered = []
    for p in products:
        if p.get("release_date"):
            try:
                product_date = datetime.strptime(p["release_date"], "%Y-%m-%d")
            except ValueError:
                continue
            if start_date and product_date < start_date:
                continue
            if end_date and product_date > end_date:
                continue

        filtered.append(p)

    # Brand filter
    if brands:
        brand_list = [b.strip() for b in brands.split(",") if b.strip()]
        filtered = [p for p in filtered if p["brand_name"] in brand_list]

    return filtered


def paginate(products: List[Dict[str, Any]], page_size: int, page_number: int) -> List[Dict[str, Any]]:
    """Paginate product list."""
    start_index = (page_number - 1) * page_size
    end_index = start_index + page_size
    if start_index >= len(products):
        return []
    return products[start_index:end_index]


@app.get("/step5")
def step5(
    page_size: int = Query(..., gt=0, description="Items per page"),
    page_number: int = Query(..., gt=0, description="Page number starting from 1"),
    brands: Optional[str] = Query(None),
    release_date_start: Optional[str] = Query(None),
    release_date_end: Optional[str] = Query(None)
) -> List[Dict[str, Any]]:
    """Step 5: Merge electronics API with brands API + all filters + pagination."""
    # Load data
    electronics = load_source_data()
    brands_data = load_brand_data()

    # Clean electronics
    products = []
    for item in electronics:
        if not isinstance(item, dict):
            continue
        if is_malformed(item):
            continue
        products.append(map_to_required_shape(item))

    # Apply filters
    products = filter_products(products, release_date_start, release_date_end, brands)

    # Paginate
    products = paginate(products, page_size, page_number)

    # Index brand info by name
    brand_lookup = {b.get("name"): b for b in brands_data if isinstance(b, dict)}

    # Merge
    merged = []
    for p in products:
        brand_info = brand_lookup.get(p["brand_name"])
        if brand_info:
            year_founded = brand_info.get("year_founded")
            company_age = None
            if isinstance(year_founded, int):
                company_age = datetime.now().year - year_founded

            address = brand_info.get("address", {})
            address_str = ", ".join([
                str(address.get("street", "")),
                str(address.get("city", "")),
                str(address.get("state", "")),
                str(address.get("postal_code", "")),
                str(address.get("country", "")),
            ])
            address_str = ", ".join([part for part in address_str.split(", ") if part and part.strip()])

            merged.append({
                "product_id": p["product_id"],
                "product_name": p["product_name"],
                "brand": {
                    "name": brand_info.get("name"),
                    "year_founded": year_founded,
                    "company_age": company_age,
                    "address": address_str
                },
                "category_name": p["category_name"],
                "description_text": p["description_text"],
                "price": p["price"],
                "currency": p["currency"],
                "processor": p["processor"],
                "memory": p["memory"],
                "release_date": p["release_date"],
                "average_rating": p["average_rating"],
                "rating_count": p["rating_count"]
            })
        else:
            # If brand missing in brands API, still return product with minimal info
            merged.append({
                **p,
                "brand": {
                    "name": p["brand_name"],
                    "year_founded": None,
                    "company_age": None,
                    "address": None
                }
            })

    return merged
