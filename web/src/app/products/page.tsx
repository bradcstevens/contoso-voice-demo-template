import styles from "./page.module.css";
import Header from "@/components/header";
import Footer from "@/components/footer";
import { getCategories } from "@/store/products";
import Link from "next/link";

export const metadata = {
  title: "Product Index | DigiKey",
  description:
    "Browse the complete DigiKey product catalog organized by category. Find capacitors, resistors, ICs, connectors, development boards, sensors, LEDs, switches, and more.",
};

const ProductsPage = () => {
  const categories = getCategories();

  return (
    <div className={styles.page}>
      <Header />

      {/* Breadcrumb */}
      <nav className={styles.breadcrumb} aria-label="Breadcrumb">
        <Link href="/" className={styles.breadcrumbLink}>
          Home
        </Link>
        <span className={styles.breadcrumbSeparator}>/</span>
        <span className={styles.breadcrumbCurrent}>Products</span>
      </nav>

      {/* Page Title */}
      <div className={styles.titleSection}>
        <h1 className={styles.pageTitle}>Product Index</h1>
      </div>

      {/* Category Grid */}
      <main className={styles.content}>
        <div className={styles.categoryGrid}>
          {categories.map((category) => (
            <div key={category.slug} className={styles.categoryGroup}>
              <h2 className={styles.categoryHeading}>
                <Link
                  href={`/products/${category.slug}`}
                  className={styles.categoryHeadingLink}
                >
                  {category.name}
                </Link>
              </h2>
              <ul className={styles.productList}>
                {category.products.map((product) => (
                  <li
                    key={product.ManufacturerProductNumber}
                    className={styles.productItem}
                  >
                    <Link
                      href={product.ProductUrl || "#"}
                      className={styles.productLink}
                    >
                      {product.Description.ProductDescription}
                    </Link>
                    <span className={styles.productMfr}>
                      - {product.Manufacturer.Name}{" "}
                      {product.ManufacturerProductNumber}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </main>

      <Footer />
    </div>
  );
};

export default ProductsPage;
