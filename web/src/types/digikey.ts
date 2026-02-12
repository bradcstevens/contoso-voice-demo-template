// DigiKey Product Index TypeScript Interfaces
// Based on DigiKey Product Search API v4 schema

// --- Core Product Interfaces ---

export interface DigiKeyDescription {
  ProductDescription: string;
  DetailedDescription: string;
}

export interface DigiKeyManufacturer {
  Id: number;
  Name: string;
}

export interface ProductStatus {
  Id: number;
  Status: string;
}

export interface ProductParameter {
  ParameterId: number;
  ParameterText: string;
  ParameterType: string;
  ValueId: string;
  ValueText: string;
}

// --- Pricing & Variation Interfaces ---

export interface PackageType {
  Id: number;
  Name: string;
}

export interface PricingBreak {
  BreakQuantity: number;
  UnitPrice: number;
  TotalPrice: number;
}

export interface ProductVariation {
  DigiKeyProductNumber: string;
  PackageType: PackageType;
  StandardPricing: PricingBreak[];
  MyPricing: PricingBreak[];
  MarketPlace: boolean;
  TariffActive: boolean;
  Supplier: DigiKeyManufacturer;
  QuantityAvailableforPackageType: number;
  MaxQuantityForDistribution: number;
  MinimumOrderQuantity: number;
  StandardPackage: number;
  DigiReelFee: number;
}

// --- Main Product Interface ---

export interface DigiKeyProduct {
  Description: DigiKeyDescription;
  Manufacturer: DigiKeyManufacturer;
  ManufacturerProductNumber: string;
  UnitPrice: number;
  ProductUrl: string;
  DatasheetUrl: string;
  PhotoUrl: string;
  ProductVariations: ProductVariation[];
  QuantityAvailable: number;
  ProductStatus: ProductStatus;
  BackOrderNotAllowed: boolean;
  NormallyStocking: boolean;
  Discontinued: boolean;
  EndOfLife: boolean;
  Ncnr: boolean;
  PrimaryVideoUrl: string;
  Parameters: ProductParameter[];
}

// --- Category Interfaces ---

export interface DigiKeyCategory {
  CategoryId: number;
  ParentId: number;
  Name: string;
  ProductCount: number;
  Children: DigiKeyCategory[];
}

export interface DigiKeyCategoryResponse {
  ProductCount: number;
  Categories: DigiKeyCategory[];
}

// --- Response Wrappers ---

export interface DigiKeyProductsResponse {
  Products: DigiKeyProduct[];
}

// --- UI Display Interfaces ---

export interface CategoryWithProducts {
  name: string;
  slug: string;
  description: string;
  products: DigiKeyProduct[];
}

// --- Utility Functions ---

/**
 * Format a price for electronics display.
 * Handles fractional cents common in bulk electronics pricing.
 * e.g., 0.004 → "$0.0040", 1.50 → "$1.50"
 */
export function formatElectronicsPrice(price: number): string {
  if (price < 0.01) {
    return `$${price.toFixed(4)}`;
  }
  if (price < 1) {
    return `$${price.toFixed(3)}`;
  }
  return `$${price.toFixed(2)}`;
}

/**
 * Extract the top N key parameters from a product.
 * Prioritizes common specs like Capacitance, Resistance, Voltage, Tolerance.
 */
export function getKeyParameters(
  product: DigiKeyProduct,
  limit: number = 3
): ProductParameter[] {
  const priorityParams = [
    "Capacitance",
    "Resistance",
    "Voltage - Rated",
    "Tolerance",
    "Power (Watts)",
    "Inductance",
    "Current Rating (Amps)",
    "Temperature Coefficient",
    "Operating Temperature",
  ];

  const sorted = [...product.Parameters].sort((a, b) => {
    const aIdx = priorityParams.indexOf(a.ParameterText);
    const bIdx = priorityParams.indexOf(b.ParameterText);
    const aPriority = aIdx === -1 ? priorityParams.length : aIdx;
    const bPriority = bIdx === -1 ? priorityParams.length : bIdx;
    return aPriority - bPriority;
  });

  return sorted.slice(0, limit);
}

/**
 * Find the lowest unit price across all product variations.
 */
export function getLowestPrice(product: DigiKeyProduct): number | null {
  let lowest: number | null = null;

  for (const variation of product.ProductVariations) {
    for (const pricing of variation.StandardPricing) {
      if (lowest === null || pricing.UnitPrice < lowest) {
        lowest = pricing.UnitPrice;
      }
    }
  }

  return lowest;
}

/**
 * Get a display-friendly product name: "Manufacturer - Part Number"
 */
export function getProductDisplayName(product: DigiKeyProduct): string {
  return `${product.Manufacturer.Name} ${product.ManufacturerProductNumber}`;
}

/**
 * Convert a category name to a URL-friendly slug.
 */
export function getCategorySlug(category: DigiKeyCategory): string {
  return category.Name.toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/**
 * Get the first DigiKey product number from variations.
 */
export function getDigiKeyPartNumber(product: DigiKeyProduct): string | null {
  if (product.ProductVariations.length > 0) {
    return product.ProductVariations[0].DigiKeyProductNumber;
  }
  return null;
}

/**
 * Check if a product is actively available for new designs.
 */
export function isActiveProduct(product: DigiKeyProduct): boolean {
  return (
    !product.Discontinued &&
    !product.EndOfLife &&
    product.ProductStatus.Status !== "Not For New Designs" &&
    product.ProductStatus.Status !== "Obsolete"
  );
}
