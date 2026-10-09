import { screen, within } from "@testing-library/react";

import { renderApp, stubApi } from "../../test/render";
import { makeGeneration, makeReport } from "./fixtures";

afterEach(() => vi.unstubAllGlobals());

describe("GenerationPage", () => {
  it("shows the current step while running, then the report", async () => {
    let calls = 0;
    stubApi({
      "GET /api/rounder/generations/g1": () => {
        calls += 1;
        return calls === 1
          ? makeGeneration({
              status: "running",
              progress: { step: "rewriting", done: 1, total: 3 },
              report: null,
              docx: null,
              pdf: null,
            })
          : makeGeneration();
      },
    });
    renderApp("/resume-rounder/generations/g1");
    expect(await screen.findByText("Rewriting (1 of 3 jobs)…")).toBeVisible();
    const steps = screen.getByRole("list", { name: "Steps" });
    expect(within(steps).getByText("Rewriting")).toHaveAttribute("aria-current", "step");
    expect(within(steps).getByText("Finding skills")).toHaveClass("step-done");

    expect(
      await screen.findByRole("link", { name: "Download .docx" }, { timeout: 4000 }),
    ).toHaveAttribute("href", "/api/rounder/generations/g1/resume.docx");
    expect(screen.getByRole("link", { name: "Download PDF" })).toHaveAttribute(
      "href",
      "/api/rounder/generations/g1/resume.pdf",
    );
  });

  it("shows coverage, unmatched roles, before and after, and pages", async () => {
    stubApi({ "GET /api/rounder/generations/g1": () => makeGeneration() });
    renderApp("/resume-rounder/generations/g1");
    expect(await screen.findByLabelText("Covered skills")).toHaveTextContent(
      "PostgreSQL (Postgres)",
    );
    expect(screen.getByLabelText("Skills not covered")).toHaveTextContent("Kubernetes (required)");
    expect(screen.getByText(/didn't match a job in your resume/)).toHaveTextContent("Freelance");
    expect(screen.getByText("0.9 pages (target 1, your resume was 0.8)")).toBeVisible();

    const acme = screen.getByRole("region", { name: /Software Engineer, Acme/ });
    expect(within(acme).getByText("Skills used: Postgres")).toBeVisible();
    expect(within(acme).getByRole("heading", { name: "Before" })).toBeVisible();
    expect(within(acme).getByText("Designed the Postgres schema.")).toBeVisible();
    const globex = screen.getByRole("region", { name: /Developer, Globex/ });
    expect(within(globex).getByText(/No saved skills matched this role/)).toBeVisible();
    expect(within(globex).queryByRole("heading", { name: "Before" })).toBeNull();
  });

  it("shows the overflow warning", async () => {
    const report = makeReport({
      pages: { target: 1, template: 1.6, final: 1.2, attempts: 3, overflow: 0.2 },
      warnings: [
        "Couldn't fit the resume in 1 pages after 3 attempts: the closest is 0.2 pages over.",
      ],
    });
    stubApi({ "GET /api/rounder/generations/g1": () => makeGeneration({ report }) });
    renderApp("/resume-rounder/generations/g1");
    expect(await screen.findByText(/closest is 0.2 pages over/)).toBeVisible();
  });

  it("shows a failure", async () => {
    stubApi({
      "GET /api/rounder/generations/g1": () =>
        makeGeneration({
          status: "failed",
          error: "Can't reach the local LLM server.",
          report: null,
          docx: null,
          pdf: null,
        }),
    });
    renderApp("/resume-rounder/generations/g1");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Generating the resume failed: Can't reach the local LLM server.",
    );
    expect(screen.queryByRole("link", { name: "Download .docx" })).toBeNull();
  });

  it("says when the resume doesn't exist", async () => {
    stubApi({});
    renderApp("/resume-rounder/generations/nope");
    expect(await screen.findByRole("heading", { name: "Resume not found" })).toBeVisible();
  });
});
