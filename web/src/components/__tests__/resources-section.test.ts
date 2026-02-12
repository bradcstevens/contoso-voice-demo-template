import { describe, it, expect } from "vitest";

/**
 * Resources Section - Unit Tests
 *
 * Tests for the Tools/Services/Content section data and structure.
 * These tests verify the data model and configuration that drives the component.
 */

// The data structure the component will use
import {
  RESOURCES_COLUMNS,
  type ResourceColumn,
} from "../resources-section-data";

describe("ResourcesSection data", () => {
  it("should export exactly three columns: Tools, Services, Content", () => {
    expect(RESOURCES_COLUMNS).toHaveLength(3);
    const headings = RESOURCES_COLUMNS.map((col: ResourceColumn) => col.heading);
    expect(headings).toEqual(["Tools", "Services", "Content"]);
  });

  it("should have exactly 5 links per column", () => {
    for (const column of RESOURCES_COLUMNS) {
      expect(column.links).toHaveLength(5);
    }
  });

  it("should have the correct Tools links", () => {
    const tools = RESOURCES_COLUMNS.find(
      (col: ResourceColumn) => col.heading === "Tools"
    );
    expect(tools).toBeDefined();
    const labels = tools!.links.map((link) => link.label);
    expect(labels).toEqual([
      "PCB Builder",
      "Conversion Calculators",
      "Scheme-It",
      "Reference Design Library",
      "Cross Reference",
    ]);
  });

  it("should have the correct Services links", () => {
    const services = RESOURCES_COLUMNS.find(
      (col: ResourceColumn) => col.heading === "Services"
    );
    expect(services).toBeDefined();
    const labels = services!.links.map((link) => link.label);
    expect(labels).toEqual([
      "Device Programming",
      "Part Tracing",
      "Digital Solutions",
      "Design & Integration Services",
      "Product Services",
    ]);
  });

  it("should have the correct Content links", () => {
    const content = RESOURCES_COLUMNS.find(
      (col: ResourceColumn) => col.heading === "Content"
    );
    expect(content).toBeDefined();
    const labels = content!.links.map((link) => link.label);
    expect(labels).toEqual([
      "New Products",
      "TechForum",
      "Maker.io",
      "Product Training Library",
      "Video Library",
    ]);
  });
});
