/**
 * Tests for DigiKey type utilities used by the Section component.
 * Validates that display helpers produce correct output for product cards.
 */
import { describe, it, expect } from "vitest";
import {
  formatElectronicsPrice,
  getProductDisplayName,
  getKeyParameters,
  isActiveProduct,
  DigiKeyProduct,
} from "../digikey";

// Minimal mock product matching DigiKeyProduct interface
function createMockProduct(
  overrides: Partial<DigiKeyProduct> = {}
): DigiKeyProduct {
  return {
    Description: {
      ProductDescription: "CAP CER 0.1UF 50V X7R 0603",
      DetailedDescription:
        "0.1 uF +/-10% 50V Ceramic Capacitor X7R 0603 (1608 Metric)",
    },
    Manufacturer: { Id: 399, Name: "KEMET" },
    ManufacturerProductNumber: "C0603C104K5RACTU",
    UnitPrice: 0.08,
    ProductUrl: "https://www.digikey.com/en/products/detail/kemet/C0603C104K5RACTU/1465594",
    DatasheetUrl: "https://www.yageogroup.com/content/datasheet/asset/file/KEM_C1002_X7R_SMD",
    PhotoUrl: "https://mm.digikey.com/Volume0/opasdata/d220001/medias/images/5352/0603.jpg",
    ProductVariations: [],
    QuantityAvailable: 10000,
    ProductStatus: { Id: 0, Status: "Active" },
    BackOrderNotAllowed: false,
    NormallyStocking: true,
    Discontinued: false,
    EndOfLife: false,
    Ncnr: false,
    PrimaryVideoUrl: "",
    Parameters: [
      { ParameterId: 1, ParameterText: "Capacitance", ParameterType: "string", ValueId: "1", ValueText: "0.1 uF" },
      { ParameterId: 2, ParameterText: "Voltage - Rated", ParameterType: "string", ValueId: "2", ValueText: "50V" },
      { ParameterId: 3, ParameterText: "Tolerance", ParameterType: "string", ValueId: "3", ValueText: "+/-10%" },
      { ParameterId: 4, ParameterText: "Operating Temperature", ParameterType: "string", ValueId: "4", ValueText: "-55C to 125C" },
    ],
    ...overrides,
  };
}

describe("DigiKey display utilities for Section component", () => {
  // Test 1: formatElectronicsPrice handles sub-cent, sub-dollar, and normal prices
  it("formats electronics prices correctly for different ranges", () => {
    expect(formatElectronicsPrice(0.004)).toBe("$0.0040");
    expect(formatElectronicsPrice(0.08)).toBe("$0.080");
    expect(formatElectronicsPrice(3.5)).toBe("$3.50");
    expect(formatElectronicsPrice(0)).toBe("$0.0000");
  });

  // Test 2: getProductDisplayName returns "Manufacturer PartNumber"
  it("builds display name from manufacturer and part number", () => {
    const product = createMockProduct();
    expect(getProductDisplayName(product)).toBe("KEMET C0603C104K5RACTU");
  });

  // Test 3: getKeyParameters returns prioritized parameters up to limit
  it("returns prioritized parameters limited to requested count", () => {
    const product = createMockProduct();
    const params = getKeyParameters(product, 3);
    expect(params).toHaveLength(3);
    // Capacitance, Voltage - Rated, and Tolerance are all priority params
    expect(params[0].ParameterText).toBe("Capacitance");
    expect(params[1].ParameterText).toBe("Voltage - Rated");
    expect(params[2].ParameterText).toBe("Tolerance");
  });

  // Test 4: isActiveProduct correctly identifies active vs discontinued products
  it("identifies active and non-active product status", () => {
    const active = createMockProduct();
    expect(isActiveProduct(active)).toBe(true);

    const discontinued = createMockProduct({ Discontinued: true });
    expect(isActiveProduct(discontinued)).toBe(false);

    const obsolete = createMockProduct({
      ProductStatus: { Id: 1, Status: "Obsolete" },
    });
    expect(isActiveProduct(obsolete)).toBe(false);
  });

  // Test 5: Mock product has all fields needed by Section component card
  it("mock product contains all fields used by the Section product card", () => {
    const product = createMockProduct();
    // Fields used by the updated Section component
    expect(product.PhotoUrl).toBeTruthy();
    expect(product.ManufacturerProductNumber).toBeTruthy();
    expect(product.Manufacturer.Name).toBeTruthy();
    expect(product.Description.ProductDescription).toBeTruthy();
    expect(typeof product.UnitPrice).toBe("number");
    expect(product.Parameters.length).toBeGreaterThan(0);
    expect(product.ProductStatus.Status).toBeTruthy();
  });
});
