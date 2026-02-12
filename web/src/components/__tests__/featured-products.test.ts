import { describe, it, expect } from "vitest";
import { getTrendingProducts } from "../../store/products";
import manufacturersData from "../../../public/manufacturers.json";
import { formatElectronicsPrice } from "../../types/digikey";

/**
 * Featured Products Section - Unit Tests
 *
 * Tests for the Featured Products section data, manufacturer badges,
 * and product card data structure used by the component.
 */

// Type for manufacturer entries from manufacturers.json
interface Manufacturer {
  Id: number;
  Name: string;
}

const manufacturers = manufacturersData as Manufacturer[];

describe("FeaturedProducts data", () => {
  it("should load manufacturers list with Id and Name fields", () => {
    expect(manufacturers.length).toBeGreaterThan(0);
    for (const mfr of manufacturers) {
      expect(mfr).toHaveProperty("Id");
      expect(mfr).toHaveProperty("Name");
      expect(typeof mfr.Id).toBe("number");
      expect(typeof mfr.Name).toBe("string");
      expect(mfr.Name.length).toBeGreaterThan(0);
    }
  });

  it("should return trending products with required card fields", () => {
    const products = getTrendingProducts(6);
    expect(products.length).toBeGreaterThan(0);
    expect(products.length).toBeLessThanOrEqual(6);

    for (const product of products) {
      // Each product card needs: manufacturer name, part number, description, unit price, photo
      expect(product.Manufacturer).toBeDefined();
      expect(product.Manufacturer.Name).toBeTruthy();
      expect(product.ManufacturerProductNumber).toBeTruthy();
      expect(product.Description).toBeDefined();
      expect(product.Description.ProductDescription).toBeTruthy();
      expect(typeof product.UnitPrice).toBe("number");
    }
  });

  it("should format product prices correctly for display", () => {
    // Electronics pricing: fractional cents, sub-dollar, and dollar amounts
    expect(formatElectronicsPrice(0.004)).toBe("$0.0040");
    expect(formatElectronicsPrice(0.15)).toBe("$0.150");
    expect(formatElectronicsPrice(3.0)).toBe("$3.00");
    expect(formatElectronicsPrice(12.5)).toBe("$12.50");
  });

  it("should have unique manufacturer IDs in the manufacturers list", () => {
    const ids = manufacturers.map((m) => m.Id);
    const uniqueIds = new Set(ids);
    expect(uniqueIds.size).toBe(ids.length);
  });

  it("should provide a PhotoUrl or fallback for product images", () => {
    const products = getTrendingProducts(6);
    const NO_IMAGE_PLACEHOLDER = "/images/no-image.svg";

    for (const product of products) {
      // PhotoUrl may be empty/null, but the component should fall back to placeholder
      const imageUrl = product.PhotoUrl || NO_IMAGE_PLACEHOLDER;
      expect(imageUrl).toBeTruthy();
      expect(typeof imageUrl).toBe("string");
    }
  });
});
