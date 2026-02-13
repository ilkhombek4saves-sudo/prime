import { test, expect } from "@playwright/test";

test("login page opens", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByText("Admin Login")).toBeVisible();
});
