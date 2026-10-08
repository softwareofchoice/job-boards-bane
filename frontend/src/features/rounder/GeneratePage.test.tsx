import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderApp, stubApi, type RecordedCall } from "../../test/render";
import { makeGeneration, makePreflight, makeSkill } from "./fixtures";
import { validateGenerate, type FormValues } from "./validation";

afterEach(() => vi.unstubAllGlobals());

const POSTING = "We need a backend engineer with Python and PostgreSQL. ".repeat(5);
const DOCX = new File(["PK fake"], "resume.docx", {
  type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
});

const VALID: FormValues = {
  template: DOCX,
  mode: "text",
  posting_url: "",
  posting_text: POSTING,
  job_title: "Backend Engineer",
  company_name: "Initech",
};

function sent(call: RecordedCall | undefined): FormData {
  return call?.init?.body as FormData;
}

async function fillForm() {
  await userEvent.upload(screen.getByLabelText(/^Your resume/), DOCX);
  await userEvent.click(screen.getByLabelText(/^Job description/));
  await userEvent.paste(POSTING);
  await userEvent.type(screen.getByLabelText(/^Job title/), "Backend Engineer");
  await userEvent.type(screen.getByLabelText(/^Company name/), "Initech");
}

describe("validateGenerate", () => {
  it("accepts a complete form", () => {
    expect(validateGenerate(VALID)).toEqual({});
  });

  it("asks for a posting URL or text", () => {
    expect(validateGenerate({ ...VALID, posting_text: "" }).posting).toBe(
      "Provide a job posting URL or paste the description",
    );
    expect(validateGenerate({ ...VALID, mode: "url" }).posting).toBe(
      "Provide a job posting URL or paste the description",
    );
  });

  it("checks the file type, text length and URL", () => {
    const pdf = new File(["%PDF"], "cv.pdf");
    expect(validateGenerate({ ...VALID, template: pdf }).template).toBe(
      "Upload a Word (.docx) file.",
    );
    expect(validateGenerate({ ...VALID, posting_text: "short" }).posting_text).toMatch(
      /at least 200 characters/,
    );
    expect(
      validateGenerate({ ...VALID, mode: "url", posting_url: "jobs.example.com" }).posting_url,
    ).toMatch(/http/);
  });
});

describe("GeneratePage", () => {
  it("checks the resume, defaults the target length, then starts and opens the result", async () => {
    const calls = stubApi({
      "GET /api/rounder/skills": () => [makeSkill()],
      "GET /api/rounder/generations": () => [],
      "POST /api/rounder/generations/preflight": () => makePreflight({ suggested_target: "1.5" }),
      "POST /api/rounder/generations": () =>
        jsonResponse(202, { generation_id: "g1", job_id: "j1" }),
      "GET /api/rounder/generations/g1": () => makeGeneration(),
    });
    renderApp("/resume-rounder");
    await screen.findByRole("link", { name: "Your skills (1)" });
    await fillForm();
    await userEvent.click(screen.getByRole("button", { name: "Check resume" }));

    expect(await screen.findByText(/Found 2 roles in your experience section/)).toBeVisible();
    expect(screen.getByLabelText(/^Target length/)).toHaveValue("1.5");
    const checked = sent(calls.find((c) => c.url.pathname.endsWith("/preflight")));
    expect(checked.get("posting_text")).toBe(POSTING.trim());
    expect(checked.get("posting_url")).toBe("");

    await userEvent.selectOptions(screen.getByLabelText(/^Target length/), "2");
    await userEvent.click(screen.getByRole("button", { name: "Generate resume" }));
    expect(
      await screen.findByRole("heading", { level: 1, name: /Backend Engineer/ }),
    ).toBeVisible();
    const started = sent(
      calls.find((c) => c.method === "POST" && c.url.pathname === "/api/rounder/generations"),
    );
    expect(started.get("target_pages")).toBe("2");
    expect(started.get("job_title")).toBe("Backend Engineer");
    expect((started.get("template") as File).name).toBe("resume.docx");
  });

  it("lets the user choose the experience heading when it isn't found", async () => {
    const calls = stubApi({
      "GET /api/rounder/skills": () => [makeSkill()],
      "GET /api/rounder/generations": () => [],
      "POST /api/rounder/generations/preflight": (_url, init) => {
        const chosen = (init?.body as FormData).get("experience_heading_idx");
        return chosen === null
          ? makePreflight({ experience_found: false, experience_entries: [] })
          : makePreflight();
      },
    });
    renderApp("/resume-rounder");
    await screen.findByRole("link", { name: "Your skills (1)" });
    await fillForm();
    await userEvent.click(screen.getByRole("button", { name: "Check resume" }));

    expect(await screen.findByText(/Couldn't find the experience section/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Check resume" })).toBeDisabled();
    await userEvent.selectOptions(screen.getByLabelText(/^Experience section heading/), "2");
    await userEvent.click(screen.getByRole("button", { name: "Check resume" }));

    expect(await screen.findByRole("button", { name: "Generate resume" })).toBeEnabled();
    const second = sent(calls.filter((c) => c.url.pathname.endsWith("/preflight"))[1]);
    expect(second.get("experience_heading_idx")).toBe("2");
  });

  it("shows server field errors, such as a posting URL that can't be read", async () => {
    stubApi({
      "GET /api/rounder/skills": () => [makeSkill()],
      "GET /api/rounder/generations": () => [],
      "POST /api/rounder/generations/preflight": () =>
        jsonResponse(422, {
          detail: [
            {
              loc: ["body", "posting_url"],
              msg: "Couldn't read the job posting from this address. Paste the description instead.",
            },
          ],
        }),
    });
    renderApp("/resume-rounder");
    await screen.findByRole("link", { name: "Your skills (1)" });
    await userEvent.upload(screen.getByLabelText(/^Your resume/), DOCX);
    await userEvent.click(screen.getByLabelText("Use its web address"));
    await userEvent.type(screen.getByLabelText(/^Job posting URL/), "https://jobs.example.test/1");
    await userEvent.type(screen.getByLabelText(/^Job title/), "Backend Engineer");
    await userEvent.type(screen.getByLabelText(/^Company name/), "Initech");
    await userEvent.click(screen.getByRole("button", { name: "Check resume" }));
    expect(await screen.findByText(/Paste the description instead/)).toBeVisible();
  });

  it("disables generation and links to the skills page when no skills are saved", async () => {
    stubApi({
      "GET /api/rounder/skills": () => [],
      "GET /api/rounder/generations": () => [],
    });
    renderApp("/resume-rounder");
    expect(await screen.findByText(/Add your skills before generating/)).toBeVisible();
    expect(screen.getByRole("link", { name: "Add skills" })).toHaveAttribute(
      "href",
      "/resume-rounder/skills",
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Check resume" })).toBeDisabled(),
    );
  });

  it("lists past resumes", async () => {
    stubApi({
      "GET /api/rounder/skills": () => [makeSkill()],
      "GET /api/rounder/generations": () => [makeGeneration()],
    });
    renderApp("/resume-rounder");
    expect(await screen.findByRole("link", { name: "Backend Engineer" })).toHaveAttribute(
      "href",
      "/resume-rounder/generations/g1",
    );
    expect(screen.getByText("1 of 1")).toBeVisible();
  });
});
