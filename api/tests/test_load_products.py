"""
Tests for the DigiKey product data loader.
Validates product loading, filtering, curation, and output format.
"""
import json
import os
import sys
from pathlib import Path

import pytest

# Add api directory to path so we can import the loader
sys.path.insert(0, str(Path(__file__).parent.parent))


# --- Fixtures ---

@pytest.fixture
def project_root():
    """Return the project root directory."""
    return Path(__file__).parent.parent.parent


@pytest.fixture
def reference_products_dir(project_root):
    """Return the reference products directory."""
    return project_root / ".reference" / "product-index" / "products"


@pytest.fixture
def reference_categories_file(project_root):
    """Return the reference categories file."""
    return project_root / ".reference" / "product-index" / "categories" / "categories.json"


# --- Test 1: load_all_products reads all reference JSON files ---

def test_load_all_products_returns_products(reference_products_dir):
    """Loading all products from reference files should return a non-empty list of product dicts."""
    from load_products import load_all_products

    products = load_all_products(reference_products_dir)
    assert isinstance(products, list)
    assert len(products) > 100, "Should load hundreds of products from reference files"
    # Each product should be a dict with expected DigiKey fields
    for product in products[:5]:
        assert "Description" in product
        assert "Manufacturer" in product
        assert "ManufacturerProductNumber" in product


# --- Test 2: filter_quality_products removes bad data ---

def test_filter_quality_products_removes_discontinued_and_missing_data():
    """Filtering should remove products that are discontinued, lack PhotoUrl, or lack Parameters."""
    from load_products import filter_quality_products

    good_product = {
        "Description": {"ProductDescription": "CAP CER 1UF", "DetailedDescription": "1uF Capacitor"},
        "Manufacturer": {"Id": 1, "Name": "TestMfg"},
        "ManufacturerProductNumber": "TEST-001",
        "UnitPrice": 0.10,
        "PhotoUrl": "https://example.com/photo.jpg",
        "Discontinued": False,
        "Parameters": [{"ParameterId": 1, "ParameterText": "Capacitance", "ValueText": "1uF"}],
        "ProductStatus": {"Id": 0, "Status": "Active"},
    }
    bad_no_photo = {
        "Description": {"ProductDescription": "BAD1", "DetailedDescription": "No photo"},
        "Manufacturer": {"Id": 2, "Name": "BadMfg"},
        "ManufacturerProductNumber": "BAD-001",
        "UnitPrice": 0.05,
        "PhotoUrl": "",
        "Discontinued": False,
        "Parameters": [{"ParameterId": 1, "ParameterText": "Test", "ValueText": "val"}],
        "ProductStatus": {"Id": 0, "Status": "Active"},
    }
    bad_discontinued = {
        "Description": {"ProductDescription": "BAD2", "DetailedDescription": "Discontinued"},
        "Manufacturer": {"Id": 3, "Name": "BadMfg2"},
        "ManufacturerProductNumber": "BAD-002",
        "UnitPrice": 0.15,
        "PhotoUrl": "https://example.com/photo2.jpg",
        "Discontinued": True,
        "Parameters": [{"ParameterId": 1, "ParameterText": "Test", "ValueText": "val"}],
        "ProductStatus": {"Id": 0, "Status": "Active"},
    }
    bad_no_params = {
        "Description": {"ProductDescription": "BAD3", "DetailedDescription": "No params"},
        "Manufacturer": {"Id": 4, "Name": "BadMfg3"},
        "ManufacturerProductNumber": "BAD-003",
        "UnitPrice": 0.20,
        "PhotoUrl": "https://example.com/photo3.jpg",
        "Discontinued": False,
        "Parameters": [],
        "ProductStatus": {"Id": 0, "Status": "Active"},
    }

    all_products = [good_product, bad_no_photo, bad_discontinued, bad_no_params]
    filtered = filter_quality_products(all_products)

    assert len(filtered) == 1
    assert filtered[0]["ManufacturerProductNumber"] == "TEST-001"


# --- Test 3: curate_products selects from representative categories ---

def test_curate_products_selects_representative_subset(reference_products_dir):
    """Curated subset should contain 50-75 products from 8-10 representative categories."""
    from load_products import load_all_products, filter_quality_products, curate_products

    all_products = load_all_products(reference_products_dir)
    quality_products = filter_quality_products(all_products)
    curated = curate_products(quality_products)

    assert isinstance(curated, list)
    assert 50 <= len(curated) <= 75, f"Expected 50-75 curated products, got {len(curated)}"

    # Verify products come from multiple category files (based on source_category tag)
    categories = set()
    for product in curated:
        if "_source_category" in product:
            categories.add(product["_source_category"])
    assert len(categories) >= 8, f"Expected at least 8 categories, got {len(categories)}"


# --- Test 4: output JSON is valid and has correct structure ---

def test_output_json_structure():
    """The generated products.json should be a valid JSON array of DigiKey product objects."""
    from load_products import build_output_products

    sample_product = {
        "Description": {"ProductDescription": "IC MCU 32BIT", "DetailedDescription": "ARM Cortex-M4"},
        "Manufacturer": {"Id": 497, "Name": "STMicroelectronics"},
        "ManufacturerProductNumber": "STM32F405RGT6",
        "UnitPrice": 12.50,
        "ProductUrl": "https://www.digikey.com/example",
        "DatasheetUrl": "https://example.com/datasheet.pdf",
        "PhotoUrl": "https://example.com/photo.jpg",
        "ProductVariations": [],
        "QuantityAvailable": 1000,
        "ProductStatus": {"Id": 0, "Status": "Active"},
        "Discontinued": False,
        "Parameters": [{"ParameterId": 1, "ParameterText": "Core", "ValueText": "ARM Cortex-M4"}],
        "_source_category": "integrated-circuits-ics",
    }

    output = build_output_products([sample_product])
    assert isinstance(output, list)
    assert len(output) == 1

    product = output[0]
    # Should retain core DigiKey fields
    assert "Description" in product
    assert "Manufacturer" in product
    assert "ManufacturerProductNumber" in product
    assert "UnitPrice" in product
    assert "PhotoUrl" in product
    # Internal metadata should be stripped
    assert "_source_category" not in product


# --- Test 5: end-to-end loader produces valid output file ---

def test_end_to_end_loader_writes_valid_json(project_root, tmp_path):
    """Running the full loader should produce a valid JSON file with curated products."""
    from load_products import run_loader

    output_file = tmp_path / "products.json"
    run_loader(
        products_dir=project_root / ".reference" / "product-index" / "products",
        output_path=output_file,
    )

    assert output_file.exists()
    data = json.loads(output_file.read_text())
    assert isinstance(data, list)
    assert 50 <= len(data) <= 75, f"Expected 50-75 products, got {len(data)}"

    # Validate each product is valid JSON with required fields
    for product in data:
        assert "Description" in product
        assert "ProductDescription" in product["Description"]
        assert "Manufacturer" in product
        assert "ManufacturerProductNumber" in product
        assert "UnitPrice" in product
        assert "PhotoUrl" in product
        assert product["PhotoUrl"], "PhotoUrl should not be empty"
