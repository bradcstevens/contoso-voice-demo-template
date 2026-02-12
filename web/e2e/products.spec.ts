import { test, expect } from "@playwright/test";

test.describe("Products Catalog - /products page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/products");
  });

  test("should load the products page with correct title", async ({
    page,
  }) => {
    await expect(page).toHaveTitle(/Product Index.*DigiKey/);
    await expect(
      page.getByRole("heading", { name: "Product Index", level: 1 })
    ).toBeVisible();
  });

  test("should display breadcrumb navigation with Home link", async ({
    page,
  }) => {
    const breadcrumb = page.getByRole("navigation", { name: "Breadcrumb" });
    await expect(breadcrumb).toBeVisible();
    await expect(breadcrumb.getByText("Home")).toBeVisible();
    await expect(breadcrumb.getByText("Products")).toBeVisible();
  });

  test("should display all 8 category groups", async ({ page }) => {
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
      await expect(
        page.getByRole("heading", { name, level: 2 })
      ).toBeVisible();
    }
  });

  test("should have category headings that link to correct category pages", async ({
    page,
  }) => {
    // Check that the "Capacitors" heading links to /products/capacitors
    const capacitorsLink = page.getByRole("heading", { name: "Capacitors", level: 2 }).getByRole("link");
    await expect(capacitorsLink).toHaveAttribute("href", "/products/capacitors");

    // Check "Resistors" heading links to /products/resistors
    const resistorsLink = page.getByRole("heading", { name: "Resistors", level: 2 }).getByRole("link");
    await expect(resistorsLink).toHaveAttribute("href", "/products/resistors");
  });

  test("should display product listings under each category with descriptions", async ({
    page,
  }) => {
    // Each category group should have product items listed
    const productItems = page.locator("li").filter({ hasText: /- / });
    const count = await productItems.count();
    // 8 categories * approx 4 products each = ~32 products
    expect(count).toBeGreaterThanOrEqual(8);
  });
});

test.describe("Category Detail Page - /products/[category]", () => {
  test("should load the capacitors category page", async ({ page }) => {
    await page.goto("/products/capacitors");

    await expect(page).toHaveTitle(/Capacitors.*DigiKey/);
    await expect(
      page.getByRole("heading", { name: "Capacitors", level: 1 })
    ).toBeVisible();
  });

  test("should display breadcrumb with Home, Products, and category name", async ({
    page,
  }) => {
    await page.goto("/products/capacitors");

    const breadcrumb = page.getByRole("navigation", { name: "Breadcrumb" });
    await expect(breadcrumb).toBeVisible();
    await expect(breadcrumb.getByText("Home")).toBeVisible();
    await expect(breadcrumb.getByText("Products")).toBeVisible();
    await expect(breadcrumb.getByText("Capacitors")).toBeVisible();
  });

  test("should display a result count", async ({ page }) => {
    await page.goto("/products/capacitors");

    // Should show something like "4 results"
    await expect(page.getByText(/\d+ results?/)).toBeVisible();
  });

  test("should display product cards with images, part numbers, and prices", async ({
    page,
  }) => {
    await page.goto("/products/capacitors");

    // Product cards should be present with product information
    const productCards = page.locator("a").filter({
      has: page.locator("img"),
    });
    const count = await productCards.count();
    expect(count).toBeGreaterThan(0);

    // Each card should show a price
    await expect(page.getByText(/\$\d/).first()).toBeVisible();
  });

  test("should display category description", async ({ page }) => {
    await page.goto("/products/capacitors");

    await expect(
      page.getByText("Essential passive components", { exact: false })
    ).toBeVisible();
  });
});

test.describe("Subcategory/Filter Page - /products/[category]/[subcategory]", () => {
  test("should load the subcategory page with filter sidebar and product table", async ({
    page,
  }) => {
    await page.goto("/products/capacitors/ceramic-capacitors");

    // Page title should display formatted subcategory name
    await expect(
      page.getByRole("heading", { name: "Ceramic Capacitors", level: 1 })
    ).toBeVisible();

    // Filter sidebar should be visible
    await expect(
      page.getByRole("heading", { name: "Refine Results" })
    ).toBeVisible();

    // Product table should be visible
    await expect(page.locator("table")).toBeVisible();
  });

  test("should display breadcrumb with full path on subcategory page", async ({
    page,
  }) => {
    await page.goto("/products/capacitors/ceramic-capacitors");

    const breadcrumb = page.getByRole("navigation", { name: "Breadcrumb" });
    await expect(breadcrumb).toBeVisible();
    await expect(breadcrumb.getByText("Home")).toBeVisible();
    await expect(breadcrumb.getByText("Products")).toBeVisible();
    await expect(
      breadcrumb.getByRole("link", { name: "Capacitors", exact: true })
    ).toBeVisible();
    await expect(breadcrumb.getByText("Ceramic Capacitors")).toBeVisible();
  });

  test("should display the product table with column headers", async ({
    page,
  }) => {
    await page.goto("/products/capacitors/ceramic-capacitors");

    const table = page.locator("table");
    await expect(table).toBeVisible();

    // Check table headers
    const headers = ["Image", "MFR Part #", "Manufacturer", "Description", "Unit Price", "Stock"];
    for (const header of headers) {
      await expect(table.getByText(header, { exact: false })).toBeVisible();
    }
  });

  test("should display result count summary", async ({ page }) => {
    await page.goto("/products/capacitors/ceramic-capacitors");

    // Should show result count like "4 of 4 results" in the title section
    await expect(
      page.getByText(/\d+ of \d+ results?/).first()
    ).toBeVisible();

    // Table summary should also be visible (e.g., "Showing 1-4 of 4 results")
    await expect(
      page.getByText(/Showing \d+-\d+ of \d+ results/).first()
    ).toBeVisible();
  });

  test("should have Apply Filters and Reset Filters buttons", async ({
    page,
  }) => {
    await page.goto("/products/capacitors/ceramic-capacitors");

    await expect(
      page.getByRole("button", { name: "Apply Filters" })
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Reset Filters" })
    ).toBeVisible();
  });
});
