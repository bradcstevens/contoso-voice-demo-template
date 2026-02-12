#!/usr/bin/env python3
"""
Curate DigiKey product data for the frontend store.

Reads products from .reference/product-index/products/ and selects
representative products for 8 key categories. Outputs curated JSON files
to web/public/ for the Next.js frontend.

Usage:
    python scripts/curate_frontend_products.py
"""

import json
import os
import re
import sys

# Resolve paths relative to project root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
PRODUCTS_DIR = os.path.join(PROJECT_ROOT, ".reference", "product-index", "products")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "web", "public")

# Target categories: display name -> source filename
CATEGORIES = {
    "Capacitors": {
        "file": "capacitors.json",
        "description": "Essential passive components for energy storage, filtering, and decoupling in electronic circuits. From tiny 0402 ceramic capacitors to large electrolytics, find the right capacitor for your design.",
        "pick_count": 4,
    },
    "Resistors": {
        "file": "resistors.json",
        "description": "Fundamental components for controlling current flow and voltage division. Available in a wide range of values, tolerances, and packages for every application.",
        "pick_count": 4,
    },
    "Integrated Circuits (ICs)": {
        "file": "integrated-circuits-ics.json",
        "description": "The brains of electronic systems. From simple logic gates and op-amps to complex microcontrollers and FPGAs, find the ICs that power your designs.",
        "pick_count": 4,
    },
    "Connectors & Interconnects": {
        "file": "connectors-interconnects.json",
        "description": "Reliable connections for every interface. Board-to-board, wire-to-board, and cable assemblies from leading manufacturers to keep your designs connected.",
        "pick_count": 4,
    },
    "Development Boards & Kits": {
        "file": "development-boards-kits-programmers.json",
        "description": "Accelerate prototyping with evaluation boards, development kits, and programmers. From Arduino and Raspberry Pi to manufacturer-specific evaluation platforms.",
        "pick_count": 4,
    },
    "Sensors & Transducers": {
        "file": "sensors-transducers.json",
        "description": "Convert physical phenomena into electrical signals. Temperature sensors, accelerometers, pressure sensors, and more for IoT, industrial, and consumer applications.",
        "pick_count": 4,
    },
    "LEDs & Optoelectronics": {
        "file": "optoelectronics.json",
        "description": "Light up your designs with LEDs, displays, photodiodes, and optocouplers. From indicator LEDs to high-power illumination, find the right optoelectronic solution.",
        "pick_count": 4,
    },
    "Switches": {
        "file": "switches.json",
        "description": "Tactile, toggle, slide, and rotary switches for user interfaces and circuit control. Reliable mechanical and electronic switching solutions for any application.",
        "pick_count": 4,
    },
}

# Products to feature as trending (hand-picked for interesting variety)
# We'll select these by matching keywords after loading
TRENDING_KEYWORDS = [
    # A dev board (Arduino, Raspberry Pi, etc.)
    {"category": "Development Boards & Kits", "keywords": ["arduino", "raspberry", "esp32", "eval", "development", "board"], "fallback_index": 0},
    # A microcontroller IC
    {"category": "Integrated Circuits (ICs)", "keywords": ["microcontroller", "mcu", "processor", "stm32", "atmega", "pic"], "fallback_index": 0},
    # A capacitor (common/popular)
    {"category": "Capacitors", "keywords": ["100nf", "0.1uf", "100uf", "10uf", "ceramic", "mlcc"], "fallback_index": 1},
    # A sensor
    {"category": "Sensors & Transducers", "keywords": ["temperature", "humidity", "accelerometer", "pressure", "sensor"], "fallback_index": 0},
    # An LED
    {"category": "LEDs & Optoelectronics", "keywords": ["led", "white", "rgb", "smd"], "fallback_index": 0},
    # A switch
    {"category": "Switches", "keywords": ["tactile", "push", "button", "switch"], "fallback_index": 0},
]


def load_products(filename):
    """Load products from a reference JSON file."""
    filepath = os.path.join(PRODUCTS_DIR, filename)
    if not os.path.exists(filepath):
        print(f"WARNING: {filepath} not found, skipping")
        return []
    with open(filepath) as f:
        data = json.load(f)
    return data.get("Products", [])


