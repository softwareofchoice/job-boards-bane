import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderApp, stubApi } from "../../test/render";
import { makeApplication, pdfFile, pngFile } from "./fixtures";

const CREATE = "POST /api/tracker/applications";
const CHECK = "GET /api/tracker/applications/check-url";

beforeEach(() => {
  // jsdom has no object URLs; the preview only needs a string.
  URL.createObjectURL = vi.fn(() => "blob:preview");
  URL.revokeObjectURL = vi.fn();
});
afterEach(() => vi.unstubAllGlobals());

/** Render the form page and wait for its lazily loaded bundle. */
async function openForm() {
  renderApp("/tracker/new");
  await screen.findByRole("heading", { name: "Log an application" });
}

async function fillValidForm(user = userEvent.setup()) {
  await user.type(screen.getByLabelText(/Job posting title/), "Backend Engineer");
  await user.type(screen.getByLabelText(/Company name/), "Acme");
  await user.type(screen.getByLabelText(/Job posting URL/), "https://jobs.acme.test/123");
  await user.upload(screen.getByLabelText(/Resume used/), pdfFile());
  return user;
}

describe("NewApplicationPage", () => {
  it("shows client-side errors next to each field without calling the API", async () => {
    const calls = stubApi({});
    await openForm();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/Job posting URL/), "not a url");
    await user.click(screen.getByRole("button", { name: "Save application" }));

    expect(screen.getByLabelText(/Job posting title/)).toHaveAccessibleDescription(
      "Enter the job title.",
    );
    expect(screen.getByLabelText(/Company name/)).toHaveAccessibleDescription(
      "Enter the company name.",
    );
    expect(screen.getByLabelText(/Job posting URL/)).toHaveAccessibleDescription(
      /http:\/\/ or https:\/\//,
    );
    expect(screen.getByLabelText(/Resume used/)).toHaveAccessibleDescription("Choose a file.");
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(0);
  });

  it("keeps what was entered and shows server errors after a 422", async () => {
    stubApi({
      [CHECK]: () => ({ duplicate: false, previous_created_at: null }),
      [CREATE]: () =>
        jsonResponse(422, {
          detail: [
            { loc: ["body", "resume"], msg: "Upload a PDF or DOCX file.", type: "value_error" },
          ],
        }),
    });
    await openForm();
    const user = await fillValidForm();

    await user.click(screen.getByRole("button", { name: "Save application" }));

    expect(await screen.findByText("Upload a PDF or DOCX file.")).toBeVisible();
    expect(screen.getByLabelText(/Job posting title/)).toHaveValue("Backend Engineer");
    expect(screen.getByLabelText(/Company name/)).toHaveValue("Acme");
  });

  it("sends the form as multipart and resets it after saving", async () => {
    const calls = stubApi({
      [CHECK]: () => ({ duplicate: false, previous_created_at: null }),
      [CREATE]: () => jsonResponse(201, makeApplication({ id: "new1" })),
    });
    await openForm();
    const user = await fillValidForm();
    await user.upload(screen.getByLabelText(/Screenshot of the posting/), pngFile());
    expect(screen.getByAltText("Screenshot preview")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Save application" }));

    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent("Saved “Backend Engineer” at Acme.");
    expect(screen.getByRole("link", { name: "View it" })).toHaveAttribute("href", "/tracker/new1");

    const post = calls.find((c) => c.method === "POST");
    const body = post?.init?.body as FormData;
    expect(body.get("job_title")).toBe("Backend Engineer");
    expect(body.get("posting_url")).toBe("https://jobs.acme.test/123");
    expect((body.get("resume") as File).name).toBe("resume.pdf");
    expect((body.get("screenshot") as File).name).toBe("posting.png");

    expect(screen.getByLabelText(/Job posting title/)).toHaveValue("");
    expect(screen.getByLabelText(/Company name/)).toHaveValue("");
    expect((screen.getByLabelText(/Resume used/) as HTMLInputElement).files).toHaveLength(0);
    expect(screen.queryByAltText("Screenshot preview")).toBeNull();
  });

  it("warns when the URL was logged before, but still allows saving", async () => {
    const calls = stubApi({
      [CHECK]: () => ({ duplicate: true, previous_created_at: "2026-09-15T10:00:00Z" }),
      [CREATE]: () => jsonResponse(201, makeApplication()),
    });
    await openForm();
    const user = await fillValidForm();

    await waitFor(() =>
      expect(screen.getByText(/You already logged this posting on/)).toBeVisible(),
    );
    const check = calls.find((c) => c.url.pathname.endsWith("check-url"));
    expect(check?.url.searchParams.get("url")).toBe("https://jobs.acme.test/123");

    await user.click(screen.getByRole("button", { name: "Save application" }));
    expect(await screen.findByText(/Saved “Backend Engineer”/)).toBeVisible();
  });

  it("shows unexpected server errors with the reference ID", async () => {
    stubApi({
      [CHECK]: () => ({ duplicate: false, previous_created_at: null }),
      [CREATE]: () =>
        jsonResponse(500, {
          error: { code: "internal_error", message: "Something went wrong.", request_id: "req42" },
        }),
    });
    await openForm();
    const user = await fillValidForm();
    await user.click(screen.getByRole("button", { name: "Save application" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("reference: req42");
  });
});
