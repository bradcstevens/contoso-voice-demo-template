import styles from "./page.module.css";
import Header from "@/components/header";
import Footer from "@/components/footer";
import ProductImage from "@/components/product-image";
import { getCategories, getProductsByCategory } from "@/store/products";
import {
  formatElectronicsPrice,
  getKeyParameters,
  getDigiKeyPartNumber,
} from "@/types/digikey";
import Link from "next/link";

interface CategoryPageProps {
  params: Promise<{ category: string }>;
}

export async function generateStaticParams() {
  const categories = getCategories();
  return categories.map((cat) => ({
    category: cat.slug,
  }));
}

export async function generateMetadata({ params }: CategoryPageProps) {
  const { category: slug } = await params;
  const categories = getCategories();
  const category = categories.find((c) => c.slug === slug);

  if (!category) {
    return { title: "Category not found | DigiKey" };
  }

  return {
    title: `${category.name} | DigiKey`,
    description: category.description,
  };
}

export default async function CategoryPage({ params }: CategoryPageProps) {
  const { category: slug } = await params;
  const categories = getCategories();
  const category = categories.find((c) => c.slug === slug);

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

  const products = getProductsByCategory(slug);

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
        <span className={styles.breadcrumbCurrent}>{category.name}</span>
      </nav>

      {/* Category Title and Result Count */}
      <div className={styles.titleSection}>
        <h1 className={styles.pageTitle}>{category.name}</h1>
        <span className={styles.resultCount}>
          {products.length} {products.length === 1 ? "result" : "results"}
        </span>
      </div>

      {/* Category Description */}
      <div className={styles.descriptionSection}>
        <p className={styles.categoryDescription}>{category.description}</p>
      </div>

      {/* Product Grid */}
      <main className={styles.content}>
        <div className={styles.productGrid}>
          {products.map((product) => {
            const dkPartNumber = getDigiKeyPartNumber(product);
            const keyParams = getKeyParameters(product, 3);

            return (
              <a
                key={product.ManufacturerProductNumber}
                href="#"
                className={styles.productCard}
              >
                {/* Product Image */}
                <div className={styles.productImageWrapper}>
                  <ProductImage
                    src={product.PhotoUrl}
                    alt={product.Description.ProductDescription}
                    className={styles.productImage}
                  />
                </div>

                {/* Product Info */}
                <div className={styles.productInfo}>
                  <div className={styles.partNumber}>
                    {product.ManufacturerProductNumber}
                  </div>
                  {dkPartNumber && (
                    <div className={styles.dkPartNumber}>{dkPartNumber}</div>
                  )}
                  <div className={styles.manufacturer}>
                    {product.Manufacturer.Name}
                  </div>
                  <div className={styles.description}>
                    {product.Description.ProductDescription}
                  </div>

                  {/* Key Parameters */}
                  {keyParams.length > 0 && (
                    <div className={styles.parameters}>
                      {keyParams.map((param) => (
                        <span
                          key={param.ParameterId}
                          className={styles.paramTag}
                        >
                          {param.ParameterText}: {param.ValueText}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Price and Stock */}
                  <div className={styles.priceRow}>
                    <span className={styles.price}>
                      {formatElectronicsPrice(product.UnitPrice)}
                    </span>
                    <span className={styles.stock}>
                      {product.QuantityAvailable.toLocaleString()} in stock
                    </span>
                  </div>
                </div>
              </a>
            );
          })}
        </div>
      </main>

      <Footer />
    </div>
  );
}