def is_good_product(product):
    """Check if a product is suitable for frontend display."""
    # Must have a photo
    if not product.get("PhotoUrl"):
        return False
    # Must not be discontinued or end-of-life
    if product.get("Discontinued") or product.get("EndOfLife"):
        return False
    # Prefer active status
    status = product.get("ProductStatus", {}).get("Status", "")
    if status in ("Obsolete",):
        return False
    # Must have a description
    desc = product.get("Description", {})
    if not desc.get("ProductDescription"):
        return False
    return True


def score_product(product):
    """Score a product for selection priority. Higher is better."""
    score = 0
    # Prefer products with more parameters (richer data)
    params = product.get("Parameters", [])
    score += min(len(params), 10) * 2

    # Prefer products with a photo
    if product.get("PhotoUrl"):
        score += 10

    # Prefer active status
    status = product.get("ProductStatus", {}).get("Status", "")
    if status == "Active":
        score += 5

    # Prefer products that are normally stocking
    if product.get("NormallyStocking"):
        score += 3

    # Prefer products with higher availability (popular items)
    qty = product.get("QuantityAvailable", 0)
    if qty > 1000000:
        score += 3
    elif qty > 100000:
        score += 2
    elif qty > 10000:
        score += 1

    # Prefer products with a datasheet URL
    if product.get("DatasheetUrl"):
        score += 2

    # Prefer products with unit price > 0 (has pricing)
    if product.get("UnitPrice", 0) > 0:
        score += 2

    return score


def select_products(products, count):
    """Select the best products from a list."""
    good = [p for p in products if is_good_product(p)]
    if not good:
        return products[:count]

    # Sort by score descending, then take top N
    good.sort(key=score_product, reverse=True)

    # Try to get variety by picking from different manufacturers
    selected = []
    seen_manufacturers = set()
    for p in good:
        mfg = p.get("Manufacturer", {}).get("Name", "")
        if mfg not in seen_manufacturers or len(selected) >= count:
            selected.append(p)
            seen_manufacturers.add(mfg)
        if len(selected) >= count:
            break

    # If we still need more, fill from remaining good products
    if len(selected) < count:
        for p in good:
            if p not in selected:
                selected.append(p)
            if len(selected) >= count:
                break

    return selected[:count]


def category_name_to_slug(name):
    """Convert category name to URL-friendly slug."""
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def find_trending_product(category_products, keywords, fallback_index=0):
    """Find a product matching keywords for trending section."""
    for product in category_products:
        desc = product.get("Description", {})
        full_text = " ".join([
            desc.get("ProductDescription", ""),
            desc.get("DetailedDescription", ""),
            product.get("ManufacturerProductNumber", ""),
            product.get("Manufacturer", {}).get("Name", ""),
        ]).lower()
        for kw in keywords:
            if kw.lower() in full_text:
                return product
    # Fallback: return product at given index
    if category_products and fallback_index < len(category_products):
        return category_products[fallback_index]
    return None


def strip_extra_fields(product):
    """Keep only the fields defined in our DigiKeyProduct TypeScript interface."""
    return {
        "Description": product.get("Description", {}),
        "Manufacturer": product.get("Manufacturer", {}),
        "ManufacturerProductNumber": product.get("ManufacturerProductNumber", ""),
        "UnitPrice": product.get("UnitPrice", 0),
        "ProductUrl": product.get("ProductUrl", ""),
        "DatasheetUrl": product.get("DatasheetUrl", ""),
        "PhotoUrl": product.get("PhotoUrl", ""),
        "ProductVariations": product.get("ProductVariations", []),
        "QuantityAvailable": product.get("QuantityAvailable", 0),
        "ProductStatus": product.get("ProductStatus", {}),
        "BackOrderNotAllowed": product.get("BackOrderNotAllowed", False),
        "NormallyStocking": product.get("NormallyStocking", True),
        "Discontinued": product.get("Discontinued", False),
        "EndOfLife": product.get("EndOfLife", False),
        "Ncnr": product.get("Ncnr", False),
        "PrimaryVideoUrl": product.get("PrimaryVideoUrl", ""),
        "Parameters": product.get("Parameters", []),
    }


