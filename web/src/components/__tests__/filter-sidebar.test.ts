/**
 * Tests for the FilterSidebar component (Task 20).
 * Verifies that the filter sidebar renders parameter-based checkboxes
 * with Apply and Reset buttons using DigiKey styling.
 */
import { describe, it, expect, beforeAll } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

const componentsDir = resolve(__dirname, "..");
let componentContent: string;
let cssContent: string;

beforeAll(() => {
  const componentPath = resolve(componentsDir, "filter-sidebar.tsx");
  const cssPath = resolve(componentsDir, "filter-sidebar.module.css");
  componentContent = readFileSync(componentPath, "utf-8");
  cssContent = readFileSync(cssPath, "utf-8");
});

describe("FilterSidebar - filter-sidebar.tsx", () => {
  // Test 1: Component uses CSS Modules and accepts products prop for filter extraction
  it("uses CSS Modules and accepts products-related props", () => {
    expect(componentContent).toContain('import styles from "./filter-sidebar.module.css"');
    expect(componentContent).toMatch(/products|Products|parameters|Parameters/i);
  });

  // Test 2: Renders checkbox inputs for parameter-based filtering
  it("renders checkbox inputs for parameter-based filtering", () => {
    expect(componentContent).toMatch(/type="checkbox"|type=.checkbox/);
    expect(componentContent).toMatch(/ParameterText|parameterText|parameter/i);
  });

  // Test 3: Includes Apply Filters and Reset Filters buttons
  it("includes Apply Filters and Reset Filters buttons", () => {
    expect(componentContent).toMatch(/Apply/i);
    expect(componentContent).toMatch(/Reset/i);
  });

  // Test 4: Uses CSS Modules and avoids Tailwind utility classes
  it("uses CSS Modules and avoids Tailwind utility classes", () => {
    expect(componentContent).toContain('import styles from "./filter-sidebar.module.css"');
    expect(componentContent).toMatch(/styles\.\w+/);
    expect(componentContent).not.toMatch(/className="[^"]*\b(flex|grid|p-|m-|text-|bg-)\b/);
  });
});

describe("FilterSidebar - filter-sidebar.module.css", () => {
  // Test 5: CSS defines sidebar layout, filter group styles, and DigiKey brand button colors
  it("defines sidebar layout, filter groups, and uses DigiKey brand variables for buttons", () => {
    // Should have a sidebar container class
    expect(cssContent).toMatch(/\.sidebar|\.filterSidebar/);
    // Should have filter group styling
    expect(cssContent).toMatch(/\.filterGroup|\.group/);
    // Should use --dk-red for the Apply button
    expect(cssContent).toMatch(/var\(--dk-red\)/);
    // Should have button styling
    expect(cssContent).toMatch(/\.applyButton|\.resetButton|button/i);
  });
});
