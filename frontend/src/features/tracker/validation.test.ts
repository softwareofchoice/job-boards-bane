import { pdfFile, pngFile } from "./fixtures";
import { validateApplication, type ApplicationFormValues } from "./validation";

const LIMIT = 10 * 1024 * 1024;

const valid: ApplicationFormValues = {
  job_title: "Backend Engineer",
  company_name: "Acme",
  posting_url: "https://jobs.acme.test/1",
  resume: pdfFile(),
  screenshot: null,
};

describe("validateApplication", () => {
  it("accepts a valid form, with or without a screenshot", () => {
    expect(validateApplication(valid, LIMIT)).toEqual({});
    expect(validateApplication({ ...valid, screenshot: pngFile() }, LIMIT)).toEqual({});
  });

  it("requires the text fields and resume", () => {
    const errors = validateApplication(
      { job_title: "  ", company_name: "", posting_url: "", resume: null, screenshot: null },
      LIMIT,
    );
    expect(Object.keys(errors).sort()).toEqual([
      "company_name",
      "job_title",
      "posting_url",
      "resume",
    ]);
  });

  it.each(["jobs.acme.test", "ftp://acme.test", "javascript:alert(1)"])(
    "rejects the URL %s",
    (url) => {
      expect(validateApplication({ ...valid, posting_url: url }, LIMIT)).toHaveProperty(
        "posting_url",
      );
    },
  );

  it("limits lengths", () => {
    const errors = validateApplication({ ...valid, job_title: "x".repeat(201) }, LIMIT);
    expect(errors.job_title).toMatch(/200 characters/);
  });

  it("checks file types and sizes", () => {
    expect(validateApplication({ ...valid, resume: pdfFile("cv.txt") }, LIMIT).resume).toBe(
      "Upload a PDF or DOCX file.",
    );
    expect(validateApplication({ ...valid, resume: pdfFile("cv.pdf", 2000) }, 1000).resume).toMatch(
      /limit/,
    );
    expect(
      validateApplication({ ...valid, screenshot: pngFile("shot.gif") }, LIMIT).screenshot,
    ).toMatch(/PNG/);
  });
});
