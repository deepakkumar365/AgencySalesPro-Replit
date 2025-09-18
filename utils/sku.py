import re
from typing import Optional
from app import db
from models import Product, Category, UOM

# Helpers to normalize strings to 3-4 letter codes

def _slug3(value: Optional[str]) -> str:
    if not value:
        return "XXX"
    s = re.sub(r"[^A-Za-z0-9]", "", value).upper()
    return (s[:3] if len(s) >= 3 else s.ljust(3, 'X'))


def _slug4(value: Optional[str]) -> str:
    if not value:
        return "XXXX"
    s = re.sub(r"[^A-Za-z0-9]", "", value).upper()
    return (s[:4] if len(s) >= 4 else s.ljust(4, 'X'))


def generate_sku(name: str,
                  category_id: Optional[int] = None,
                  uom_id: Optional[int] = None) -> str:
    """
    Generate SKU using logic:
    - 3-letter category short code (or from category name)
    - 3-letter UOM short code
    - 3-4 letters from product name
    - Numeric suffix to ensure uniqueness
    Format: CAT-UOM-NAM-####
    """
    # Derive category code
    cat_code = "CAT"
    if category_id:
        cat = Category.query.get(category_id)
        if cat:
            cat_code = (cat.short_name or _slug3(cat.name or "CAT"))[:3].upper()
    else:
        cat_code = "CAT"

    # Derive UOM code
    uom_code = "UOM"
    if uom_id:
        uom = UOM.query.get(uom_id)
        if uom:
            uom_code = (uom.short_name or _slug3(uom.name or "UOM"))[:3].upper()
    else:
        uom_code = "UOM"

    # Name part
    name_code = _slug4(name)

    base = f"{cat_code}-{uom_code}-{name_code}"

    # Find next available numeric suffix (0001..)
    # Query existing SKUs that start with base-
    like_pattern = f"{base}-%"
    existing = db.session.query(Product.sku).filter(Product.sku.like(like_pattern)).all()
    taken = set()
    for (sku_val,) in existing:
        m = re.search(r"-(\d{3,6})$", sku_val)
        if m:
            taken.add(int(m.group(1)))

    suffix = 1
    while suffix in taken:
        suffix += 1
    sku = f"{base}-{suffix:04d}"

    # Final guard: if even base without suffix is free and no existing found, still return with suffix for consistency
    # Ensure absolute uniqueness
    while Product.query.filter_by(sku=sku).first() is not None:
        suffix += 1
        sku = f"{base}-{suffix:04d}"

    return sku