def main():
    print("Curating DigiKey products for frontend...")
    print(f"Source: {PRODUCTS_DIR}")
    print(f"Output: {OUTPUT_DIR}")
    print()

    all_products = []
    categories_output = []
    manufacturers_set = {}
    category_products_map = {}  # For trending selection

    for cat_name, config in CATEGORIES.items():
        print(f"Processing {cat_name}...")
        raw_products = load_products(config["file"])
        if not raw_products:
            print(f"  WARNING: No products found, skipping")
            continue

        selected = select_products(raw_products, config["pick_count"])
        cleaned = [strip_extra_fields(p) for p in selected]

        slug = category_name_to_slug(cat_name)
        print(f"  Selected {len(cleaned)} products (from {len(raw_products)} total)")

        # Extract DigiKey category info from first product if available
        raw_category = raw_products[0].get("Category", {}) if raw_products else {}
        category_id = raw_category.get("CategoryId", 0)
        parent_id = raw_category.get("ParentId", 0)

        categories_output.append({
            "name": cat_name,
            "slug": slug,
            "description": config["description"],
            "categoryId": category_id,
            "parentId": parent_id,
            "productCount": len(cleaned),
        })

        # Track all products and category mapping
        all_products.extend(cleaned)
        category_products_map[cat_name] = cleaned

        # Collect manufacturers
        for p in cleaned:
            mfg = p.get("Manufacturer", {})
            mfg_id = mfg.get("Id", 0)
            if mfg_id and mfg_id not in manufacturers_set:
                manufacturers_set[mfg_id] = {
                    "Id": mfg_id,
                    "Name": mfg.get("Name", "Unknown"),
                }

    # Select trending products
    print()
    print("Selecting trending products...")
    trending = []
    trending_part_numbers = set()
    for spec in TRENDING_KEYWORDS:
        cat_prods = category_products_map.get(spec["category"], [])
        product = find_trending_product(cat_prods, spec["keywords"], spec.get("fallback_index", 0))
        if product and product.get("ManufacturerProductNumber") not in trending_part_numbers:
            trending.append(strip_extra_fields(product))
            trending_part_numbers.add(product.get("ManufacturerProductNumber"))
            print(f"  Trending: {product.get('ManufacturerProductNumber')} ({spec['category']})")

    # Write output files
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # products.json - all curated products with a _category field for the store
    products_with_category = []
    for cat_name, config in CATEGORIES.items():
        slug = category_name_to_slug(cat_name)
        for p in category_products_map.get(cat_name, []):
            product_entry = strip_extra_fields(p)
            product_entry["_category"] = slug
            product_entry["_categoryName"] = cat_name
            products_with_category.append(product_entry)

    products_output_path = os.path.join(OUTPUT_DIR, "products.json")
    with open(products_output_path, "w") as f:
        json.dump(products_with_category, f, indent=2)
    print(f"\nWrote {len(products_with_category)} products to {products_output_path}")

    # categories.json - category listing
    categories_output_path = os.path.join(OUTPUT_DIR, "categories.json")
    with open(categories_output_path, "w") as f:
        json.dump(categories_output, f, indent=2)
    print(f"Wrote {len(categories_output)} categories to {categories_output_path}")

    # manufacturers.json - replaces brands.json
    manufacturers_list = sorted(manufacturers_set.values(), key=lambda m: m["Name"])
    manufacturers_output_path = os.path.join(OUTPUT_DIR, "manufacturers.json")
    with open(manufacturers_output_path, "w") as f:
        json.dump(manufacturers_list, f, indent=2)
    print(f"Wrote {len(manufacturers_list)} manufacturers to {manufacturers_output_path}")

    # trending.json - trending product selection
    trending_output_path = os.path.join(OUTPUT_DIR, "trending.json")
    with open(trending_output_path, "w") as f:
        json.dump(trending, f, indent=2)
    print(f"Wrote {len(trending)} trending products to {trending_output_path}")

    print("\nDone!")


if __name__ == "__main__":
    main()
