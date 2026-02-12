"use client";

import styles from "./product-table.module.css";
import type { DigiKeyProduct } from "@/types/digikey";
import { formatElectronicsPrice } from "@/types/digikey";
import { useState } from "react";

const NO_IMAGE_PLACEHOLDER = "/images/no-image.svg";
const ITEMS_PER_PAGE = 20;

type SortKey =
  | "partNumber"
  | "manufacturer"
  | "description"
  | "price"
  | "stock";
type SortDirection = "asc" | "desc";

interface ProductTableProps {
  products: DigiKeyProduct[];
}

function sortProducts(
  products: DigiKeyProduct[],
  sortKey: SortKey,
  sortDirection: SortDirection
): DigiKeyProduct[] {
  const sorted = [...products].sort((a, b) => {
    let comparison = 0;
    switch (sortKey) {
      case "partNumber":
        comparison = a.ManufacturerProductNumber.localeCompare(
          b.ManufacturerProductNumber
        );
        break;
      case "manufacturer":
        comparison = a.Manufacturer.Name.localeCompare(b.Manufacturer.Name);
        break;
      case "description":
        comparison = a.Description.ProductDescription.localeCompare(
          b.Description.ProductDescription
        );
        break;
      case "price":
        comparison = a.UnitPrice - b.UnitPrice;
        break;
      case "stock":
        comparison = a.QuantityAvailable - b.QuantityAvailable;
        break;
    }
    return sortDirection === "asc" ? comparison : -comparison;
  });
  return sorted;
}

const ProductTable = ({ products }: ProductTableProps) => {
  const [currentPage, setCurrentPage] = useState(1);
  const [sortKey, setSortKey] = useState<SortKey>("partNumber");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDirection("asc");
    }
    setCurrentPage(1);
  };

  const sortedProducts = sortProducts(products, sortKey, sortDirection);
  const totalProducts = sortedProducts.length;
  const totalPages = Math.max(1, Math.ceil(totalProducts / ITEMS_PER_PAGE));
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
  const endIndex = Math.min(startIndex + ITEMS_PER_PAGE, totalProducts);
  const pageProducts = sortedProducts.slice(startIndex, endIndex);

  const sortIndicator = (key: SortKey) => {
    if (sortKey !== key) return "";
    return sortDirection === "asc" ? " \u25B2" : " \u25BC";
  };

  return (
    <div className={styles.tableContainer}>
      <div className={styles.resultSummary}>
        Showing {totalProducts === 0 ? 0 : startIndex + 1}-{endIndex} of{" "}
        {totalProducts} results
      </div>

      <div className={styles.tableWrapper}>
        <table className={styles.table}>
          <thead>
            <tr className={styles.headerRow}>
              <th className={styles.headerCell}>Image</th>
              <th
                className={styles.headerCellSortable}
                onClick={() => handleSort("partNumber")}
              >
                MFR Part #{sortIndicator("partNumber")}
              </th>
              <th
                className={styles.headerCellSortable}
                onClick={() => handleSort("manufacturer")}
              >
                Manufacturer{sortIndicator("manufacturer")}
              </th>
              <th
                className={styles.headerCellSortable}
                onClick={() => handleSort("description")}
              >
                Description{sortIndicator("description")}
              </th>
              <th
                className={styles.headerCellSortable}
                onClick={() => handleSort("price")}
              >
                Unit Price{sortIndicator("price")}
              </th>
              <th
                className={styles.headerCellSortable}
                onClick={() => handleSort("stock")}
              >
                Stock{sortIndicator("stock")}
              </th>
            </tr>
          </thead>
          <tbody>
            {pageProducts.length === 0 && (
              <tr>
                <td colSpan={6} className={styles.emptyRow}>
                  No products found
                </td>
              </tr>
            )}
            {pageProducts.map((product, index) => (
              <tr
                key={product.ManufacturerProductNumber}
                className={
                  index % 2 === 0 ? styles.tableRowEven : styles.tableRowOdd
                }
              >
                <td className={styles.imageCell}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={product.PhotoUrl || NO_IMAGE_PLACEHOLDER}
                    alt={product.Description.ProductDescription}
                    className={styles.productImage}
                    loading="lazy"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src = NO_IMAGE_PLACEHOLDER;
                    }}
                  />
                </td>
                <td className={styles.partNumberCell}>
                  <a
                    href={product.ProductUrl || "#"}
                    className={styles.partNumberLink}
                    target={product.ProductUrl ? "_blank" : undefined}
                    rel={
                      product.ProductUrl ? "noopener noreferrer" : undefined
                    }
                  >
                    {product.ManufacturerProductNumber}
                  </a>
                </td>
                <td className={styles.cell}>{product.Manufacturer.Name}</td>
                <td className={styles.descriptionCell}>
                  {product.Description.ProductDescription}
                </td>
                <td className={styles.priceCell}>
                  {formatElectronicsPrice(product.UnitPrice)}
                </td>
                <td className={styles.stockCell}>
                  {product.QuantityAvailable.toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className={styles.pagination}>
          <button
            className={styles.pageButton}
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={currentPage === 1}
          >
            Previous
          </button>

          {Array.from({ length: totalPages }, (_, i) => i + 1)
            .filter((page) => {
              // Show first, last, and pages near current
              if (page === 1 || page === totalPages) return true;
              if (Math.abs(page - currentPage) <= 2) return true;
              return false;
            })
            .map((page, idx, arr) => {
              const showEllipsis = idx > 0 && page - arr[idx - 1] > 1;
              return (
                <span key={page}>
                  {showEllipsis && (
                    <span className={styles.ellipsis}>...</span>
                  )}
                  <button
                    className={
                      page === currentPage
                        ? styles.pageButtonActive
                        : styles.pageButton
                    }
                    onClick={() => setCurrentPage(page)}
                  >
                    {page}
                  </button>
                </span>
              );
            })}

          <button
            className={styles.pageButton}
            onClick={() =>
              setCurrentPage((p) => Math.min(totalPages, p + 1))
            }
            disabled={currentPage === totalPages}
          >
            Next
          </button>
        </div>
      )}

      <div className={styles.paginationSummary}>
        Page {currentPage} of {totalPages} &mdash; Showing{" "}
        {totalProducts === 0 ? 0 : startIndex + 1}-{endIndex} of{" "}
        {totalProducts} results
      </div>
    </div>
  );
};

export default ProductTable;
