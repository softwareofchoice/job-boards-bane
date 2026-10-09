import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { expect, test, type APIRequestContext } from "@playwright/test";

const NORTHWIND = "Senior Software Engineer at Northwind Analytics";
const FABRIKAM = "Software Engineer at Fabrikam Logistics";
const SKILLS = [
  ["PostgreSQL", NORTHWIND, "Designed the reporting schema and tuned slow dashboard queries."],
  ["FastAPI", NORTHWIND, "Built internal FastAPI services for report exports."],
  ["Kubernetes", FABRIKAM, "Moved the tracking service onto Kubernetes with Helm."],
] as const;

const POSTING =
  "Initech is hiring a Backend Engineer to build the services behind our billing platform. " +
  "Required: Python, PostgreSQL and Kubernetes, plus experience designing REST APIs. " +
  "Preferred: FastAPI and Terraform. You'll work with product and support teams to ship " +
  "reliable features every week and mentor other engineers.";

/** A sample resume built by the backend's own builder (see app/rounder/sample_resumes.py). */
function sampleResume(): Buffer {
  const dir = mkdtempSync(join(tmpdir(), "bane-e2e-"));
  execFileSync("uv", ["run", "python", "-m", "app.rounder.sample_resumes", dir], {
    cwd: "../backend",
  });
  return readFileSync(join(dir, "styled-1-page.docx"));
}

/** The E2E database is shared between runs: remove this test's skills if a run left them. */
async function removeSkills(request: APIRequestContext) {
  const response = await request.get("/api/rounder/skills");
  const saved = (await response.json()) as { id: string; skill_name: string; role: string }[];
  for (const skill of saved) {
    if (SKILLS.some(([name, role]) => name === skill.skill_name && role === skill.role)) {
      await request.delete(`/api/rounder/skills/${skill.id}`);
    }
  }
}

test("add skills, tailor a resume and download it", async ({ page, request }) => {
  test.slow(); // LibreOffice renders the resume a few times.
  await removeSkills(request);
  const resume = sampleResume();

  await page.goto("/resume-rounder/skills");
  for (const [name, role, summary] of SKILLS) {
    await page.getByLabel("Skill name").fill(name);
    await page.getByLabel("Role").fill(role);
    await page.getByLabel("Skill summary").fill(summary);
    await page.getByRole("button", { name: "Add skill" }).click();
    await expect(page.getByRole("status")).toContainText(`Saved “${name}” for ${role}.`);
  }
  await expect(page.getByRole("region", { name: NORTHWIND }).getByRole("listitem")).toHaveCount(2);

  await page.getByRole("link", { name: "← Tailor a resume" }).click();
  await page.getByLabel("Your resume").setInputFiles({
    name: "alex-rivera.docx",
    mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    buffer: resume,
  });
  await page.getByLabel("Job description").fill(POSTING);
  await page.getByLabel("Job title").fill("Backend Engineer");
  await page.getByLabel("Company name").fill("Initech");
  await page.getByRole("button", { name: "Check resume" }).click();

  await expect(page.getByText("Found 3 roles in your experience section.")).toBeVisible();
  await expect(page.getByLabel("Target length")).toHaveValue("1");
  await page.getByRole("button", { name: "Generate resume" }).click();

  await expect(page).toHaveURL(/\/resume-rounder\/generations\//);
  const download = page.getByRole("link", { name: "Download .docx" });
  await expect(download).toBeVisible({ timeout: 60_000 });
  await expect(page.getByLabel("Covered skills")).toContainText("PostgreSQL");
  await expect(page.getByLabel("Covered skills")).toContainText("Kubernetes");
  const northwind = page.getByRole("region", { name: /Senior Software Engineer, Northwind/ });
  await expect(northwind.getByText(/Skills used: .*PostgreSQL/)).toBeVisible();
  await expect(
    northwind.getByText("Designed the reporting schema", { exact: false }).last(),
  ).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await download.click();
  const file = await downloadPromise;
  expect(file.suggestedFilename()).toBe("Initech-Backend-Engineer-resume.docx");
  expect(
    readFileSync(await file.path())
      .subarray(0, 2)
      .toString(),
  ).toBe("PK");

  // It's listed with past resumes.
  await page.getByRole("link", { name: "← Tailor another resume" }).click();
  await expect(
    page
      .getByRole("region", { name: "Past resumes" })
      .getByRole("link", { name: "Backend Engineer" })
      .first(),
  ).toBeVisible();

  await removeSkills(request);
});
