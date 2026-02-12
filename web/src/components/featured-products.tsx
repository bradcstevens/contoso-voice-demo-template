"use client";

import { useRef, useState } from "react";
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

const FeaturedProducts = () => {
  const products = getTrendingProducts(12);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scroll = (direction: "left" | "right") => {
    if (!scrollRef.current) return;
    const amount = 480;
    scrollRef.current.scrollBy({
      left: direction === "left" ? -amount : amount,
      behavior: "smooth",
    });
  };

  return (
    <section className={styles.featuredSection} aria-label="Featured Products">
      <div className={styles.featuredInner}>
        {/* Section header */}
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionHeading}>Featured Products</h2>
        </div>

        {/* Manufacturer badges row */}
        <div className={styles.manufacturerRow}>
          {manufacturers.map((mfr) => (
            <span key={mfr.Id} className={styles.manufacturerBadge}>
              {mfr.Name}
            </span>
          ))}
        </div>

        {/* Product cards carousel with flanking arrows */}
        <div className={styles.carouselWrapper}>
          <button
            type="button"
            className={`${styles.carouselBtn} ${styles.carouselBtnLeft}`}
            onClick={() => scroll("left")}
            aria-label="Scroll left"
          >
            &#8249;
          </button>
          <div className={styles.productCarousel} ref={scrollRef}>
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
          <button
            type="button"
            className={`${styles.carouselBtn} ${styles.carouselBtnRight}`}
            onClick={() => scroll("right")}
            aria-label="Scroll right"
          >
            &#8250;
          </button>
        </div>
      </div>
    </section>
  );
};

export default FeaturedProducts;
