import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderApp, stubApi } from "../../test/render";
import { makeApplication } from "./fixtures";

afterEach(() => vi.unstubAllGlobals());

const APPLIED_AT = "2026-10-01T14:03:00Z";
const INTERVIEW_AT = "2026-10-05T09:00:00Z";

const interviewing = makeApplication({
  status: "interviewing",
  allowed_next: ["offer", "rejected"],
  status_history: [
    { from_status: null, to_status: "applied", changed_at: APPLIED_AT },
    { from_status: "applied", to_status: "interviewing", changed_at: INTERVIEW_AT },
  ],
});

async function open() {
  renderApp("/tracker/a1");
  return screen.findByRole("region", { name: /Status/ });
}

describe("status panel", () => {
  it("moves to an allowed status and shows the history", async () => {
    let current = makeApplication();
    const calls = stubApi({
      "GET /api/tracker/applications/a1": () => current,
      "POST /api/tracker/applications/a1/status": () => (current = interviewing),
    });
    const panel = await open();
    expect(within(panel).getByText("Applied", { selector: ".status-badge" })).toBeVisible();
    expect(within(panel).queryByRole("button", { name: /Undo/ })).toBeNull();

    await userEvent.click(within(panel).getByRole("button", { name: "Got an interview" }));
    expect(await within(panel).findByRole("button", { name: "Got an offer" })).toBeVisible();
    expect(within(panel).getByRole("button", { name: "Rejected" })).toBeVisible();
    const post = calls.find((c) => c.method === "POST");
    expect(JSON.parse(String(post?.init?.body))).toEqual({ status: "interviewing" });
    const history = within(panel).getByRole("list", { name: "Status history" });
    expect(
      within(history)
        .getAllByRole("listitem")
        .map((li) => li.textContent),
    ).toEqual([expect.stringContaining("Applied"), expect.stringContaining("Interviewing")]);
  });

  it("undoes the latest change", async () => {
    let current = interviewing;
    stubApi({
      "GET /api/tracker/applications/a1": () => current,
      "DELETE /api/tracker/applications/a1/status/latest": () => (current = makeApplication()),
    });
    const panel = await open();
    await userEvent.click(within(panel).getByRole("button", { name: "Undo “Interviewing”" }));
    expect(await within(panel).findByRole("button", { name: "Got an interview" })).toBeVisible();
    await waitFor(() => expect(within(panel).queryByRole("button", { name: /Undo/ })).toBeNull());
  });

  it("says when a status is final", async () => {
    stubApi({
      "GET /api/tracker/applications/a1": () =>
        makeApplication({ status: "offer", allowed_next: [] }),
    });
    const panel = await open();
    expect(within(panel).getByText("This is a final status.")).toBeVisible();
  });

  it("shows a refused change", async () => {
    stubApi({
      "GET /api/tracker/applications/a1": () => makeApplication(),
      "POST /api/tracker/applications/a1/status": () =>
        jsonResponse(409, {
          error: {
            code: "invalid_status_change",
            message: "Can't change the status from Rejected to Interviewing. Rejected is final.",
            request_id: "r1",
            allowed: [],
          },
        }),
    });
    const panel = await open();
    await userEvent.click(within(panel).getByRole("button", { name: "Got an interview" }));
    expect(await within(panel).findByRole("alert")).toHaveTextContent("Rejected is final.");
  });
});
