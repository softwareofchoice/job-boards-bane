import { readFile } from "node:fs/promises";

import { expect, test } from "@playwright/test";
import { load } from "js-yaml";

// The E2E backend runs with JOB_SOURCE=fake and LLM_FAKE=true (see playwright.config.ts),
// so this exercises the whole flow without Google or Ollama.

test("search, watch it run, review the results, export CSV and YAML, re-import", async ({
  page,
}) => {
  const title = `E2E Engineer ${Date.now()}`;
  await page.goto("/scraper");

  await page.getByLabel("Job title").fill(title);
  await page.getByLabel("Location").fill("Austin, TX");
  await page.getByLabel("Job level").selectOption("senior");
  await page.getByLabel("Years of experience").fill("5");
  const skills = page.getByRole("textbox", { name: /Relevant skills/ });
  await skills.fill("Python");
  await skills.press("Enter");
  await skills.fill("PostgreSQL");
  await skills.press("Enter");
  await page.getByLabel("Number of jobs pulled").fill("8");
  await page.getByLabel("Number of jobs selected").fill("3");

  // Export the options before running, to re-import later.
  const yamlDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export YAML" }).click();
  const yamlFile = await (await yamlDownload).path();
  const exported = load(await readFile(yamlFile, "utf8")) as {
    search: { job_title: string; skills: string[] };
  };
  expect(exported.search.job_title).toBe(title);
  expect(exported.search.skills).toEqual(["Python", "PostgreSQL"]);

  await page.getByRole("button", { name: "Run search" }).click();
  await expect(page).toHaveURL(/\/scraper\/runs\/[0-9a-f-]+$/);
  await expect(page.getByRole("heading", { level: 2, name: "Top 3 of 8" })).toBeVisible({
    timeout: 20_000,
  });

  const postings = page.locator("ol.postings > li");
  await expect(postings).toHaveCount(3);
  const scores = await postings.locator(".score").allInnerTexts();
  const numbers = scores.map(Number);
  expect(numbers).toEqual([...numbers].sort((a, b) => b - a));

  await postings.first().locator("summary").click();
  await expect(postings.first().getByText(/We're hiring a/)).toBeVisible();

  await page.getByLabel("Show all 8").check();
  await expect(page.getByRole("heading", { level: 2, name: "All 8 postings" })).toBeVisible();
  await expect(postings).toHaveCount(8);

  const csvDownload = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download CSV" }).click();
  const csv = (await readFile(await (await csvDownload).path(), "utf8")).replace(/^\uFEFF/, "");
  const lines = csv.trim().split(/\r?\n/);
  expect(lines[0]).toMatch(/^rank,score,title,company,location,posted_date,url/);
  expect(lines).toHaveLength(9);

  // The run is listed under past searches.
  await page.getByRole("link", { name: "← New search" }).click();
  await expect(page.getByRole("link", { name: title })).toBeVisible();

  // Importing the exported file fills the form back in.
  await page.reload();
  await page.getByTestId("yaml-input").setInputFiles(yamlFile);
  await expect(page.getByRole("status")).toContainText("Loaded");
  await expect(page.getByLabel("Job title")).toHaveValue(title);
  await expect(page.getByLabel("Number of jobs selected")).toHaveValue("3");

  // Clean up.
  await page.getByRole("button", { name: `Delete search for ${title}` }).click();
  await expect(page.getByRole("link", { name: title })).toHaveCount(0);
});
