import { describe, it, expect } from "vitest";

/**
 * Hero Carousel - Unit Tests (TDD)
 *
 * Tests for the carousel slide data, configuration, and structure.
 * Follows the same data-driven testing pattern used across the codebase.
 */

import {
  CAROUSEL_SLIDES,
  AUTOPLAY_INTERVAL_MS,
  type CarouselSlide,
} from "../hero-carousel-data";

describe("HeroCarousel slide data", () => {
  it("should export exactly 3 slides", () => {
    expect(CAROUSEL_SLIDES).toHaveLength(3);
  });

  it("each slide should have all required fields with non-empty values", () => {
    const requiredKeys: (keyof CarouselSlide)[] = [
      "id",
      "image",
      "title",
      "description",
      "ctaLabel",
      "ctaHref",
      "overlayVariant",
    ];

    for (const slide of CAROUSEL_SLIDES) {
      for (const key of requiredKeys) {
        expect(slide[key], `slide "${slide.id}" missing "${key}"`).toBeTruthy();
      }
      // overlayVariant must be one of the two allowed values
      expect(["light", "dark"]).toContain(slide.overlayVariant);
    }
  });

  it("should have unique slide ids", () => {
    const ids = CAROUSEL_SLIDES.map((s) => s.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("all image paths should start with /images/ and end with .jpg", () => {
    for (const slide of CAROUSEL_SLIDES) {
      expect(slide.image).toMatch(/^\/images\/.+\.jpg$/);
    }
  });

  it("AUTOPLAY_INTERVAL_MS should be a positive number (>= 3000ms)", () => {
    expect(AUTOPLAY_INTERVAL_MS).toBeGreaterThanOrEqual(3000);
    expect(typeof AUTOPLAY_INTERVAL_MS).toBe("number");
  });
});
