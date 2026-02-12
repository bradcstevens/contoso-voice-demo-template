import { test, expect } from "@playwright/test";

test.describe("Homepage smoke tests", () => {
  test("should load the homepage successfully", async ({ page }) => {
    const response = await page.goto("/");

    // Verify the page returned a successful HTTP status
    expect(response?.status()).toBeLessThan(400);
  });

  test("should have the correct page title", async ({ page }) => {
    await page.goto("/");

    await expect(page).toHaveTitle(/DigiKey/);
  });

  test("should display the hero banner heading", async ({ page }) => {
    await page.goto("/");

    const heading = page.getByRole("heading", {
      name: "Engineering Connected Intelligence",
    });
    await expect(heading).toBeVisible();
  });

  test("should display the product categories sidebar", async ({ page }) => {
    await page.goto("/");

    const nav = page.getByRole("navigation", {
      name: "Product categories",
    });
    await expect(nav).toBeVisible();
  });
});
