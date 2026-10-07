import type { Application } from "./api";

export function makeApplication(overrides: Partial<Application> = {}): Application {
  const id = overrides.id ?? "a1";
  return {
    id,
    job_title: "Backend Engineer",
    company_name: "Acme",
    posting_url: "https://jobs.acme.test/123",
    screenshot: null,
    resume: {
      id: `${id}-resume`,
      url: `/api/files/${id}-resume`,
      original_name: "resume.pdf",
      content_type: "application/pdf",
      size_bytes: 20480,
    },
    created_at: "2026-10-01T14:03:00Z",
    ...overrides,
  };
}

export function pdfFile(name = "resume.pdf", size = 1000): File {
  return new File([new Uint8Array(size)], name, { type: "application/pdf" });
}

export function pngFile(name = "posting.png"): File {
  return new File([new Uint8Array(100)], name, { type: "image/png" });
}
