import { readFile } from "node:fs/promises";

import { expect, test } from "@playwright/test";

const PDF = Buffer.from("%PDF-1.7\n1 0 obj << >> endobj\ntrailer << >>\n%%EOF\n");
const PNG = Buffer.concat([
  Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
  Buffer.alloc(64),
]);

test("log an application, find it in the list, open it and download the resume", async ({
  page,
}) => {
  // The E2E database is shared between runs, so make this run's entry easy to find.
  const title = `E2E Engineer ${Date.now()}`;

  await page.goto("/tracker/new");
  await page.getByLabel("Job posting title").fill(title);
  await page.getByLabel("Company name").fill("Playwright Inc");
  await page.getByLabel("Job posting URL").fill(`https://jobs.example.test/${Date.now()}`);
  await page.getByLabel("Resume used").setInputFiles({
    name: "e2e-resume.pdf",
    mimeType: "application/pdf",
    buffer: PDF,
  });
  await page.getByLabel("Screenshot of the posting").setInputFiles({
    name: "posting.png",
    mimeType: "image/png",
    buffer: PNG,
  });
  await page.getByRole("button", { name: "Save application" }).click();

  await expect(page.getByRole("status")).toContainText(`Saved “${title}” at Playwright Inc.`);
  await expect(page.getByLabel("Job posting title")).toHaveValue("");

  await page.getByRole("link", { name: "← All applications" }).click();
  const firstRow = page.getByRole("row").nth(1);
  await expect(firstRow.getByRole("link", { name: title })).toBeVisible();
  await expect(firstRow.getByText("Yes")).toBeVisible();

  await page.getByLabel("Search by title or company").fill(title);
  await expect(page.getByRole("row")).toHaveCount(2);
  await page.getByRole("link", { name: title }).click();

  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  await expect(page.getByAltText(`Screenshot of the ${title} posting`)).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download e2e-resume.pdf" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("e2e-resume.pdf");
  expect(await readFile(await download.path())).toEqual(PDF);

  // Clean up, which also exercises delete.
  await page.getByRole("button", { name: "Delete application" }).click();
  await page.getByRole("button", { name: "Yes, delete" }).click();
  await expect(page).toHaveURL("/tracker");
  await page.getByLabel("Search by title or company").fill(title);
  await expect(page.getByText(`No applications match “${title}”.`)).toBeVisible();
});
