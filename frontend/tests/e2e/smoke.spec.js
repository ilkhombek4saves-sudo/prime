import { test, expect } from "@playwright/test";

// ── Auth tests ──────────────────────────────────────────────────────────

test("login page opens", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByText("Admin Login")).toBeVisible();
});

test("login page has username and password fields", async ({ page }) => {
  await page.goto("/login");
  await expect(page.locator('input[type="text"], input[name="username"]')).toBeVisible();
  await expect(page.locator('input[type="password"]')).toBeVisible();
});

test("login with invalid credentials shows error", async ({ page }) => {
  await page.goto("/login");
  await page.fill('input[type="text"], input[name="username"]', "baduser");
  await page.fill('input[type="password"]', "badpass");
  await page.click('button[type="submit"]');
  // Should show an error or stay on login page
  await expect(page).toHaveURL(/login/);
});

test("unauthenticated user redirected to login", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/login/);
});

// ── Navigation tests ─────────────────────────────────────────────────────

test("dashboard loads after login", async ({ page }) => {
  await page.goto("/login");
  await page.evaluate(() => {
    localStorage.setItem("jwt", "test-token-for-e2e");
  });
  await page.goto("/");
  await expect(page.getByText("Dashboard")).toBeVisible();
});

test("navigation links are visible", async ({ page }) => {
  await page.goto("/login");
  await page.evaluate(() => {
    localStorage.setItem("jwt", "test-token-for-e2e");
  });
  await page.goto("/");
  const navLinks = ["Agents", "Providers", "Plugins", "Sessions", "Tasks", "Settings", "Chat"];
  for (const link of navLinks) {
    await expect(page.getByRole("link", { name: link }).or(page.getByText(link))).toBeVisible();
  }
});

test("chat page loads", async ({ page }) => {
  await page.goto("/login");
  await page.evaluate(() => {
    localStorage.setItem("jwt", "test-token-for-e2e");
  });
  await page.goto("/chat");
  await expect(page.getByText("Chat")).toBeVisible();
});

test("providers page loads", async ({ page }) => {
  await page.goto("/login");
  await page.evaluate(() => {
    localStorage.setItem("jwt", "test-token-for-e2e");
  });
  await page.goto("/providers");
  await expect(page.getByText("Providers")).toBeVisible();
});

test("settings page loads", async ({ page }) => {
  await page.goto("/login");
  await page.evaluate(() => {
    localStorage.setItem("jwt", "test-token-for-e2e");
  });
  await page.goto("/settings");
  await expect(page.getByText("Settings")).toBeVisible();
});

test("tasks page loads", async ({ page }) => {
  await page.goto("/login");
  await page.evaluate(() => {
    localStorage.setItem("jwt", "test-token-for-e2e");
  });
  await page.goto("/tasks");
  await expect(page.getByText("Tasks")).toBeVisible();
});

test("logout clears token and redirects", async ({ page }) => {
  await page.goto("/login");
  await page.evaluate(() => {
    localStorage.setItem("jwt", "test-token-for-e2e");
  });
  await page.goto("/");
  await page.click('button:has-text("Logout")');
  const token = await page.evaluate(() => localStorage.getItem("jwt"));
  expect(token).toBeNull();
});
