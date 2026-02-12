import styles from "./company-description.module.css";

export default function CompanyDescription() {
  return (
    <section className={styles.section}>
      <div className={styles.inner}>
        <p className={styles.text}>
          DigiKey is your leading global distributor of electronic components and
          automation products, trusted by engineers, designers, and procurement
          professionals worldwide. We provide one of the industry&apos;s widest
          selections of authorized components, all backed by robust online
          resources, design tools, and 24/7 customer support to help bring ideas
          to life faster. From our single, state-of-the-art distribution center
          in Thief River Falls, Minnesota, we ensure fast, reliable delivery,
          consistent quality, and seamless service to customers around the globe.
        </p>
      </div>
    </section>
  );
}
