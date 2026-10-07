import { expect, test } from "@playwright/test";

test("home page loads and every nav link renders its page", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Job Board's Bane" })).toBeVisible();

  // The badge comes from the real /api/health, so this also checks the dev proxy to the backend.
  await expect(page.getByText(/All systems ok|unavailable/)).toBeVisible();
  await expect(page.getByText("Backend offline")).toHaveCount(0);

  const nav = page.getByRole("navigation", { name: "Main" });
  const pages = [
    ["Tracker", "/tracker", "Job Application Tracker"],
    ["Job Scraper", "/scraper", "Web Job Scraper"],
    ["Resume Rounder", "/resume-rounder", "Resume Rounder"],
  ] as const;
  for (const [link, path, heading] of pages) {
    await nav.getByRole("link", { name: link }).click();
    await expect(page).toHaveURL(path);
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
  }
});
