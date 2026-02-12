import styles from "./value-props.module.css";

const props = [
  {
    icon: "support",
    title: "Top quality support",
    text: "A full suite of design and purchasing tools to help you on your journey",
  },
  {
    icon: "distribution",
    title: "Authorized Distribution",
    text: "Fully authorized supply chain for buyer confidence",
  },
  {
    icon: "breadth",
    title: "Breadth of Product",
    text: "Over 17.6 million products available",
  },
];

function PropIcon({ id }: { id: string }) {
  switch (id) {
    case "support":
      return (
        <svg className={styles.icon} viewBox="0 0 40 40" fill="none" aria-hidden="true">
          <circle cx="20" cy="20" r="18" stroke="#cc0000" strokeWidth="3" fill="none" />
          <circle cx="20" cy="20" r="6" fill="#cc0000" />
        </svg>
      );
    case "distribution":
      return (
        <svg className={styles.icon} viewBox="0 0 40 40" fill="none" aria-hidden="true">
          <path d="M8 32V12L20 6L32 12V32H8Z" fill="#cc0000" />
          <rect x="16" y="22" width="8" height="10" fill="white" />
          <rect x="14" y="14" width="12" height="6" rx="1" fill="white" opacity="0.6" />
        </svg>
      );
    case "breadth":
      return (
        <svg className={styles.icon} viewBox="0 0 40 40" fill="none" aria-hidden="true">
          <rect x="6" y="10" width="28" height="22" rx="2" fill="#cc0000" />
          <rect x="10" y="14" width="20" height="4" rx="1" fill="white" />
          <rect x="10" y="21" width="14" height="4" rx="1" fill="white" />
        </svg>
      );
    default:
      return null;
  }
}

export default function ValueProps() {
  return (
    <section className={styles.section} aria-label="Why DigiKey">
      <div className={styles.inner}>
        {props.map((prop) => (
          <div key={prop.icon} className={styles.card}>
            <PropIcon id={prop.icon} />
            <div className={styles.cardText}>
              <div className={styles.cardTitle}>{prop.title}</div>
              <div className={styles.cardDesc}>{prop.text}</div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
