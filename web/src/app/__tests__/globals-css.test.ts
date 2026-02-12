/**
 * Tests for DigiKey Global Color Palette and Typography (Task 12).
 * Verifies that globals.css contains the required DigiKey brand variables,
 * updated body/link/button base styles, and preserves existing variables.
 */
import { describe, it, expect, beforeAll } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

let cssContent: string;

beforeAll(() => {
  const cssPath = resolve(__dirname, "..", "globals.css");
  cssContent = readFileSync(cssPath, "utf-8");
});

describe("DigiKey Global Color Palette - globals.css", () => {
  // Test 1: All DigiKey brand color CSS variables are defined
  it("defines all required DigiKey brand color variables", () => {
    const requiredVars: Record<string, string> = {
      "--dk-red": "#cc0000",
      "--dk-red-hover": "#a00000",
      "--dk-orange": "#f57c00",
      "--dk-dark": "#1a1a1a",
      "--dk-gray-bg": "#f5f5f5",
      "--dk-blue": "#0056b3",
      "--dk-border": "#e0e0e0",
    };

    for (const [varName, value] of Object.entries(requiredVars)) {
      expect(cssContent).toContain(`${varName}: ${value}`);
    }
  });

  // Test 2: Body background is updated to white
  it("sets body background-color to white", () => {
    // Match the body rule and check it uses white (either #fff, #ffffff, or var(--color-white))
    const bodyMatch = cssContent.match(
      /body\s*\{[^}]*background-color:\s*([^;]+);/
    );
    expect(bodyMatch).not.toBeNull();
    const bgValue = bodyMatch![1].trim();
    expect(
      bgValue === "var(--color-white)" ||
        bgValue === "#fff" ||
        bgValue === "#ffffff" ||
        bgValue === "white"
    ).toBe(true);
  });

  // Test 3: Link color is updated to DigiKey blue
  it("sets link color to DigiKey blue", () => {
    const linkMatch = cssContent.match(/^a\s*\{[^}]*color:\s*([^;]+);/m);
    expect(linkMatch).not.toBeNull();
    const colorValue = linkMatch![1].trim();
    expect(
      colorValue === "var(--dk-blue)" ||
        colorValue === "#0056b3"
    ).toBe(true);
  });

  // Test 4: Red CTA button base styles exist
  it("defines red CTA button base styles", () => {
    // Should have a .btn-cta or similar class with DigiKey red
    expect(cssContent).toContain(".btn-cta");
    expect(cssContent).toMatch(/\.btn-cta\s*\{[^}]*background-color:\s*var\(--dk-red\)/);
    expect(cssContent).toMatch(/\.btn-cta:hover\s*\{[^}]*background-color:\s*var\(--dk-red-hover\)/);
  });

  // Test 5: Existing variables are preserved (non-breaking)
  it("preserves existing color-zinc and color-sky variables", () => {
    // Verify key existing variables still present
    expect(cssContent).toContain("--color-zinc-50: #fafafa");
    expect(cssContent).toContain("--color-zinc-900: #18181b");
    expect(cssContent).toContain("--color-sky-500: #0ea5e9");
    expect(cssContent).toContain("--color-sky-600: #0284c7");
    expect(cssContent).toContain("--font-family-sans:");
    // Existing .button class should still be present
    expect(cssContent).toMatch(/\.button\s*\{/);
  });
});
