"use client";

import { useState, useCallback } from "react";
import styles from "./featured-manufacturers.module.css";
import manufacturersData from "../../public/manufacturers.json";

interface Manufacturer {
  Id: number;
  Name: string;
}

const manufacturers = manufacturersData as Manufacturer[];
const ITEMS_PER_PAGE = 8;
const totalPages = Math.ceil(manufacturers.length / ITEMS_PER_PAGE);

export default function FeaturedManufacturers() {
  const [page, setPage] = useState(0);

  const next = useCallback(
    () => setPage((p) => (p + 1) % totalPages),
    []
  );
  const prev = useCallback(
    () => setPage((p) => (p - 1 + totalPages) % totalPages),
    []
  );

  const visible = manufacturers.slice(
    page * ITEMS_PER_PAGE,
    page * ITEMS_PER_PAGE + ITEMS_PER_PAGE
  );

  return (
    <section
      className={styles.section}
      aria-label="Featured Manufacturers"
    >
      <div className={styles.inner}>
        <div className={styles.heading}>
          <h2 className={styles.title}>Featured Manufacturers</h2>
          <a href="#" className={styles.viewAll}>
            View All
          </a>
        </div>

        <div className={styles.carouselWrap}>
          <button
            className={`${styles.arrow} ${styles.arrowLeft}`}
            onClick={prev}
            aria-label="Previous manufacturers"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M10 12L6 8L10 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>

          <div className={styles.logoGrid}>
            {visible.map((mfr) => (
              <div key={mfr.Id} className={styles.logoCard}>
                <span className={styles.logoText}>{mfr.Name}</span>
              </div>
            ))}
          </div>

          <button
            className={`${styles.arrow} ${styles.arrowRight}`}
            onClick={next}
            aria-label="Next manufacturers"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M6 12L10 8L6 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>

        {/* Dot indicators */}
        <div className={styles.dots}>
          {Array.from({ length: totalPages }).map((_, i) => (
            <button
              key={i}
              className={`${styles.dot} ${i === page ? styles.dotActive : ""}`}
              onClick={() => setPage(i)}
              aria-label={`Page ${i + 1}`}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
