"use client";

import { useState } from "react";
import styles from "./chat-product-cards.module.css";
import type { DigiKeyProduct } from "@/types/digikey";
import { formatElectronicsPrice } from "@/types/digikey";

const NO_IMAGE_PLACEHOLDER = "/images/no-image.svg";

interface ChatProductCardsProps {
  products: DigiKeyProduct[];
}

/**
 * Product image with automatic fallback to placeholder on error.
 */
function CardImage({ product }: { product: DigiKeyProduct }) {
  const [src, setSrc] = useState(product.PhotoUrl || NO_IMAGE_PLACEHOLDER);

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={product.Description.ProductDescription}
      className={styles.cardImage}
      loading="lazy"
      onError={() => setSrc(NO_IMAGE_PLACEHOLDER)}
    />
  );
}

/**
 * ChatProductCards
 *
 * Renders a compact list of product cards inline within a chat message bubble.
 * Each card shows the product image, part number, manufacturer, description,
 * price, and stock status. Clicking a card opens the product page on DigiKey.
 *
 * Designed to fit within the 500px-wide chat window without horizontal scrolling.
 */
const ChatProductCards = ({ products }: ChatProductCardsProps) => {
  if (!products || products.length === 0) return null;

  return (
    <div className={styles.productCardsContainer}>
      <div className={styles.productCardsLabel}>Referenced Products</div>
      <div className={styles.productCardsGrid}>
        {products.map((product) => (
          <a
            key={product.ManufacturerProductNumber}
            href={product.ProductUrl || "#"}
            target={product.ProductUrl ? "_blank" : undefined}
            rel={product.ProductUrl ? "noopener noreferrer" : undefined}
            className={styles.productCard}
          >
            <div className={styles.cardImageWrapper}>
              <CardImage product={product} />
            </div>
            <div className={styles.cardContent}>
              <div className={styles.cardPartNumber}>
                {product.ManufacturerProductNumber}
              </div>
              <div className={styles.cardManufacturer}>
                {product.Manufacturer.Name}
              </div>
              <div className={styles.cardDescription}>
                {product.Description.ProductDescription}
              </div>
              <div className={styles.cardFooter}>
                <span className={styles.cardPrice}>
                  {formatElectronicsPrice(product.UnitPrice)}
                </span>
                <span className={styles.cardStock}>
                  {product.QuantityAvailable.toLocaleString()} in stock
                </span>
              </div>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
};

export default ChatProductCards;
