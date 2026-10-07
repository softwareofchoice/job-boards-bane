import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderApp, stubApi } from "../../test/render";
import { makeApplication } from "./fixtures";

afterEach(() => vi.unstubAllGlobals());

const withScreenshot = makeApplication({
  id: "a1",
  screenshot: {
    id: "s1",
    url: "/api/files/s1",
    original_name: "shot.png",
    content_type: "image/png",
    size_bytes: 2048,
  },
});

describe("ApplicationDetailPage", () => {
  it("shows all fields, the screenshot and the resume download", async () => {
    stubApi({ "GET /api/tracker/applications/a1": () => withScreenshot });
    renderApp("/tracker/a1");

    expect(await screen.findByRole("heading", { name: "Backend Engineer" })).toBeVisible();
    expect(screen.getByText("Acme")).toBeVisible();
    expect(screen.getByRole("link", { name: "https://jobs.acme.test/123" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Download resume.pdf" })).toHaveAttribute(
      "href",
      "/api/files/a1-resume",
    );
    expect(screen.getByAltText("Screenshot of the Backend Engineer posting")).toHaveAttribute(
      "src",
      "/api/files/s1",
    );
  });

  it("asks for confirmation before deleting, then returns to the list", async () => {
    const calls = stubApi({
      "GET /api/tracker/applications/a1": () => withScreenshot,
      "DELETE /api/tracker/applications/a1": () => new Response(null, { status: 204 }),
      "GET /api/tracker/applications": () => ({ items: [], total: 0, page: 1, page_size: 25 }),
    });
    renderApp("/tracker/a1");
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Delete application" }));
    expect(screen.getByRole("alertdialog")).toHaveTextContent("can't be undone");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);

    await user.click(screen.getByRole("button", { name: "Delete application" }));
    await user.click(screen.getByRole("button", { name: "Yes, delete" }));

    expect(await screen.findByRole("heading", { name: "Job Application Tracker" })).toBeVisible();
    expect(calls.filter((c) => c.method === "DELETE")).toHaveLength(1);
  });

  it("says when the application doesn't exist", async () => {
    stubApi({
      "GET /api/tracker/applications/gone": () =>
        jsonResponse(404, {
          error: { code: "not_found", message: "Application not found.", request_id: "r" },
        }),
    });
    renderApp("/tracker/gone");
    expect(await screen.findByRole("heading", { name: "Application not found" })).toBeVisible();
  });
});
