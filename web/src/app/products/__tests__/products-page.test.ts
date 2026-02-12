/**
 * Tests for the Products Catalog Page (Task 18).
 * Verifies that the products page and its CSS module are correctly
 * structured to display a multi-column product index with DigiKey styling.
 */
import { describe, it, expect, beforeAll } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

const productsDir = resolve(__dirname, "..");
let pageContent: string;
let cssContent: string;

beforeAll(() => {
  const pagePath = resolve(productsDir, "page.tsx");
  const cssPath = resolve(productsDir, "page.module.css");
  pageContent = readFileSync(pagePath, "utf-8");
  cssContent = readFileSync(cssPath, "utf-8");
});

describe("Products Catalog Page - page.tsx", () => {
  // Test 1: Page file exists and imports required shared components and data
  it("imports Header, Footer, getCategories, and Link", () => {
    expect(pageContent).toContain('import Header from "@/components/header"');
    expect(pageContent).toContain('import Footer from "@/components/footer"');
    expect(pageContent).toContain('import { getCategories } from "@/store/products"');
    expect(pageContent).toContain('import Link from "next/link"');
  });

  // Test 2: Page renders Header, breadcrumb, page title, category grid, and Footer
  it("renders Header, breadcrumb, Product Index title, category grid, and Footer", () => {
    expect(pageContent).toContain("<Header");
    expect(pageContent).toContain("<Footer");
    expect(pageContent).toContain("Product Index");
    // Should have a breadcrumb area
    expect(pageContent).toMatch(/breadcrumb/i);
    // Should iterate over categories to render them
    expect(pageContent).toMatch(/categories\.map/);
  });

  // Test 3: Each category renders its name and product links
  it("renders category names as headings and product links underneath", () => {
    // Category name should be rendered (from category.name)
    expect(pageContent).toMatch(/category\.name/);
    // Product links should use Link component with product info
    expect(pageContent).toMatch(/category\.products\.map/);
    // Each product link should display product description or manufacturer part number
    expect(pageContent).toMatch(/ManufacturerProductNumber|ProductDescription/);
  });

  // Test 4: Uses CSS Modules (not Tailwind) with page.module.css import
  it("uses CSS Modules for styling", () => {
    expect(pageContent).toContain('import styles from "./page.module.css"');
    // Should reference styles.something in JSX
    expect(pageContent).toMatch(/styles\.\w+/);
    // Should NOT contain Tailwind class patterns
    expect(pageContent).not.toMatch(/className="[^"]*\b(flex|grid|p-|m-|text-|bg-)\b/);
  });
});

describe("Products Catalog Page - page.module.css", () => {
  // Test 5: CSS module defines multi-column grid layout and DigiKey brand colors
  it("defines multi-column category grid with DigiKey brand styling", () => {
    // Should define a grid or multi-column layout for categories
    expect(cssContent).toMatch(/grid-template-columns|column-count|columns/);
    // Should use DigiKey brand variables
    expect(cssContent).toMatch(/var\(--dk-(red|blue|border|gray-bg)\)/);
    // Should have a page container or wrapper class
    expect(cssContent).toMatch(/\.(page|container|wrapper|content)/);
    // Should have a category-related class
    expect(cssContent).toMatch(/\.(category|categoryGroup|categoryCard|categoryItem)/i);
  });
});
