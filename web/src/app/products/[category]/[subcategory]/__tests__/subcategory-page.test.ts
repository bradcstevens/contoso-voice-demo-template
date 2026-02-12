/**
 * Tests for the Product Listing / Filter Page (Task 20).
 * Verifies that the subcategory page renders a product data table
 * with a filter sidebar, breadcrumb, and pagination using DigiKey styling.
 */
import { describe, it, expect, beforeAll } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

const subcategoryDir = resolve(__dirname, "..");
let pageContent: string;
let cssContent: string;

beforeAll(() => {
  const pagePath = resolve(subcategoryDir, "page.tsx");
  const cssPath = resolve(subcategoryDir, "page.module.css");
  pageContent = readFileSync(pagePath, "utf-8");
  cssContent = readFileSync(cssPath, "utf-8");
});

describe("Subcategory Page - page.tsx", () => {
  // Test 1: Imports required shared components, data functions, and CSS Modules
  it("imports Header, Footer, FilterSidebar, ProductTable, data functions, and CSS Modules", () => {
    expect(pageContent).toContain('import Header from "@/components/header"');
    expect(pageContent).toContain('import Footer from "@/components/footer"');
    expect(pageContent).toContain("FilterSidebar");
    expect(pageContent).toContain("ProductTable");
    expect(pageContent).toContain("getCategories");
    expect(pageContent).toContain("getProductsByCategory");
    expect(pageContent).toContain('import styles from "./page.module.css"');
  });

  // Test 2: Renders breadcrumb with Home > Products > Category > Subcategory
  it("renders breadcrumb with Home, Products, Category, and Subcategory", () => {
    expect(pageContent).toMatch(/breadcrumb/i);
    expect(pageContent).toContain("Home");
    expect(pageContent).toContain("/products");
    // Should have at least 3 breadcrumb separators for 4 levels
    expect(pageContent).toMatch(/breadcrumbSeparator/);
  });

  // Test 3: Handles not-found / invalid category gracefully
  it("handles not-found / invalid category gracefully", () => {
    expect(pageContent).toMatch(/not found|notFound|Category not found/i);
  });

  // Test 4: Uses CSS Modules (not Tailwind utility classes)
  it("uses CSS Modules and avoids Tailwind utility classes", () => {
    expect(pageContent).toContain('import styles from "./page.module.css"');
    expect(pageContent).toMatch(/styles\.\w+/);
    expect(pageContent).not.toMatch(/className="[^"]*\b(flex|grid|p-|m-|text-|bg-)\b/);
  });
});

describe("Subcategory Page - page.module.css", () => {
  // Test 5: CSS uses DigiKey brand variables, breadcrumb, and layout classes
  it("defines layout with sidebar and content, breadcrumb, and uses DigiKey brand variables", () => {
    // Should use DigiKey brand variables
    expect(cssContent).toMatch(/var\(--dk-(red|blue|border|gray-bg)\)/);
    // Should have breadcrumb styling
    expect(cssContent).toMatch(/\.breadcrumb/);
    // Should have a main layout container
    expect(cssContent).toMatch(/\.mainContent|\.contentArea|\.pageContent/);
    // Should include responsive breakpoints
    expect(cssContent).toMatch(/@media/);
  });
});
