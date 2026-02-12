"use client";

import { useState, useEffect, useCallback } from "react";
import styles from "./hero-carousel.module.css";

interface Slide {
  image: string;
  title: string;
  subtitle?: string;
  text: string;
  bullets?: string[];
  cta: string;
  href: string;
}

const slides: Slide[] = [
  {
    image: "/images/04-shipping-boxes.jpg",
    title:
      "The world's largest selection of electronic components in stock for immediate shipment!",
    text: "",
    cta: "Delivery time and cost",
    href: "#products",
  },
  {
    image: "/images/connected-intelligence.jpg",
    title: "Engineering Connected Intelligence",
    text: "DigiKey's global supplier network and technical expertise position us as the ideal partner for engineers creating the systems of tomorrow.",
    cta: "Learn More",
    href: "#products",
  },
  {
    image: "/images/from-board-to-build-using-uno-q-and-app-lab-webinar.jpg",
    title: "Join us for a webinar with Arduino",
    text: "From board to build: Using UNO Q and app lab",
    bullets: ["Date: February 12, 2026", "Time: 9:00 AM CST"],
    cta: "Register now",
    href: "#products",
  },
];

const AUTOPLAY_INTERVAL = 6000;

export default function HeroCarousel() {
  const [current, setCurrent] = useState(0);
  const [paused, setPaused] = useState(false);

  const goTo = useCallback((index: number) => {
    setCurrent(index);
  }, []);

  const next = useCallback(() => {
    setCurrent((prev) => (prev + 1) % slides.length);
  }, []);

  const prev = useCallback(() => {
    setCurrent((prev) => (prev - 1 + slides.length) % slides.length);
  }, []);

  useEffect(() => {
    if (paused) return;
    const timer = setInterval(next, AUTOPLAY_INTERVAL);
    return () => clearInterval(timer);
  }, [paused, next]);

  return (
    <div
      className={styles.carousel}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      role="region"
      aria-label="Hero carousel"
      aria-roledescription="carousel"
    >
      {/* Slides */}
      {slides.map((slide, i) => (
        <div
          key={i}
          className={`${styles.slide} ${i === current ? styles.slideActive : ""}`}
          role="group"
          aria-roledescription="slide"
          aria-label={`Slide ${i + 1} of ${slides.length}`}
          aria-hidden={i !== current}
        >
          <div
            className={styles.slideImage}
            style={{ backgroundImage: `url(${slide.image})` }}
          />
          <div className={styles.slideOverlay} />
          <div className={styles.slideContent}>
            <h2 className={styles.slideTitle}>{slide.title}</h2>
            {slide.text && <p className={styles.slideText}>{slide.text}</p>}
            {slide.bullets && (
              <ul className={styles.slideBullets}>
                {slide.bullets.map((b, idx) => (
                  <li key={idx}>{b}</li>
                ))}
              </ul>
            )}
            <a href={slide.href} className={styles.slideCta}>
              {slide.cta}
            </a>
          </div>
        </div>
      ))}

      {/* Arrow buttons (visible on hover) */}
      <button
        className={`${styles.arrow} ${styles.arrowLeft}`}
        onClick={prev}
        aria-label="Previous slide"
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <path
            d="M12.5 15L7.5 10L12.5 5"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      <button
        className={`${styles.arrow} ${styles.arrowRight}`}
        onClick={next}
        aria-label="Next slide"
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <path
            d="M7.5 15L12.5 10L7.5 5"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {/* Dot indicators */}
      <div className={styles.dots} role="tablist" aria-label="Slide controls">
        {slides.map((_, i) => (
          <button
            key={i}
            className={`${styles.dot} ${i === current ? styles.dotActive : ""}`}
            onClick={() => goTo(i)}
            role="tab"
            aria-selected={i === current}
            aria-label={`Go to slide ${i + 1}`}
          />
        ))}
      </div>
    </div>
  );
}
