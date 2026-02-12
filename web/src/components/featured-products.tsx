"use client";

import { useState } from "react";
import styles from "./featured-products.module.css";
import { getTrendingProducts } from "@/store/products";
import { formatElectronicsPrice, getProductDisplayName } from "@/types/digikey";
import type { DigiKeyProduct } from "@/types/digikey";
import manufacturersData from "../../public/manufacturers.json";

const NO_IMAGE_PLACEHOLDER = "/images/no-image.svg";

/** Manufacturer entry from manufacturers.json */
interface Manufacturer {
  Id: number;
  Name: string;
}

const manufacturers = manufacturersData as Manufacturer[];

/**
 * Product image with automatic fallback to placeholder on error.
 * Uses a plain <img> tag for external DigiKey URLs to avoid
 * Next.js Image domain configuration issues.
 */
function FeaturedProductImage({ product }: { product: DigiKeyProduct }) {
  const [src, setSrc] = useState(
    product.PhotoUrl || NO_IMAGE_PLACEHOLDER
  );

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={getProductDisplayName(product)}
      className={styles.cardImage}
      onError={() => setSrc(NO_IMAGE_PLACEHOLDER)}
      loading="lazy"
    />
  );
}

/**
 * FeaturedProducts
 *
 * A section displaying "FEATURED PRODUCTS" with manufacturer name badges
 * and a horizontal wrapping grid of product cards. Each card shows the
 * product image, manufacturer, part number, description, and unit price.
 *
 * Data sources:
 * - getTrendingProducts() from @/store/products for the product cards
 * - manufacturers.json for the manufacturer badge row
 */
const FeaturedProducts = () => {
  const products = getTrendingProducts(12);

  return (
    <section className={styles.featuredSection} aria-label="Featured Products">
      <div className={styles.featuredInner}>
        {/* Section heading */}
        <h2 className={styles.sectionHeading}>Featured Products</h2>

        {/* Manufacturer badges row */}
        <div className={styles.manufacturerRow}>
          {manufacturers.map((mfr) => (
            <span key={mfr.Id} className={styles.manufacturerBadge}>
              {mfr.Name}
            </span>
          ))}
        </div>

        {/* Product cards grid */}
        <div className={styles.productGrid}>
          {products.map((product) => (
            <div
              key={product.ManufacturerProductNumber}
              className={styles.productCard}
            >
              <a
                href={product.ProductUrl || "#"}
                target={product.ProductUrl ? "_blank" : undefined}
                rel={product.ProductUrl ? "noopener noreferrer" : undefined}
                className={styles.cardLink}
              >
                <div className={styles.cardImageWrapper}>
                  <FeaturedProductImage product={product} />
                </div>
                <div className={styles.cardBody}>
                  <div className={styles.cardManufacturer}>
                    {product.Manufacturer.Name}
                  </div>
                  <div className={styles.cardPartNumber}>
                    {product.ManufacturerProductNumber}
                  </div>
                  <div className={styles.cardDescription}>
                    {product.Description.ProductDescription}
                  </div>
                  <div className={styles.cardPrice}>
                    {formatElectronicsPrice(product.UnitPrice)}
                  </div>
                </div>
              </a>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default FeaturedProducts;
