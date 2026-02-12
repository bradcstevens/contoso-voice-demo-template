"use client";

import styles from "./filter-sidebar.module.css";
import type { DigiKeyProduct } from "@/types/digikey";
import { useState, useMemo } from "react";

interface FilterGroup {
  parameterText: string;
  values: { valueText: string; count: number }[];
}

interface FilterSidebarProps {
  products: DigiKeyProduct[];
  onApplyFilters: (filters: Record<string, string[]>) => void;
  onResetFilters: () => void;
}

/**
 * Extract unique parameter groups from a set of products.
 * Each group contains the parameter name and all unique values
 * found across the products, with a count of how many products
 * have that value.
 */
function extractFilterGroups(products: DigiKeyProduct[]): FilterGroup[] {
  const paramMap = new Map<string, Map<string, number>>();

  for (const product of products) {
    for (const param of product.Parameters) {
      if (!param.ParameterText || !param.ValueText) continue;
      if (!paramMap.has(param.ParameterText)) {
        paramMap.set(param.ParameterText, new Map());
      }
      const valueMap = paramMap.get(param.ParameterText)!;
      valueMap.set(param.ValueText, (valueMap.get(param.ValueText) || 0) + 1);
    }
  }

  const groups: FilterGroup[] = [];
  for (const [parameterText, valueMap] of paramMap) {
    // Only show filter groups that have more than 1 unique value
    if (valueMap.size <= 1) continue;
    const values = Array.from(valueMap.entries())
      .map(([valueText, count]) => ({ valueText, count }))
      .sort((a, b) => b.count - a.count);
    groups.push({ parameterText, values });
  }

  // Sort groups by number of values descending
  groups.sort((a, b) => b.values.length - a.values.length);

  // Limit to top 6 filter groups to keep sidebar manageable
  return groups.slice(0, 6);
}

const FilterSidebar = ({
  products,
  onApplyFilters,
  onResetFilters,
}: FilterSidebarProps) => {
  const filterGroups = useMemo(() => extractFilterGroups(products), [products]);
  const [selectedFilters, setSelectedFilters] = useState<
    Record<string, string[]>
  >({});

  const handleCheckboxChange = (
    parameterText: string,
    valueText: string,
    checked: boolean
  ) => {
    setSelectedFilters((prev) => {
      const current = prev[parameterText] || [];
      if (checked) {
        return { ...prev, [parameterText]: [...current, valueText] };
      } else {
        return {
          ...prev,
          [parameterText]: current.filter((v) => v !== valueText),
        };
      }
    });
  };

  const handleApply = () => {
    // Remove empty filter groups before applying
    const cleaned: Record<string, string[]> = {};
    for (const [key, values] of Object.entries(selectedFilters)) {
      if (values.length > 0) {
        cleaned[key] = values;
      }
    }
    onApplyFilters(cleaned);
  };

  const handleReset = () => {
    setSelectedFilters({});
    onResetFilters();
  };

  const hasActiveFilters = Object.values(selectedFilters).some(
    (v) => v.length > 0
  );

  return (
    <aside className={styles.sidebar}>
      <h2 className={styles.sidebarTitle}>Refine Results</h2>

      {filterGroups.length === 0 && (
        <p className={styles.noFilters}>No filters available</p>
      )}

      {filterGroups.map((group) => (
        <div key={group.parameterText} className={styles.filterGroup}>
          <h3 className={styles.groupTitle}>{group.parameterText}</h3>
          <div className={styles.groupOptions}>
            {group.values.map((val) => (
              <label key={val.valueText} className={styles.checkboxLabel}>
                <input
                  type="checkbox"
                  className={styles.checkbox}
                  checked={
                    selectedFilters[group.parameterText]?.includes(
                      val.valueText
                    ) || false
                  }
                  onChange={(e) =>
                    handleCheckboxChange(
                      group.parameterText,
                      val.valueText,
                      e.target.checked
                    )
                  }
                />
                <span className={styles.valueText}>{val.valueText}</span>
                <span className={styles.valueCount}>({val.count})</span>
              </label>
            ))}
          </div>
        </div>
      ))}

      <div className={styles.buttonGroup}>
        <button
          className={styles.applyButton}
          onClick={handleApply}
          disabled={!hasActiveFilters}
        >
          Apply Filters
        </button>
        <button className={styles.resetButton} onClick={handleReset}>
          Reset Filters
        </button>
      </div>
    </aside>
  );
};

export default FilterSidebar;
