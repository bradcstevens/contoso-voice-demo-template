/**
 * Tests for the Category Detail Page (Task 19).
 * Verifies that the category page and its CSS module are correctly
 * structured to display a product grid with DigiKey styling.
 */
import { describe, it, expect, beforeAll } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

const categoryDir = resolve(__dirname, "..");
let pageContent: string;
let cssContent: string;

beforeAll(() => {
  const pagePath = resolve(categoryDir, "page.tsx");
  const cssPath = resolve(categoryDir, "page.module.css");
  pageContent = readFileSync(pagePath, "utf-8");
  cssContent = readFileSync(cssPath, "utf-8");
});

describe("Category Detail Page - page.tsx", () => {
  // Test 1: Imports required shared components, data functions, and types
  it("imports Header, Footer, data functions, and uses CSS Modules", () => {
    expect(pageContent).toContain('import Header from "@/components/header"');
    expect(pageContent).toContain('import Footer from "@/components/footer"');
    expect(pageContent).toContain("getCategories");
    expect(pageContent).toContain("getProductsByCategory");
    expect(pageContent).toContain('import styles from "./page.module.css"');
  });

  // Test 2: Renders breadcrumb, category title with count, product grid, and not-found handling
  it("renders breadcrumb, category title with count, product grid, and not-found case", () => {
    // Should render a breadcrumb navigation with Home > Products > Category
    expect(pageContent).toMatch(/breadcrumb/i);
    expect(pageContent).toContain("Home");
    expect(pageContent).toContain("/products");

    // Should display category name and product count (e.g., "XX results")
    expect(pageContent).toMatch(/results|Results/);

    // Should iterate products to render a grid
    expect(pageContent).toMatch(/products\.map|\.map\(/);

    // Should handle not-found / invalid category
    expect(pageContent).toMatch(/not found|notFound|Category not found/i);
  });

  // Test 3: Product cards display part number, manufacturer, description, and price
  it("renders product card details: part number, manufacturer, description, price", () => {
    expect(pageContent).toMatch(/ManufacturerProductNumber/);
    expect(pageContent).toMatch(/Manufacturer\.Name|Manufacturer/);
    expect(pageContent).toMatch(/ProductDescription|Description/);
    expect(pageContent).toMatch(/UnitPrice|formatElectronicsPrice/);
  });

  // Test 4: Uses CSS Modules (not Tailwind) and does not contain Tailwind patterns
  it("uses CSS Modules and avoids Tailwind utility classes", () => {
    expect(pageContent).toContain('import styles from "./page.module.css"');
    expect(pageContent).toMatch(/styles\.\w+/);
    expect(pageContent).not.toMatch(/className="[^"]*\b(flex|grid|p-|m-|text-|bg-)\b/);
  });
});

describe("Category Detail Page - page.module.css", () => {
  // Test 5: CSS module defines product grid layout, card styles, and DigiKey brand colors
  it("defines product grid, card styles, and uses DigiKey brand variables", () => {
    // Should have a product grid layout
    expect(cssContent).toMatch(/grid-template-columns|display:\s*grid/);
    // Should use DigiKey brand variables
    expect(cssContent).toMatch(/var\(--dk-(red|blue|border|gray-bg)\)/);
    // Should have product card class
    expect(cssContent).toMatch(/\.(productCard|card|product)/i);
    // Should have breadcrumb styling
    expect(cssContent).toMatch(/\.breadcrumb/);
    // Should include responsive breakpoints
    expect(cssContent).toMatch(/@media/);
  });
});
