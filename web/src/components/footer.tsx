import styles from "./footer.module.css";
import Link from "next/link";
import {
  FaFacebook,
  FaXTwitter,
  FaYoutube,
  FaLinkedin,
  FaInstagram,
  FaTiktok,
  FaPhone,
  FaLocationDot,
  FaApple,
} from "react-icons/fa6";
import { FaGooglePlay } from "react-icons/fa";
import { IoMail } from "react-icons/io5";
import { HiShieldCheck } from "react-icons/hi2";

const Footer = () => {
  const currentYear = new Date().getFullYear();

  return (
    <footer>
      {/* Newsletter Signup Bar */}
      <div className={styles.newsletterBar}>
        <div className={styles.newsletterInner}>
          <span className={styles.newsletterText}>
            Get the latest tech insights
          </span>
          <div className={styles.newsletterForm}>
            <input
              type="email"
              placeholder="Enter your email"
              className={styles.newsletterInput}
              aria-label="Email address for newsletter"
            />
            <button type="button" className={styles.subscribeButton}>
              Subscribe
            </button>
          </div>
        </div>
        <div className={styles.newsletterConsent}>
          <input type="checkbox" id="newsletter-consent" />
          <label htmlFor="newsletter-consent">
            I agree to receive marketing emails from DigiKey.{" "}
            <Link href="#">Learn more</Link> |{" "}
            <Link href="#">Privacy Policy</Link>
          </label>
        </div>
      </div>

      {/* Main Footer */}
      <div className={styles.footer}>
        <div className={styles.footerInner}>
          {/* Introduction Column */}
          <div className={styles.footerColumn}>
            <div className={styles.columnTitle}>Introduction</div>
            <div className={styles.columnLinks}>
              <Link href="#">About DigiKey</Link>
              <Link href="#">Help &amp; Support</Link>
              <Link href="#">Press Releases</Link>
              <Link href="#">Careers</Link>
              <Link href="#">News</Link>
              <Link href="#">Newsroom</Link>
              <Link href="#">Blog</Link>
            </div>
          </div>

          {/* Help Column */}
          <div className={styles.footerColumn}>
            <div className={styles.columnTitle}>Help</div>
            <div className={styles.columnLinks}>
              <Link href="#">Ordering Help</Link>
              <Link href="#">Shipping &amp; Delivery</Link>
              <Link href="#">Returns</Link>
              <Link href="#">Digi-Key Part Number Search</Link>
              <Link href="#">Manufacturer Part Number</Link>
              <Link href="#">Staff Resources</Link>
            </div>
          </div>

          {/* Contact Us Column */}
          <div className={styles.footerColumn}>
            <div className={styles.columnTitle}>Contact Us</div>
            <div className={styles.contactItem}>
              <FaPhone className={styles.contactIcon} size={14} />
              <span>Sales</span>
            </div>
            <div className={styles.contactItem}>
              <FaPhone className={styles.contactIcon} size={14} />
              <a href="tel:18003444539">1-800-344-4539</a>
            </div>
            <div className={styles.contactItem}>
              <IoMail className={styles.contactIcon} size={14} />
              <a href="mailto:sales@digikey.com">sales@digikey.com</a>
            </div>
            <div className={styles.contactItem}>
              <FaLocationDot className={styles.contactIcon} size={14} />
              <span>
                701 Brooks Ave South
                <br />
                Thief River Falls, MN 56701
              </span>
            </div>
          </div>

          {/* Follow Us Column */}
          <div className={styles.footerColumn}>
            <div className={styles.columnTitle}>Follow Us</div>
            <div className={styles.socialIcons}>
              <Link
                href="https://facebook.com/digikey"
                aria-label="Facebook"
                className={styles.socialIcon}
                target="_blank"
                rel="noopener noreferrer"
              >
                <FaFacebook />
              </Link>
              <Link
                href="https://twitter.com/diaboreg"
                aria-label="X (Twitter)"
                className={styles.socialIcon}
                target="_blank"
                rel="noopener noreferrer"
              >
                <FaXTwitter />
              </Link>
              <Link
                href="https://youtube.com/digikey"
                aria-label="YouTube"
                className={styles.socialIcon}
                target="_blank"
                rel="noopener noreferrer"
              >
                <FaYoutube />
              </Link>
              <Link
                href="https://linkedin.com/company/digikey"
                aria-label="LinkedIn"
                className={styles.socialIcon}
                target="_blank"
                rel="noopener noreferrer"
              >
                <FaLinkedin />
              </Link>
              <Link
                href="https://instagram.com/digikey"
                aria-label="Instagram"
                className={styles.socialIcon}
                target="_blank"
                rel="noopener noreferrer"
              >
                <FaInstagram />
              </Link>
              <Link
                href="https://tiktok.com/@digikey"
                aria-label="TikTok"
                className={styles.socialIcon}
                target="_blank"
                rel="noopener noreferrer"
              >
                <FaTiktok />
              </Link>
            </div>

            {/* App Store Badges */}
            <div className={styles.appBadges}>
              <Link
                href="#"
                className={styles.appBadge}
                aria-label="Download on the App Store"
              >
                <FaApple className={styles.appBadgeIcon} />
                <span className={styles.appBadgeText}>
                  <span className={styles.appBadgeSmall}>Download on the</span>
                  App Store
                </span>
              </Link>
              <Link
                href="#"
                className={styles.appBadge}
                aria-label="Get it on Google Play"
              >
                <FaGooglePlay className={styles.appBadgeIcon} />
                <span className={styles.appBadgeText}>
                  <span className={styles.appBadgeSmall}>Get it on</span>
                  Google Play
                </span>
              </Link>
            </div>
          </div>
        </div>

        {/* Certifications */}
        <div className={styles.certifications}>
          <div className={styles.certificationsInner}>
            <div className={styles.certBadge}>
              <HiShieldCheck className={styles.certBadgeIcon} />
              ECIA MEMBER
            </div>
            <div className={styles.certBadge}>
              <HiShieldCheck className={styles.certBadgeIcon} />
              ERAI Authorized
            </div>
          </div>
        </div>
      </div>

      {/* Copyright Bar */}
      <div className={styles.copyrightBar}>
        <div className={styles.copyrightInner}>
          <span className={styles.countryIndicator}>
            {/* US Flag inline SVG */}
            <svg
              className={styles.flag}
              viewBox="0 0 20 14"
              xmlns="http://www.w3.org/2000/svg"
              aria-hidden="true"
            >
              <rect width="20" height="14" fill="#B22234" />
              <rect y="1.077" width="20" height="1.077" fill="#fff" />
              <rect y="3.231" width="20" height="1.077" fill="#fff" />
              <rect y="5.385" width="20" height="1.077" fill="#fff" />
              <rect y="7.538" width="20" height="1.077" fill="#fff" />
              <rect y="9.692" width="20" height="1.077" fill="#fff" />
              <rect y="11.846" width="20" height="1.077" fill="#fff" />
              <rect width="8" height="7.538" fill="#3C3B6E" />
            </svg>
            United States
          </span>
          <span className={styles.copyrightText}>
            Copyright &copy; 1995-{currentYear} DigiKey
          </span>
          <span className={styles.copyrightSeparator}>|</span>
          <span className={styles.copyrightText}>All Rights Reserved</span>
          <span className={styles.copyrightSeparator}>|</span>
          <div className={styles.copyrightLinks}>
            <Link href="#">Terms of Use</Link>
            <span className={styles.copyrightSeparator}>|</span>
            <Link href="#">Privacy Policy</Link>
            <span className={styles.copyrightSeparator}>|</span>
            <Link href="#">Accessibility Statement</Link>
            <span className={styles.copyrightSeparator}>|</span>
            <Link href="#">Cookie Settings</Link>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
