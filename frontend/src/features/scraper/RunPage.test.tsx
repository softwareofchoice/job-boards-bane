import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderApp, stubApi } from "../../test/render";
import { makePosting, makeRun } from "./fixtures";

afterEach(() => vi.unstubAllGlobals());

async function openRun() {
  renderApp("/scraper/runs/r1");
  await screen.findByRole("heading", { level: 1, name: /Python Developer/ });
}

describe("RunPage", () => {
  it("shows progress while running, then the results", async () => {
    let calls = 0;
    stubApi({
      "GET /api/scraper/runs/r1": () => {
        calls += 1;
        return calls === 1
          ? makeRun({
              status: "running",
              progress: { step: "scoring", done: 4, total: 10 },
              postings: [],
            })
          : makeRun();
      },
    });
    await openRun();
    expect(screen.getByRole("status")).toHaveTextContent("Scoring 4 of 10");

    expect(
      await screen.findByRole("heading", { level: 2, name: "Top 1 of 10" }, { timeout: 4000 }),
    ).toBeVisible();
    const item = screen.getByRole("listitem");
    expect(within(item).getByText("82")).toBeVisible();
    expect(within(item).getByRole("link", { name: "Python Developer" })).toHaveAttribute(
      "href",
      "https://jobs.example.test/1",
    );
    expect(within(item).getByText("Strong match.")).toBeVisible();
    expect(within(item).getByLabelText("Matched skills")).toHaveTextContent("PythonPostgreSQL");
    expect(screen.getByRole("link", { name: "Download CSV" })).toHaveAttribute(
      "href",
      "/api/scraper/runs/r1/export.csv",
    );
  });

  it("expands a posting to show sub-scores and the description", async () => {
    stubApi({ "GET /api/scraper/runs/r1": () => makeRun() });
    await openRun();
    await userEvent.click(screen.getByText("Strong match."));
    expect(screen.getByText("Python and PostgreSQL.")).toBeVisible();
    expect(screen.getByText("Title").nextSibling).toHaveTextContent("9/10");
  });

  it("shows all postings when asked", async () => {
    const calls = stubApi({
      "GET /api/scraper/runs/r1": (url) =>
        url.searchParams.get("all") === "true"
          ? makeRun({
              postings: [
                makePosting(),
                makePosting({
                  id: "p2",
                  title: "Not scored",
                  score: null,
                  rank: null,
                  selected: false,
                  score_error: "bad reply",
                  sub_scores: null,
                }),
              ],
            })
          : makeRun(),
    });
    await openRun();
    await userEvent.click(screen.getByLabelText("Show all 10"));

    expect(await screen.findByRole("heading", { level: 2, name: "All 10 postings" })).toBeVisible();
    expect(screen.getByText("Not scored: bad reply")).toBeVisible();
    expect(calls.at(-1)?.url.searchParams.get("all")).toBe("true");
    expect(screen.getByRole("link", { name: "Download CSV" })).toHaveAttribute(
      "href",
      "/api/scraper/runs/r1/export.csv?all=true",
    );
  });

  it("warns when Google blocked the search and fewer postings were found", async () => {
    stubApi({
      "GET /api/scraper/runs/r1": () => makeRun({ stopped_reason: "blocked", pulled_count: 4 }),
    });
    await openRun();
    expect(screen.getByRole("alert")).toHaveTextContent("Google blocked the search");
    expect(screen.getByRole("status")).toHaveTextContent("Found 4 of the 10 postings asked for.");
  });

  it("shows why a search failed", async () => {
    stubApi({
      "GET /api/scraper/runs/r1": () =>
        makeRun({
          status: "failed",
          error: "Set SERPAPI_KEY to use the SerpAPI job source.",
          postings: [],
        }),
    });
    await openRun();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Set SERPAPI_KEY"));
    expect(screen.queryByRole("link", { name: "Download CSV" })).toBeNull();
  });
});
