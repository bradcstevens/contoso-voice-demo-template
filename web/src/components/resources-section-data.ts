/**
 * Data model for the Tools / Services / Content resources section.
 * Separated from the React component so it can be unit-tested
 * without a DOM environment.
 */

export type ResourceLink = {
  label: string;
  href: string;
};

export type ResourceColumn = {
  heading: string;
  iconId: "tools" | "services" | "content";
  links: ResourceLink[];
};

export const RESOURCES_COLUMNS: ResourceColumn[] = [
  {
    heading: "Tools",
    iconId: "tools",
    links: [
      { label: "PCB Builder", href: "#" },
      { label: "Conversion Calculators", href: "#" },
      { label: "Scheme-It", href: "#" },
      { label: "Reference Design Library", href: "#" },
      { label: "Cross Reference", href: "#" },
    ],
  },
  {
    heading: "Services",
    iconId: "services",
    links: [
      { label: "Device Programming", href: "#" },
      { label: "Part Tracing", href: "#" },
      { label: "Digital Solutions", href: "#" },
      { label: "Design & Integration Services", href: "#" },
      { label: "Product Services", href: "#" },
    ],
  },
  {
    heading: "Content",
    iconId: "content",
    links: [
      { label: "New Products", href: "#" },
      { label: "TechForum", href: "#" },
      { label: "Maker.io", href: "#" },
      { label: "Product Training Library", href: "#" },
      { label: "Video Library", href: "#" },
    ],
  },
];
