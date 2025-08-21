import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, Query, HTTPException

app = FastAPI(title="Product APIs – Step 1 & Step 2")

EXTERNAL_API_URL = os.getenv("EXTERNAL_API_URL")  # optional
LOCAL_SAMPLE_PATH = os.getenv("LOCAL_SAMPLE_PATH", "sample_electronics.json")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

REQUIRED_SOURCE_FIELDS = [
    "productId", "productName", "brandName", "category", "description", "price",
    "currency", "processor", "memory", "releaseDate", "averageRating", "ratingCount"
]


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def load_source_data() -> List[Dict[str, Any]]:
    """
    Loads data from the external API if EXTERNAL_API_URL is set,
    otherwise from local sample_electronics.json.
    """
    if EXTERNAL_API_URL:
        try:
            resp = requests.get(EXTERNAL_API_URL, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Failed to fetch external API: {e}")
    else:
        if not os.path.exists(LOCAL_SAMPLE_PATH):
            raise HTTPException(
                status_code=500,
                detail=f"Local sample file not found at '{LOCAL_SAMPLE_PATH}'."
            )
        with open(LOCAL_SAMPLE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

    if not isinstance(data, list):
        raise HTTPException(status_code=502, detail="Source did not return a list.")
    return data


def is_malformed(item: Dict[str, Any]) -> bool:
    """
    Step 1: Filter out malformed items.
    """
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
    """
    Step 1: Map source keys to required shape.
    """
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
# Routes
# -------------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "Backend running. Use /step1 or /step2 to fetch products."}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/step1")
def step1() -> List[Dict[str, Optional[Any]]]:
    """
    Step 1:
      - Call source (API or local file)
      - Filter out malformed items
      - Return only required fields
    """
    data = load_source_data()

    cleaned: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if is_malformed(item):
            continue
        cleaned.append(map_to_required_shape(item))

    return cleaned


@app.get("/step2")
def step2(
    release_date_start: Optional[str] = Query(None),
    release_date_end: Optional[str] = Query(None)
) -> List[Dict[str, Any]]:
    """
    Step 2:
      - Filter products by release_date range
      - Params: release_date_start, release_date_end
    """
    data = step1()  # reuse cleaned Step 1 data

    try:
        start_date = (
            datetime.strptime(release_date_start, "%Y-%m-%d")
            if release_date_start else None
        )
        end_date = (
            datetime.strptime(release_date_end, "%Y-%m-%d")
            if release_date_end else None
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    filtered_products = []
    for product in data:
        if not product.get("release_date"):
            continue
        try:
            product_date = datetime.strptime(product["release_date"], "%Y-%m-%d")
        except ValueError:
            continue

        if start_date and product_date < start_date:
            continue
        if end_date and product_date > end_date:
            continue

        filtered_products.append(product)

    return filtered_products
