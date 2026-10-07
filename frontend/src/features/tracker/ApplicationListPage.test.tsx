import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderApp, stubApi } from "../../test/render";
import type { ApplicationPage } from "./api";
import { makeApplication } from "./fixtures";

const LIST = "GET /api/tracker/applications";

function page(items: ApplicationPage["items"], total = items.length, pageNo = 1): ApplicationPage {
  return { items, total, page: pageNo, page_size: 25 };
}

afterEach(() => vi.unstubAllGlobals());

describe("ApplicationListPage", () => {
  it("lists applications with their details", async () => {
    stubApi({
      [LIST]: () =>
        page([
          makeApplication({ id: "a1", job_title: "Backend Engineer", company_name: "Acme" }),
          makeApplication({
            id: "a2",
            job_title: "Data Engineer",
            company_name: "Initech",
            screenshot: {
              id: "s",
              url: "/api/files/s",
              original_name: "s.png",
              content_type: "image/png",
              size_bytes: 1,
            },
          }),
        ]),
    });
    renderApp("/tracker");

    const rows = await screen.findAllByRole("row");
    expect(rows).toHaveLength(3); // header + 2
    const first = within(rows[1]!);
    expect(first.getByRole("link", { name: "Backend Engineer" })).toHaveAttribute(
      "href",
      "/tracker/a1",
    );
    expect(first.getByText("Acme")).toBeVisible();
    expect(first.getByRole("link", { name: "Open posting" })).toHaveAttribute(
      "href",
      "https://jobs.acme.test/123",
    );
    expect(first.getByText("—")).toBeVisible();
    expect(within(rows[2]!).getByText("Yes")).toBeVisible();
  });

  it("searches after typing stops", async () => {
    const calls = stubApi({ [LIST]: () => page([makeApplication()]) });
    renderApp("/tracker");
    await screen.findAllByRole("row");

    await userEvent.type(screen.getByLabelText("Search by title or company"), "acme");

    await waitFor(() =>
      expect(calls.some((c) => c.url.searchParams.get("q") === "acme")).toBe(true),
    );
    const listCalls = calls.filter((c) => c.url.pathname === "/api/tracker/applications");
    expect(listCalls.map((c) => c.url.searchParams.get("q"))).toEqual([null, "acme"]);
  });

  it("pages through results", async () => {
    const calls = stubApi({
      [LIST]: (url) => {
        const n = Number(url.searchParams.get("page"));
        return page([makeApplication({ id: `p${n}`, job_title: `Job on page ${n}` })], 30, n);
      },
    });
    renderApp("/tracker");
    expect(await screen.findByText("Job on page 1")).toBeVisible();
    expect(screen.getByText(/Page 1 of 2/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(await screen.findByText("Job on page 2")).toBeVisible();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    expect(calls.at(-1)?.url.searchParams.get("page")).toBe("2");
  });

  it("explains an empty list", async () => {
    stubApi({ [LIST]: () => page([]) });
    renderApp("/tracker");
    expect(await screen.findByText(/No applications yet/)).toBeVisible();
    expect(screen.getByRole("link", { name: "Log your first one." })).toHaveAttribute(
      "href",
      "/tracker/new",
    );
  });
});
