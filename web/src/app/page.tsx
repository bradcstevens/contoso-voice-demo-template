import styles from "./page.module.css";
import { getCategories } from "@/store/products";
import Chat from "@/components/messaging/chat";
import Section from "@/components/section";
import ResourcesSection from "@/components/resources-section";
import FeaturedProducts from "@/components/featured-products";
import FeaturedManufacturers from "@/components/featured-manufacturers";
import ValueProps from "@/components/value-props";
import CompanyDescription from "@/components/company-description";
import Voice from "@/components/messaging/voice";
import Header from "@/components/header";
import Footer from "@/components/footer";
import HeroCarousel from "@/components/hero-carousel";

const Home = async () => {
  const categories = getCategories();

  return (
    <>
      <Header />

      {/* Hero Section: Sidebar + Carousel */}
      <div className={styles.heroWrapper}>
        {/* Left sidebar - Product categories */}
        <nav className={styles.categorySidebar} aria-label="Product categories">
          <div className={styles.sidebarHeader}>
            <span className={styles.sidebarTitle}>Products</span>
            <a href="#products" className={styles.sidebarViewAll}>
              View All
            </a>
          </div>
          <ul className={styles.categoryList}>
            {categories.map((category) => (
              <li key={category.slug} className={styles.categoryItem}>
                <a
                  href={`#${category.slug}`}
                  className={styles.categoryLink}
                >
                  {category.name}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        {/* Hero carousel */}
        <HeroCarousel />
      </div>

      {/* Tools / Services / Content resources section */}
      <ResourcesSection />

      {/* Featured products with manufacturer badges */}
      <FeaturedProducts />

      {/* Featured manufacturers logo carousel */}
      <FeaturedManufacturers />

      {/* Value proposition bar */}
      <ValueProps />

      {/* Company description */}
      <CompanyDescription />

      {/* Product category sections */}
      <div id="products">
        {categories.map((category, i) => (
          <Section key={category.slug} index={i} category={category} />
        ))}
      </div>

      <Chat options={{ video: true, file: true }} />
      <Voice />
      <Footer />
    </>
  );
};

export default Home;
