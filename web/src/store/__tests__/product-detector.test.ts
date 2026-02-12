/**
 * Tests for product detection in assistant chat messages.
 *
 * This utility scans assistant text responses to:
 * 1. Detect "show me" intent (user wants to see product details visually)
 * 2. Extract product part numbers mentioned in the text
 * 3. Match extracted part numbers against the product catalog
 *
 * The pattern follows the same approach as call-trigger.ts for consistency.
 */
import { describe, it, expect } from "vitest";
import {
  detectShowMeIntent,
  extractProductReferences,
  matchProductsFromText,
  SHOW_ME_PATTERNS,
} from "../product-detector";

describe("detectShowMeIntent", () => {
  // Test 1: Detects "show me" intent in assistant messages
  it("detects show-me phrases in assistant text", () => {
    const phrases = [
      "Here, let me show you what we have in stock.",
      "I can show you some options for that.",
      "Take a look at these products I found for you.",
      "Here are the components you asked about.",
      "Let me pull up some products for you.",
    ];

    for (const text of phrases) {
      const result = detectShowMeIntent(text);
      expect(result.detected, `Should detect intent in: "${text}"`).toBe(true);
    }
  });

  // Test 2: Does NOT trigger on normal text without show-me intent
  it("does not trigger on normal assistant text", () => {
    const normalTexts = [
      "The resistor you need should be rated for 5V.",
      "I recommend checking the datasheet.",
      "That component is currently in stock.",
      "The price is competitive for this market.",
    ];

    for (const text of normalTexts) {
      const result = detectShowMeIntent(text);
      expect(result.detected, `Should NOT detect intent in: "${text}"`).toBe(false);
    }
  });

  // Test 3: SHOW_ME_PATTERNS is exported and non-empty
  it("exports a non-empty list of show-me patterns", () => {
    expect(SHOW_ME_PATTERNS).toBeDefined();
    expect(SHOW_ME_PATTERNS.length).toBeGreaterThan(0);
  });
});

describe("extractProductReferences", () => {
  // Test 4: Extracts part numbers from text mentioning specific catalog products
  it("extracts manufacturer part numbers from assistant text", () => {
    const text =
      "I found the C0603C104K5RACTU capacitor and the SN74LVC1G08DBVR logic gate " +
      "that would work great for your project.";

    const refs = extractProductReferences(text);
    expect(refs).toContain("C0603C104K5RACTU");
    expect(refs).toContain("SN74LVC1G08DBVR");
    expect(refs.length).toBe(2);
  });

  // Test 5: Returns empty array when no product references are found
  it("returns empty array when no product references found", () => {
    const text = "I think you should consider a ceramic capacitor for decoupling.";
    const refs = extractProductReferences(text);
    expect(refs).toEqual([]);
  });
});

describe("matchProductsFromText", () => {
  // Test 6 (bonus): Matches product references against the product catalog
  it("returns matching DigiKeyProduct objects for recognized part numbers", () => {
    const text =
      "Here, let me show you the C0603C104K5RACTU - it is a great decoupling cap.";

    const products = matchProductsFromText(text);
    expect(products.length).toBeGreaterThanOrEqual(1);
    expect(products[0].ManufacturerProductNumber).toBe("C0603C104K5RACTU");
  });
});
