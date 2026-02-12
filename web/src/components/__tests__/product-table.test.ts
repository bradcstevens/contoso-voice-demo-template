/**
 * Tests for the ProductTable component (Task 20).
 * Verifies that the product data table renders columns for Image, Part Number,
 * Manufacturer, Description, Unit Price, and Stock with DigiKey styling.
 */
import { describe, it, expect, beforeAll } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

const componentsDir = resolve(__dirname, "..");
let componentContent: string;
let cssContent: string;

beforeAll(() => {
  const componentPath = resolve(componentsDir, "product-table.tsx");
  const cssPath = resolve(componentsDir, "product-table.module.css");
  componentContent = readFileSync(componentPath, "utf-8");
  cssContent = readFileSync(cssPath, "utf-8");
});

describe("ProductTable - product-table.tsx", () => {
  // Test 1: Component uses CSS Modules, accepts products prop, and renders a table
  it("uses CSS Modules, accepts products prop, and renders an HTML table", () => {
    expect(componentContent).toContain('import styles from "./product-table.module.css"');
    expect(componentContent).toMatch(/products/i);
    expect(componentContent).toMatch(/<table|<thead|<tbody/);
  });

  // Test 2: Table header includes required columns (Image, Part #, Manufacturer, Description, Price, Stock)
  it("renders table headers for Image, Part #, Manufacturer, Description, Price, and Stock", () => {
    expect(componentContent).toMatch(/Image/);
    expect(componentContent).toMatch(/Part/i);
    expect(componentContent).toMatch(/Manufacturer/i);
    expect(componentContent).toMatch(/Description/i);
    expect(componentContent).toMatch(/Price/i);
    expect(componentContent).toMatch(/Stock|Qty|Available/i);
  });

  // Test 3: Renders product rows with key data from DigiKeyProduct
  it("renders product rows using DigiKeyProduct data fields", () => {
    expect(componentContent).toMatch(/ManufacturerProductNumber/);
    expect(componentContent).toMatch(/Manufacturer\.Name|Manufacturer/);
    expect(componentContent).toMatch(/Description|ProductDescription/);
    expect(componentContent).toMatch(/UnitPrice|formatElectronicsPrice/);
    expect(componentContent).toMatch(/QuantityAvailable/);
    expect(componentContent).toMatch(/PhotoUrl/);
  });

  // Test 4: Includes pagination with result count display
  it("includes pagination with result count display", () => {
    expect(componentContent).toMatch(/page|Page|pagination|Pagination/i);
    expect(componentContent).toMatch(/Showing|showing/);
  });
});

describe("ProductTable - product-table.module.css", () => {
  // Test 5: CSS defines table layout, blue header, alternating rows, and brand variables
  it("defines table layout with blue header, alternating row colors, and DigiKey brand variables", () => {
    // Should have a table class
    expect(cssContent).toMatch(/\.table|\.productTable/);
    // Should use --dk-blue for header
    expect(cssContent).toMatch(/var\(--dk-blue\)/);
    // Should have alternating row styles using nth-child or alternate class
    expect(cssContent).toMatch(/nth-child|alternate|even|odd/i);
    // Should have header row class
    expect(cssContent).toMatch(/\.headerRow|\.tableHeader|thead/i);
  });
});
