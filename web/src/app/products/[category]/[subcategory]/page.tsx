"use client";

import styles from "./page.module.css";
import Header from "@/components/header";
import Footer from "@/components/footer";
import FilterSidebar from "@/components/filter-sidebar";
import ProductTable from "@/components/product-table";
import { getCategories, getProductsByCategory } from "@/store/products";
import type { DigiKeyProduct } from "@/types/digikey";
import Link from "next/link";
import { useState, useMemo, use } from "react";

interface SubcategoryPageProps {
  params: Promise<{ category: string; subcategory: string }>;
}

/**
 * Apply parameter-based filters to a list of products.
 * Only keeps products that match ALL selected filter groups.
 * Within a filter group, a product must match at least one selected value.
 */
function applyFilters(
  products: DigiKeyProduct[],
  filters: Record<string, string[]>
): DigiKeyProduct[] {
  const activeFilters = Object.entries(filters).filter(
    ([, values]) => values.length > 0
  );

  if (activeFilters.length === 0) return products;

  return products.filter((product) =>
    activeFilters.every(([paramText, allowedValues]) =>
      product.Parameters.some(
        (p) =>
          p.ParameterText === paramText && allowedValues.includes(p.ValueText)
      )
    )
  );
}

/**
 * Format a slug back into a display-friendly name.
 * e.g., "ceramic-capacitors" -> "Ceramic Capacitors"
 */
function formatSubcategoryName(slug: string): string {
  return slug
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export default function SubcategoryPage({ params }: SubcategoryPageProps) {
  const { category: categorySlug, subcategory: subcategorySlug } = use(params);

  const categories = getCategories();
  const category = categories.find((c) => c.slug === categorySlug);

  const [activeFilters, setActiveFilters] = useState<
    Record<string, string[]>
  >({});

  const allProducts = useMemo(() => {
    if (!category) return [];
    return getProductsByCategory(categorySlug);
  }, [category, categorySlug]);

  const filteredProducts = useMemo(
    () => applyFilters(allProducts, activeFilters),
    [allProducts, activeFilters]
  );

  const subcategoryDisplayName = formatSubcategoryName(subcategorySlug);

  if (!category) {
    return (
      <div className={styles.page}>
        <Header />
        <div className={styles.notFound}>
          <h1 className={styles.notFoundTitle}>Category not found</h1>
          <p className={styles.notFoundText}>
            The category you are looking for does not exist.
          </p>
          <Link href="/products" className={styles.notFoundLink}>
            Browse all products
          </Link>
        </div>
        <Footer />
      </div>
    );
  }

  const handleApplyFilters = (filters: Record<string, string[]>) => {
    setActiveFilters(filters);
  };

  const handleResetFilters = () => {
    setActiveFilters({});
  };

  return (
    <div className={styles.page}>
      <Header />

      {/* Breadcrumb */}
      <nav className={styles.breadcrumb} aria-label="Breadcrumb">
        <Link href="/" className={styles.breadcrumbLink}>
          Home
        </Link>
        <span className={styles.breadcrumbSeparator}>&gt;</span>
        <Link href="/products" className={styles.breadcrumbLink}>
          Products
        </Link>
        <span className={styles.breadcrumbSeparator}>&gt;</span>
        <Link
          href={`/products/${categorySlug}`}
          className={styles.breadcrumbLink}
        >
          {category.name}
        </Link>
        <span className={styles.breadcrumbSeparator}>&gt;</span>
        <span className={styles.breadcrumbCurrent}>
          {subcategoryDisplayName}
        </span>
      </nav>

      {/* Page Title */}
      <div className={styles.titleSection}>
        <h1 className={styles.pageTitle}>{subcategoryDisplayName}</h1>
        <span className={styles.resultCount}>
          {filteredProducts.length} of {allProducts.length}{" "}
          {allProducts.length === 1 ? "result" : "results"}
        </span>
      </div>

      {/* Main Content: Sidebar + Table */}
      <div className={styles.mainContent}>
        <FilterSidebar
          products={allProducts}
          onApplyFilters={handleApplyFilters}
          onResetFilters={handleResetFilters}
        />

        <main className={styles.contentArea}>
          <ProductTable products={filteredProducts} />
        </main>
      </div>

      <Footer />
    </div>
  );
}
