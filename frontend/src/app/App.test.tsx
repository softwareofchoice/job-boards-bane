import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderApp, stubHealth } from "../test/render";

afterEach(() => vi.unstubAllGlobals());

describe("app shell", () => {
  beforeEach(() => stubHealth());

  it("home page describes and links to every sub-app", async () => {
    renderApp("/");
    expect(screen.getByRole("heading", { level: 1, name: "Job Board's Bane" })).toBeVisible();
    const main = screen.getByRole("main");
    for (const name of ["Job Application Tracker", "Web Job Scraper", "Resume Rounder"]) {
      expect(within(main).getByRole("link", { name })).toBeVisible();
    }
  });

  it.each([
    ["Tracker", "Job Application Tracker", "/tracker"],
    ["Job Scraper", "Web Job Scraper", "/scraper"],
    ["Resume Rounder", "Resume Rounder", "/resume-rounder"],
  ])("nav link %s opens its page", async (link, heading) => {
    renderApp("/");
    const nav = screen.getByRole("navigation", { name: "Main" });
    await userEvent.click(within(nav).getByRole("link", { name: link }));
    expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeVisible();
  });

  it.each(["/tracker", "/scraper", "/resume-rounder"])(
    "%s can be opened directly",
    async (path) => {
      renderApp(path);
      expect(await screen.findByRole("heading", { level: 1 })).toBeVisible();
    },
  );

  it("shows a not-found page for unknown paths", () => {
    renderApp("/nope");
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeVisible();
  });
});
