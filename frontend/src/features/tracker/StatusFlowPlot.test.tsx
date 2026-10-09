import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderApp, stubApi } from "../../test/render";
import { makeApplication, makeFlow } from "./fixtures";

afterEach(() => vi.unstubAllGlobals());

function stub(flow = makeFlow()) {
  return stubApi({
    "GET /api/tracker/applications": () => ({
      items: [makeApplication({ status: "interviewing" })],
      total: 1,
      page: 1,
      page_size: 25,
    }),
    "GET /api/tracker/status-flow": () => flow,
  });
}

describe("StatusFlowPlot", () => {
  it("draws one ribbon per path with labelled categories and a legend", async () => {
    stub();
    renderApp("/tracker");
    const plot = await screen.findByRole("group", { name: "Status flow of 7 applications" });
    const ribbons = within(plot).getAllByRole("img");
    expect(ribbons.map((r) => r.getAttribute("aria-label"))).toEqual([
      "Applied → Interviewing → Offer: 3 applications",
      "Applied (no response yet): 2 applications",
      "Applied → Interviewing (still interviewing): 1 application",
      "Applied → Rejected: 1 application",
    ]);
    expect(ribbons[0]).toHaveClass("flow-offer");
    expect(ribbons[1]).toHaveClass("flow-open");
    expect(ribbons[3]).toHaveClass("flow-rejected");
    for (const label of ["After applying", "Outcome", "No response yet", "Still interviewing"]) {
      expect(within(plot).getAllByText(label).length).toBeGreaterThan(0);
    }
    expect(screen.getByRole("list", { name: /Ribbon colour/ })).toHaveTextContent(
      "OfferRejectedStill open",
    );
  });

  it("shows the path and count on hover and on keyboard focus", async () => {
    stub();
    renderApp("/tracker");
    const plot = await screen.findByRole("group", { name: /Status flow/ });
    const [offer, , , rejected] = within(plot).getAllByRole("img");

    fireEvent.pointerMove(offer!, { clientX: 100, clientY: 50 });
    expect(screen.getByRole("status")).toHaveTextContent(
      "3 applicationsApplied → Interviewing → Offer",
    );
    expect(offer).toHaveClass("flow-ribbon-hover");

    fireEvent.focus(rejected!);
    expect(screen.getByRole("status")).toHaveTextContent("1 applicationApplied → Rejected");
  });

  it("offers the same numbers as a table", async () => {
    stub();
    renderApp("/tracker");
    await userEvent.click(await screen.findByRole("button", { name: "Show as table" }));
    const rows = within(screen.getAllByRole("table")[0]!).getAllByRole("row");
    expect(rows.slice(1).map((r) => r.textContent)).toEqual([
      "Applied → Interviewing → OfferOffer3",
      "Applied (no response yet)Still open2",
      "Applied → Interviewing (still interviewing)Still open1",
      "Applied → RejectedRejected1",
    ]);
  });

  it("isn't shown without applications", async () => {
    stub({ total: 0, paths: [] });
    renderApp("/tracker");
    await screen.findByRole("heading", { name: "Job Application Tracker" });
    await screen.findByRole("link", { name: "Backend Engineer" });
    expect(screen.queryByRole("heading", { name: /Status flow/ })).toBeNull();
  });
});

describe("status column and filter", () => {
  it("shows each status and filters by it", async () => {
    const calls = stub();
    renderApp("/tracker");
    const row = (await screen.findByRole("link", { name: "Backend Engineer" })).closest("tr")!;
    expect(within(row).getByText("Interviewing")).toBeVisible();

    await userEvent.selectOptions(screen.getByLabelText("Status"), "offer");
    await vi.waitFor(() =>
      expect(
        calls.some(
          (c) =>
            c.url.pathname === "/api/tracker/applications" &&
            c.url.searchParams.get("status") === "offer",
        ),
      ).toBe(true),
    );
  });
});
