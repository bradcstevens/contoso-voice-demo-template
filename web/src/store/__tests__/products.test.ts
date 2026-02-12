/**
 * Tests for the DigiKey product store.
 * Verifies the store correctly loads and exposes DigiKey product data
 * with the expected API surface for frontend components.
 */
import { describe, it, expect } from "vitest";

// We test the store by importing it directly
// The store reads from JSON files in web/public/
import {
  getCategories,
  getTrendingProducts,
  getProductsByCategory,
} from "../products";

describe("DigiKey Product Store", () => {
  // Test 1: getCategories returns CategoryWithProducts[] with correct structure
  it("returns 8 categories with products in CategoryWithProducts format", () => {
    const categories = getCategories();
    expect(categories).toHaveLength(8);

    // Each category must have the CategoryWithProducts shape
    for (const cat of categories) {
      expect(cat).toHaveProperty("name");
      expect(cat).toHaveProperty("slug");
      expect(cat).toHaveProperty("description");
      expect(cat).toHaveProperty("products");
      expect(typeof cat.name).toBe("string");
      expect(typeof cat.slug).toBe("string");
      expect(typeof cat.description).toBe("string");
      expect(Array.isArray(cat.products)).toBe(true);
      expect(cat.products.length).toBeGreaterThanOrEqual(3);
      expect(cat.products.length).toBeLessThanOrEqual(5);
    }
  });

  // Test 2: Products have DigiKeyProduct structure
  it("returns products with DigiKeyProduct fields", () => {
    const categories = getCategories();
    const product = categories[0].products[0];

    // Core DigiKeyProduct fields
    expect(product).toHaveProperty("Description");
    expect(product.Description).toHaveProperty("ProductDescription");
    expect(product).toHaveProperty("Manufacturer");
    expect(product.Manufacturer).toHaveProperty("Name");
    expect(product).toHaveProperty("ManufacturerProductNumber");
    expect(product).toHaveProperty("UnitPrice");
    expect(product).toHaveProperty("PhotoUrl");
    expect(product).toHaveProperty("Parameters");
    expect(Array.isArray(product.Parameters)).toBe(true);
  });

  // Test 3: getTrendingProducts returns a limited set of diverse products
  it("returns trending products with correct default limit", () => {
    const trending = getTrendingProducts();
    expect(trending.length).toBeGreaterThanOrEqual(1);
    expect(trending.length).toBeLessThanOrEqual(6);

    // Each trending product should be a valid DigiKeyProduct
    for (const product of trending) {
      expect(product).toHaveProperty("ManufacturerProductNumber");
      expect(product).toHaveProperty("PhotoUrl");
      expect(typeof product.ManufacturerProductNumber).toBe("string");
    }
  });

  // Test 4: getTrendingProducts respects limit parameter
  it("respects the limit parameter for trending products", () => {
    const limited = getTrendingProducts(3);
    expect(limited.length).toBeLessThanOrEqual(3);
  });

  // Test 5: getProductsByCategory returns products for a valid slug
  it("returns products for a valid category slug", () => {
    const categories = getCategories();
    const firstSlug = categories[0].slug;

    const products = getProductsByCategory(firstSlug);
    expect(products.length).toBeGreaterThan(0);
    // Products returned should match the category
    expect(products).toEqual(categories[0].products);
  });
});
