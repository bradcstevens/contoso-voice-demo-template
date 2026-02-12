"use client";

import { useState } from "react";

const NO_IMAGE_PLACEHOLDER = "/images/no-image.svg";

interface ProductImageProps {
  src: string | undefined | null;
  alt: string;
  className?: string;
}

/**
 * Client-side product image with automatic fallback to a placeholder
 * when the original image fails to load. This must be a client component
 * because it uses the onError event handler.
 */
export default function ProductImage({ src, alt, className }: ProductImageProps) {
  const [imgSrc, setImgSrc] = useState(src || NO_IMAGE_PLACEHOLDER);

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={imgSrc}
      alt={alt}
      className={className}
      loading="lazy"
      onError={() => setImgSrc(NO_IMAGE_PLACEHOLDER)}
    />
  );
}
