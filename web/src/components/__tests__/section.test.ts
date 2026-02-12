import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";
import { getCategories } from "../../store/products";

/**
 * Section Component - Unit Tests
 *
 * Validates that the Section component and its CSS module follow
 * the DigiKey catalog card-grid design: clean white background,
 * product cards with borders, and brand-color headings.
 */

const sectionCss = fs.readFileSync(
  path.resolve(__dirname, "../section.module.css"),
  "utf-8"
);

const sectionTsx = fs.readFileSync(
  path.resolve(__dirname, "../section.tsx"),
  "utf-8"
);

describe("Section component - DigiKey catalog card grid", () => {
  it("should NOT use alternating blue/white background pattern", () => {
    // The old design used .oddSection with sky-900 and .evenSection with zinc-50
    // The new design uses a consistent white background for all sections
    expect(sectionCss).not.toMatch(/--color-sky-900/);
    expect(sectionCss).not.toMatch(/oddSection/);
    expect(sectionCss).not.toMatch(/evenSection/);
    // Component should not use index-based alternating logic
    expect(sectionTsx).not.toMatch(/oddSection/);
    expect(sectionTsx).not.toMatch(/evenSection/);
    expect(sectionTsx).not.toMatch(/index\s*%\s*2/);
  });

  it("should use DigiKey brand CSS variables for styling", () => {
    // Section CSS must reference DigiKey brand tokens, not generic Tailwind-style vars
    expect(sectionCss).toMatch(/var\(--dk-border\)/);
    expect(sectionCss).toMatch(/var\(--dk-blue\)/);
    expect(sectionCss).toMatch(/var\(--dk-dark\)/);
  });

  it("should define product card styles with border and hover shadow", () => {
    // Product cards must have a bordered card appearance (matching featured-products pattern)
    expect(sectionCss).toMatch(/\.productCard\s*\{/);
    expect(sectionCss).toMatch(/border.*var\(--dk-border\)/);
    expect(sectionCss).toMatch(/box-shadow/);
  });

  it("should provide category data with products for each section", () => {
    const categories = getCategories();
    expect(categories.length).toBeGreaterThan(0);

    for (const category of categories) {
      expect(category.name).toBeTruthy();
      expect(category.slug).toBeTruthy();
      expect(category.products.length).toBeGreaterThan(0);

      // Each product must have the fields the card displays
      for (const product of category.products) {
        expect(product.ManufacturerProductNumber).toBeTruthy();
        expect(product.Manufacturer.Name).toBeTruthy();
        expect(typeof product.UnitPrice).toBe("number");
      }
    }
  });

  it("should include responsive breakpoints for card grid", () => {
    // Must have at least one @media rule for responsive card widths
    expect(sectionCss).toMatch(/@media\s*\(/);
    // Cards should adapt at mobile widths
    expect(sectionCss).toMatch(/max-width:\s*768px/);
  });
});
