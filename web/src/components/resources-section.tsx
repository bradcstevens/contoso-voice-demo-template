import styles from "./resources-section.module.css";
import { RESOURCES_COLUMNS } from "./resources-section-data";

/**
 * SVG icons matching DigiKey's Tools / Services / Content section.
 * Each icon is a large decorative illustration placed on the right of the card.
 */
function ResourceIcon({ id }: { id: "tools" | "services" | "content" }) {
  switch (id) {
    case "tools":
      return (
        <svg
          className={styles.icon}
          viewBox="0 0 120 120"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          {/* Red circle ring */}
          <circle cx="60" cy="60" r="48" stroke="#cc0000" strokeWidth="20" />
          {/* Notch at top-left */}
          <rect x="10" y="8" width="22" height="22" rx="2" fill="white" />
          {/* Hexagon in center */}
          <polygon
            points="60,28 87.7,44 87.7,76 60,92 32.3,76 32.3,44"
            fill="none"
            stroke="#1a1a1a"
            strokeWidth="5"
            strokeLinejoin="round"
          />
        </svg>
      );
    case "services":
      return (
        <svg
          className={styles.icon}
          viewBox="0 0 100 130"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          {/* Red rectangle body */}
          <rect x="10" y="20" width="80" height="100" rx="4" fill="#cc0000" />
          {/* Clipboard clip at top */}
          <rect
            x="30"
            y="8"
            width="40"
            height="24"
            rx="3"
            fill="none"
            stroke="#1a1a1a"
            strokeWidth="4"
          />
          <rect x="38" y="4" width="24" height="12" rx="2" fill="white" />
          {/* Inner lines representing a document */}
          <line
            x1="26"
            y1="56"
            x2="74"
            y2="56"
            stroke="white"
            strokeWidth="3"
            strokeLinecap="round"
          />
          <line
            x1="26"
            y1="70"
            x2="74"
            y2="70"
            stroke="white"
            strokeWidth="3"
            strokeLinecap="round"
          />
          <line
            x1="26"
            y1="84"
            x2="58"
            y2="84"
            stroke="white"
            strokeWidth="3"
            strokeLinecap="round"
          />
          <line
            x1="26"
            y1="98"
            x2="66"
            y2="98"
            stroke="white"
            strokeWidth="3"
            strokeLinecap="round"
          />
        </svg>
      );
    case "content":
      return (
        <svg
          className={styles.icon}
          viewBox="0 0 120 120"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          {/* Red rectangle / screen */}
          <rect x="10" y="8" width="100" height="74" rx="4" fill="#cc0000" />
          {/* Play button triangle */}
          <polygon points="52,24 52,64 82,44" fill="white" />
          {/* Monitor stand */}
          <rect x="28" y="86" width="64" height="6" rx="1" fill="#1a1a1a" />
          <line
            x1="60"
            y1="92"
            x2="60"
            y2="106"
            stroke="#1a1a1a"
            strokeWidth="5"
          />
          <line
            x1="38"
            y1="106"
            x2="82"
            y2="106"
            stroke="#1a1a1a"
            strokeWidth="5"
            strokeLinecap="round"
          />
        </svg>
      );
  }
}

/**
 * ResourcesSection
 *
 * A three-column white-card section displaying Tools, Services, and Content
 * links with decorative SVG icons, matching the DigiKey homepage layout.
 */
const ResourcesSection = () => {
  return (
    <section className={styles.resourcesSection} aria-label="Resources">
      <div className={styles.resourcesInner}>
        {RESOURCES_COLUMNS.map((column) => (
          <div key={column.heading} className={styles.card}>
            <div className={styles.cardBody}>
              <h2 className={styles.columnHeading}>{column.heading}</h2>
              <ul className={styles.linkList}>
                {column.links.map((link) => (
                  <li key={link.label} className={styles.linkItem}>
                    <a href={link.href} className={styles.link}>
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
            <div className={styles.cardIcon}>
              <ResourceIcon id={column.iconId} />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};

export default ResourcesSection;
