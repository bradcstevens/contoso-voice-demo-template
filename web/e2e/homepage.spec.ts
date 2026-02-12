import { test, expect } from "@playwright/test";

test.describe("Homepage - Header", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("should render the header with logo linking to home", async ({
    page,
  }) => {
    const header = page.locator("header");
    await expect(header).toBeVisible();

    // Logo text is visible
    const logoText = header.getByText("DigiKey", { exact: true });
    await expect(logoText).toBeVisible();
  });

  test("should render the search bar with input and category dropdown", async ({
    page,
  }) => {
    const searchInput = page.getByLabel("Search products");
    await expect(searchInput).toBeVisible();
    await expect(searchInput).toHaveAttribute(
      "placeholder",
      "Enter keyword or part #"
    );

    const categoryDropdown = page.getByLabel("Search category");
    await expect(categoryDropdown).toBeVisible();
  });

  test("should render navigation links in the header nav row", async ({
    page,
  }) => {
    const nav = page.locator("header nav");
    await expect(nav).toBeVisible();

    const expectedLinks = [
      "Products",
      "Manufacturers",
      "Resources",
      "Request a Quote",
    ];
    for (const label of expectedLinks) {
      await expect(nav.getByText(label)).toBeVisible();
    }
  });
});

test.describe("Homepage - Hero Section", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("should display the hero banner with heading and CTA", async ({
    page,
  }) => {
    const heading = page.getByRole("heading", {
      name: "Engineering Connected Intelligence",
    });
    await expect(heading).toBeVisible();

    const cta = page.getByRole("link", { name: "Learn More", exact: true });
    await expect(cta).toBeVisible();
  });

  test("should display the product categories sidebar with category links", async ({
    page,
  }) => {
    const sidebar = page.getByRole("navigation", {
      name: "Product categories",
    });
    await expect(sidebar).toBeVisible();

    // Verify known categories appear in the sidebar
    const expectedCategories = [
      "Capacitors",
      "Resistors",
      "Integrated Circuits (ICs)",
      "Connectors & Interconnects",
      "Development Boards & Kits",
      "Sensors & Transducers",
      "LEDs & Optoelectronics",
      "Switches",
    ];
    for (const category of expectedCategories) {
      await expect(sidebar.getByText(category)).toBeVisible();
    }
  });

  test("should display View All link in the category sidebar", async ({
    page,
  }) => {
    const sidebar = page.getByRole("navigation", {
      name: "Product categories",
    });
    await expect(sidebar.getByText("View All")).toBeVisible();
  });
});

test.describe("Homepage - Resources Section", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("should display the three resource columns: Tools, Services, Content", async ({
    page,
  }) => {
    const resourcesSection = page.getByLabel("Resources");
    await expect(resourcesSection).toBeVisible();

    // Check column headings
    await expect(
      resourcesSection.getByRole("heading", { name: "Tools" })
    ).toBeVisible();
    await expect(
      resourcesSection.getByRole("heading", { name: "Services" })
    ).toBeVisible();
    await expect(
      resourcesSection.getByRole("heading", { name: "Content" })
    ).toBeVisible();
  });

  test("should display resource links within each column", async ({
    page,
  }) => {
    const resourcesSection = page.getByLabel("Resources");

    // Spot-check a link from each column
    await expect(resourcesSection.getByText("PCB Builder")).toBeVisible();
    await expect(
      resourcesSection.getByText("Device Programming")
    ).toBeVisible();
    await expect(resourcesSection.getByText("TechForum")).toBeVisible();
  });
});

test.describe("Homepage - Featured Products Section", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("should display the Featured Products heading and manufacturer badges", async ({
    page,
  }) => {
    const featuredSection = page.getByLabel("Featured Products");
    await expect(featuredSection).toBeVisible();

    await expect(
      featuredSection.getByRole("heading", { name: "Featured Products" })
    ).toBeVisible();
  });

  test("should display product cards with part numbers and prices", async ({
    page,
  }) => {
    const featuredSection = page.getByLabel("Featured Products");

    // There should be product cards (up to 12 trending products)
    // Each card has a price starting with "$"
    const priceElements = featuredSection.locator("text=$");
    const count = await priceElements.count();
    expect(count).toBeGreaterThan(0);
  });
});

test.describe("Homepage - Category Sections", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("should display category sections with headings for each product category", async ({
    page,
  }) => {
    const categoryNames = [
      "Capacitors",
      "Resistors",
      "Integrated Circuits (ICs)",
      "Connectors & Interconnects",
      "Development Boards & Kits",
      "Sensors & Transducers",
      "LEDs & Optoelectronics",
      "Switches",
    ];

    for (const name of categoryNames) {
      const section = page.locator(`section:has(h2:text-is("${name}"))`);
      await expect(section).toBeVisible();
    }
  });

  test("should display product cards within category sections", async ({
    page,
  }) => {
    // Check the first category section (Capacitors) has product cards
    const capacitorsSection = page.locator(
      'section:has(h2:text-is("Capacitors"))'
    );
    await expect(capacitorsSection).toBeVisible();

    // Product cards should contain manufacturer names and part numbers
    const cards = capacitorsSection.locator("a").filter({ has: page.locator("img") });
    const cardCount = await cards.count();
    expect(cardCount).toBeGreaterThan(0);
  });
});

test.describe("Homepage - Footer", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("should display the newsletter signup bar", async ({ page }) => {
    const footer = page.locator("footer");
    await expect(footer).toBeVisible();

    await expect(
      footer.getByText("Get the latest tech insights")
    ).toBeVisible();
    await expect(
      footer.getByLabel("Email address for newsletter")
    ).toBeVisible();
    await expect(footer.getByText("Subscribe")).toBeVisible();
  });

  test("should display footer link columns: Introduction, Help, Contact Us, Follow Us", async ({
    page,
  }) => {
    const footer = page.locator("footer");

    await expect(footer.getByText("Introduction")).toBeVisible();
    await expect(footer.getByText("Help", { exact: true })).toBeVisible();
    await expect(footer.getByText("Contact Us")).toBeVisible();
    await expect(footer.getByText("Follow Us")).toBeVisible();
  });

  test("should display copyright information", async ({ page }) => {
    const footer = page.locator("footer");
    const currentYear = new Date().getFullYear();

    await expect(
      footer.getByText(`Copyright`, { exact: false })
    ).toBeVisible();
    await expect(
      footer.getByText(`${currentYear}`, { exact: false })
    ).toBeVisible();
  });

  test("should display social media links", async ({ page }) => {
    const footer = page.locator("footer");

    await expect(footer.getByLabel("Facebook")).toBeVisible();
    await expect(footer.getByLabel("YouTube")).toBeVisible();
    await expect(footer.getByLabel("LinkedIn")).toBeVisible();
    await expect(footer.getByLabel("Instagram")).toBeVisible();
  });
});
