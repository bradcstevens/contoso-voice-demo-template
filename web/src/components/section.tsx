"use client";

import styles from "./section.module.css";
import type { CategoryWithProducts } from "@/types/digikey";
import { useState } from "react";
import {
  getProductDisplayName,
  formatElectronicsPrice,
  getKeyParameters,
  isActiveProduct,
} from "@/types/digikey";
import type { DigiKeyProduct } from "@/types/digikey";

const NO_IMAGE_PLACEHOLDER = "/images/no-image.svg";

/**
 * Product image with automatic fallback to placeholder on error.
 * Uses a plain <img> tag for external DigiKey URLs (mm.digikey.com)
 * to avoid Next.js Image domain configuration issues.
 */
function ProductImage({ product }: { product: DigiKeyProduct }) {
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

type Props = {
  category: CategoryWithProducts;
  index: number;
};

const Section = ({ category }: Props) => {
  return (
    <section id={category.slug} className={styles.categorySection}>
      <div className={styles.categoryInner}>
        <h2 className={styles.categoryTitle}>{category.name}</h2>
        <p className={styles.categoryDescription}>{category.description}</p>

        <div className={styles.productGrid}>
          {category.products.map((product) => (
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
                  <ProductImage product={product} />
                </div>

                {!isActiveProduct(product) && (
                  <span className={styles.statusBadge}>
                    {product.ProductStatus.Status}
                  </span>
                )}

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
                  <div className={styles.cardParams}>
                    {getKeyParameters(product, 3)
                      .map((p) => p.ValueText)
                      .join(", ")}
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

export default Section;
