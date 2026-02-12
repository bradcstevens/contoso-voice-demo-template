// ---------------------------------------------------------------------------
// Product Detection Utility for Chat Messages
//
// Scans assistant text responses to detect "show me" intent and extract
// product part number references. When detected, the chat UI renders inline
// product cards alongside the assistant's text response.
//
// This follows the same pure-utility pattern as call-trigger.ts: no React
// or DOM dependencies, fully testable in a Node environment.
// ---------------------------------------------------------------------------

import type { DigiKeyProduct } from "@/types/digikey";
import productsData from "../../public/products.json";

// ---- Types ----------------------------------------------------------------

/** Result of scanning text for "show me" intent */
export interface ShowMeResult {
  /** Whether a show-me intent was detected */
  detected: boolean;
}

// ---- Product Catalog (static import) --------------------------------------

// Type-assert the imported JSON to a minimal shape for matching purposes.
// The full product data is available on each entry.
interface CatalogProduct extends DigiKeyProduct {
  _category?: string;
  _categoryName?: string;
}

const catalog = productsData as CatalogProduct[];

// Build a lookup map keyed by ManufacturerProductNumber for O(1) matching
const catalogByPartNumber = new Map<string, DigiKeyProduct>();
for (const product of catalog) {
  catalogByPartNumber.set(
    product.ManufacturerProductNumber.toUpperCase(),
    product
  );
}

// ---- Show-Me Intent Patterns ----------------------------------------------

/**
 * Regex patterns that match assistant phrases indicating product display.
 *
 * These detect when the assistant is presenting products to the user.
 * Case-insensitive matching.
 */
export const SHOW_ME_PATTERNS: RegExp[] = [
  /\bshow you\b/i,
  /\blet me show\b/i,
  /\btake a look at\b/i,
  /\bhere are the\b/i,
  /\bhere are some\b/i,
  /\bhere is the\b/i,
  /\bcheck out\b/i,
  /\bpull up\b/i,
  /\bi found\b.*\bfor you\b/i,
  /\bhere.*\bproducts?\b/i,
  /\bhere.*\bcomponents?\b/i,
  /\bhere.*\boptions?\b/i,
];

// ---- Intent Detection -----------------------------------------------------

/**
 * Scan assistant text for "show me" intent.
 *
 * @param text - The assistant's message text to scan
 * @returns A ShowMeResult indicating whether intent was found
 */
export function detectShowMeIntent(text: string): ShowMeResult {
  if (!text || text.length === 0) {
    return { detected: false };
  }

  for (const pattern of SHOW_ME_PATTERNS) {
    if (pattern.test(text)) {
      return { detected: true };
    }
  }

  return { detected: false };
}

// ---- Part Number Extraction -----------------------------------------------

/**
 * Extract manufacturer part numbers from text.
 *
 * Electronics part numbers typically contain a mix of uppercase letters,
 * digits, and hyphens, and are at least 6 characters long. This regex
 * is designed to catch common formats like:
 *   - C0603C104K5RACTU (KEMET capacitor)
 *   - RC0402FR-0710KL (YAGEO resistor)
 *   - ATMEGA328P-PU (Microchip MCU)
 *
 * We filter candidates against the actual product catalog to avoid
 * false positives from normal text.
 *
 * @param text - Text to extract product references from
 * @returns Array of matched part number strings
 */
export function extractProductReferences(text: string): string[] {
  if (!text || text.length === 0) {
    return [];
  }

  // Match alphanumeric sequences with optional hyphens, at least 6 chars
  const candidatePattern = /\b([A-Z0-9][A-Z0-9\-]{4,}[A-Z0-9])\b/gi;
  const matches = text.match(candidatePattern);

  if (!matches) {
    return [];
  }

  // Deduplicate and filter to only known catalog part numbers
  const seen = new Set<string>();
  const results: string[] = [];

  for (const candidate of matches) {
    const upper = candidate.toUpperCase();
    if (!seen.has(upper) && catalogByPartNumber.has(upper)) {
      seen.add(upper);
      results.push(candidate);
    }
  }

  return results;
}

// ---- Full Matching Pipeline -----------------------------------------------

/**
 * Extract product references from text and return matching DigiKeyProduct
 * objects from the catalog.
 *
 * This combines extractProductReferences() with catalog lookup.
 *
 * @param text - Text to scan for product references
 * @returns Array of DigiKeyProduct objects found in the text
 */
export function matchProductsFromText(text: string): DigiKeyProduct[] {
  const refs = extractProductReferences(text);
  const products: DigiKeyProduct[] = [];

  for (const ref of refs) {
    const product = catalogByPartNumber.get(ref.toUpperCase());
    if (product) {
      products.push(product);
    }
  }

  return products;
}
