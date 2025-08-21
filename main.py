import json
import os
import re
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
import requests

app = FastAPI(title="Product APIs – Step 1")
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
        # The assignment states the API returns a list of product items
        raise HTTPException(status_code=502, detail="Source did not return a list.")
    return data


def is_malformed(item: Dict[str, Any]) -> bool:
    """
    Step-1 asks us to filter out outright errors/malformed items.
    We keep nulls (return as null) but:
      - If a required key is completely missing, it's malformed.
      - If releaseDate is present and not in 'YYYY-MM-DD' format, it's malformed.
      - If price is present and not a number, it's malformed.
      - If averageRating is present and not a number in [0,5], it's malformed.
      - If ratingCount is present and not a non-negative int, it's malformed.
    """
    # Must contain all required keys (values can be None)
    for k in REQUIRED_SOURCE_FIELDS:
        if k not in item:
            return True

    # Validate formats/ranges ONLY when values are not None
    release_date = item.get("releaseDate")
    if release_date is not None and not (isinstance(release_date, str) and DATE_RE.match(release_date)):
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

    # Everything else passes (even if None)
    return False


def map_to_required_shape(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map source keys -> exact casing required by the assignment.
    Return only those fields; keep values exactly as received (including None).
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
    return {"message": "Backend running. Use /step1 to fetch products."}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/step1")
def step1() -> List[Dict[str, Optional[Any]]]:
    """
    Step 1:
      - Call source (external API or local sample file)
      - Filter out malformed/error items
      - Return ONLY the specified fields, exact casing, values unchanged
      - Preserve formats (e.g., release_date stays 'YYYY-MM-DD' if provided)
      - Keep nulls as null
      - Return a LIST of items (array), not wrapped
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
