"use client";

import styles from "./header.module.css";
import { useUserStore } from "@/store/user";
import Link from "next/link";
import usePersistStore from "@/store/usePersistStore";
import { useEffect } from "react";
import { fetchUser } from "@/data/user";

const navLinks = [
  { label: "Products", href: "/products", hasDropdown: true },
  { label: "Manufacturers", href: "/manufacturers", hasDropdown: true },
  { label: "Resources", href: "/resources", hasDropdown: true },
  { label: "Request a Quote", href: "/quote", hasDropdown: false },
];

/** Inline US flag SVG */
function UsFlag() {
  return (
    <svg
      className={styles.flagSvg}
      viewBox="0 0 30 20"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="United States"
    >
      <rect width="30" height="20" fill="#B22234" />
      <rect y="1.54" width="30" height="1.54" fill="#fff" />
      <rect y="4.62" width="30" height="1.54" fill="#fff" />
      <rect y="7.69" width="30" height="1.54" fill="#fff" />
      <rect y="10.77" width="30" height="1.54" fill="#fff" />
      <rect y="13.85" width="30" height="1.54" fill="#fff" />
      <rect y="16.92" width="30" height="1.54" fill="#fff" />
      <rect width="12" height="10.77" fill="#3C3B6E" />
      {/* Simplified stars pattern */}
      <g fill="#fff">
        <circle cx="2" cy="1.5" r="0.5" />
        <circle cx="4" cy="1.5" r="0.5" />
        <circle cx="6" cy="1.5" r="0.5" />
        <circle cx="8" cy="1.5" r="0.5" />
        <circle cx="10" cy="1.5" r="0.5" />
        <circle cx="3" cy="3" r="0.5" />
        <circle cx="5" cy="3" r="0.5" />
        <circle cx="7" cy="3" r="0.5" />
        <circle cx="9" cy="3" r="0.5" />
        <circle cx="2" cy="4.5" r="0.5" />
        <circle cx="4" cy="4.5" r="0.5" />
        <circle cx="6" cy="4.5" r="0.5" />
        <circle cx="8" cy="4.5" r="0.5" />
        <circle cx="10" cy="4.5" r="0.5" />
        <circle cx="3" cy="6" r="0.5" />
        <circle cx="5" cy="6" r="0.5" />
        <circle cx="7" cy="6" r="0.5" />
        <circle cx="9" cy="6" r="0.5" />
        <circle cx="2" cy="7.5" r="0.5" />
        <circle cx="4" cy="7.5" r="0.5" />
        <circle cx="6" cy="7.5" r="0.5" />
        <circle cx="8" cy="7.5" r="0.5" />
        <circle cx="10" cy="7.5" r="0.5" />
        <circle cx="3" cy="9" r="0.5" />
        <circle cx="5" cy="9" r="0.5" />
        <circle cx="7" cy="9" r="0.5" />
        <circle cx="9" cy="9" r="0.5" />
      </g>
    </svg>
  );
}

/** Chevron down icon */
function ChevronDown({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="10"
      height="10"
      viewBox="0 0 10 10"
      fill="none"
    >
      <path
        d="M2.5 3.75L5 6.25L7.5 3.75"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

const Header = () => {
  const userState = usePersistStore(useUserStore, (state) => state);
  const user = usePersistStore(useUserStore, (state) => state.user);

  useEffect(() => {
    if (userState && !userState.user) {
      fetchUser().then((u) => {
        userState.setUser(u.name, u.email, u.image);
      });
    }
  }, [userState]);

  const firstName = user?.name?.split(" ")[0] || "";
  const fullName = user?.name || "Sign In";

  return (
    <header className={styles.header}>
      {/* Top Row: Red background */}
      <div className={styles.topRow}>
        <div className={styles.topRowInner}>
          {/* Logo */}
          <div className={styles.logo}>
            <Link href="/">
              <span className={styles.logoText}>DigiKey</span>
            </Link>
          </div>

          {/* Search Bar */}
          <div className={styles.searchContainer}>
            <input
              type="text"
              className={styles.searchInput}
              placeholder="Enter keyword or part #"
              aria-label="Search products"
            />
            <button className={styles.uploadBtn} aria-label="Upload a list">
              <svg
                width="14"
                height="14"
                viewBox="0 0 14 14"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M7 10V2" />
                <path d="M4 5L7 2L10 5" />
                <path d="M2 10V12H12V10" />
              </svg>
              <span>Upload a List</span>
            </button>
            <button className={styles.searchButton} aria-label="Search">
              <svg
                width="18"
                height="18"
                viewBox="0 0 18 18"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="7.5" cy="7.5" r="5.5" />
                <path d="M12 12L16 16" />
              </svg>
            </button>
          </div>

          {/* Right side: Flag, Account, Cart */}
          <div className={styles.accountArea}>
            <div className={styles.flagIcon}>
              <UsFlag />
            </div>

            <div className={styles.userInfo}>
              <span className={styles.greeting}>
                Hello, {fullName}
              </span>
              <span className={styles.accountLink}>
                Account &amp; Lists
                <ChevronDown className={styles.accountChevron} />
              </span>
            </div>

            <div className={styles.divider} />

            <Link href="/cart" className={styles.cartArea}>
              <svg
                className={styles.cartSvg}
                width="22"
                height="22"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="9" cy="21" r="1" />
                <circle cx="20" cy="21" r="1" />
                <path d="M1 1H5L7.68 14.39C7.77 14.84 8.02 15.25 8.38 15.55C8.74 15.84 9.19 16 9.65 16H19.4C19.86 16 20.31 15.84 20.67 15.55C21.03 15.25 21.28 14.84 21.37 14.39L23 6H6" />
              </svg>
              <span className={styles.cartCount}>
                0 item(s)
                <ChevronDown className={styles.cartChevron} />
              </span>
            </Link>
          </div>
        </div>
      </div>

      {/* Navigation Row */}
      <nav className={styles.navRow}>
        <div className={styles.navInner}>
          <div className={styles.navLinks}>
            {navLinks.map((link) => (
              <Link key={link.href} href={link.href} className={styles.navItem}>
                {link.label}
                {link.hasDropdown && (
                  <ChevronDown className={styles.navChevron} />
                )}
              </Link>
            ))}
          </div>
          <a href="#tariff" className={styles.tariffBtn}>
            Tariff Resource Updates
          </a>
        </div>
      </nav>
    </header>
  );
};

export default Header;
