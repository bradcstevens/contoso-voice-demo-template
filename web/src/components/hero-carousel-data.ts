/**
 * Hero Carousel Slide Data
 *
 * Configuration for the hero banner carousel slides.
 * Each slide has a background image, text content, and CTA.
 */

export interface CarouselSlide {
  id: string;
  image: string;
  title: string;
  description: string;
  ctaLabel: string;
  ctaHref: string;
  /** Controls the overlay gradient direction for text readability */
  overlayVariant: "light" | "dark";
}

export const CAROUSEL_SLIDES: CarouselSlide[] = [
  {
    id: "shipping",
    image: "/images/04-shipping-boxes.jpg",
    title: "Fast Delivery, Worldwide",
    description:
      "Get your parts faster with DigiKey's industry-leading shipping. Same-day shipping available on in-stock items ordered by 8 PM CT.",
    ctaLabel: "Ship Today",
    ctaHref: "#products",
    overlayVariant: "dark",
  },
  {
    id: "connected-intelligence",
    image: "/images/connected-intelligence.jpg",
    title: "Engineering Connected Intelligence",
    description:
      "The bridge between innovative design and smart devices. DigiKey's global supplier network and technical expertise position us as the ideal partner for engineers.",
    ctaLabel: "Learn More",
    ctaHref: "#products",
    overlayVariant: "dark",
  },
  {
    id: "board-to-build",
    image: "/images/from-board-to-build-using-uno-q-and-app-lab-webinar.jpg",
    title: "From Board to Build",
    description:
      "Explore development platforms and tools to accelerate your next project. Start prototyping with Arduino, Raspberry Pi, and more.",
    ctaLabel: "Explore Dev Tools",
    ctaHref: "#products",
    overlayVariant: "light",
  },
];

/** Auto-play interval in milliseconds */
export const AUTOPLAY_INTERVAL_MS = 5000;
