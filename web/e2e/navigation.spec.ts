import { test, expect } from "@playwright/test";

test.describe("Header Navigation Links", () => {
  test("should navigate to the Products page from header nav", async ({
    page,
  }) => {
    await page.goto("/");

    // Click the Products link in the header nav row
    const nav = page.locator("header nav");
    await nav.getByText("Products").click();

    // Should land on the /products page
    await expect(page).toHaveURL(/\/products$/);
    await expect(
      page.getByRole("heading", { name: "Product Index", level: 1 })
    ).toBeVisible();
  });

  test("should navigate back to homepage via the DigiKey logo", async ({
    page,
  }) => {
    await page.goto("/products");

    // Click the logo to go home
    const header = page.locator("header");
    await header.getByText("DigiKey", { exact: true }).click();

    await expect(page).toHaveURL("/");
    await expect(
      page.getByRole("heading", { name: "Engineering Connected Intelligence" })
    ).toBeVisible();
  });
});

test.describe("Breadcrumb Navigation", () => {
  test("should navigate from products page to home via breadcrumb", async ({
    page,
  }) => {
    await page.goto("/products");

    const breadcrumb = page.getByRole("navigation", { name: "Breadcrumb" });
    await breadcrumb.getByText("Home").click();

    await expect(page).toHaveURL("/");
  });

  test("should navigate from category page to products page via breadcrumb", async ({
    page,
  }) => {
    await page.goto("/products/capacitors");

    const breadcrumb = page.getByRole("navigation", { name: "Breadcrumb" });
    await breadcrumb.getByText("Products").click();

    await expect(page).toHaveURL(/\/products$/);
    await expect(
      page.getByRole("heading", { name: "Product Index", level: 1 })
    ).toBeVisible();
  });

  test("should navigate from subcategory page to category page via breadcrumb", async ({
    page,
  }) => {
    await page.goto("/products/capacitors/ceramic-capacitors");

    const breadcrumb = page.getByRole("navigation", { name: "Breadcrumb" });
    await breadcrumb.getByRole("link", { name: "Capacitors", exact: true }).click();

    await expect(page).toHaveURL(/\/products\/capacitors$/);
    await expect(
      page.getByRole("heading", { name: "Capacitors", level: 1 })
    ).toBeVisible();
  });

  test("should navigate from subcategory page to home via breadcrumb", async ({
    page,
  }) => {
    await page.goto("/products/capacitors/ceramic-capacitors");

    const breadcrumb = page.getByRole("navigation", { name: "Breadcrumb" });
    await breadcrumb.getByText("Home").click();

    await expect(page).toHaveURL("/");
  });
});

test.describe("Category Navigation Flows", () => {
  test("should navigate from products index to a category page by clicking a category heading", async ({
    page,
  }) => {
    await page.goto("/products");

    // Click the "Resistors" category heading link
    const resistorsHeading = page
      .getByRole("heading", { name: "Resistors", level: 2 })
      .getByRole("link");
    await resistorsHeading.click();

    await expect(page).toHaveURL(/\/products\/resistors$/);
    await expect(
      page.getByRole("heading", { name: "Resistors", level: 1 })
    ).toBeVisible();
  });

  test("should complete a full navigation flow: Home -> Products -> Category -> Home", async ({
    page,
  }) => {
    // Start at home
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: "Engineering Connected Intelligence" })
    ).toBeVisible();

    // Navigate to Products via header
    const nav = page.locator("header nav");
    await nav.getByText("Products").click();
    await expect(page).toHaveURL(/\/products$/);

    // Navigate to a category
    const switchesHeading = page
      .getByRole("heading", { name: "Switches", level: 2 })
      .getByRole("link");
    await switchesHeading.click();
    await expect(page).toHaveURL(/\/products\/switches$/);
    await expect(
      page.getByRole("heading", { name: "Switches", level: 1 })
    ).toBeVisible();

    // Navigate back home via breadcrumb
    const breadcrumb = page.getByRole("navigation", { name: "Breadcrumb" });
    await breadcrumb.getByText("Home").click();
    await expect(page).toHaveURL("/");
  });
});

test.describe("Homepage Category Sidebar Links", () => {
  test("should have category sidebar links that anchor to category sections", async ({
    page,
  }) => {
    await page.goto("/");

    const sidebar = page.getByRole("navigation", {
      name: "Product categories",
    });

    // Each category link should use an anchor href
    const capacitorsLink = sidebar.getByText("Capacitors");
    await expect(capacitorsLink).toBeVisible();
    await expect(capacitorsLink).toHaveAttribute("href", "#capacitors");
  });

  test("should scroll to category section when clicking a sidebar link", async ({
    page,
  }) => {
    await page.goto("/");

    const sidebar = page.getByRole("navigation", {
      name: "Product categories",
    });

    // Click the Switches link (last category, likely below fold)
    await sidebar.getByText("Switches").click();

    // The URL should have the anchor
    await expect(page).toHaveURL(/#switches$/);

    // The Switches section heading should be visible after scrolling
    const switchesHeading = page.locator(
      'section#switches h2:text-is("Switches")'
    );
    await expect(switchesHeading).toBeVisible();
  });
});
