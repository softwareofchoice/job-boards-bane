import { screen } from "@testing-library/react";

import { HEALTHY, renderApp, stubHealth } from "../test/render";

afterEach(() => vi.unstubAllGlobals());

describe("health badge and LLM warning", () => {
  it("shows ok when everything is up, and no LLM warning", async () => {
    stubHealth();
    renderApp("/scraper");
    expect(await screen.findByText("All systems ok")).toBeVisible();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("warns on LLM pages when the LLM is down", async () => {
    stubHealth({ ...HEALTHY, llm: "error", llm_message: "Run `ollama pull llama3.1:8b`." });
    renderApp("/resume-rounder");
    expect(await screen.findByText("LLM unavailable")).toBeVisible();
    expect(await screen.findByRole("alert")).toHaveTextContent("ollama pull llama3.1:8b");
  });

  it("doesn't show the LLM warning on the tracker", async () => {
    stubHealth({ ...HEALTHY, llm: "error", llm_message: "down" });
    renderApp("/tracker");
    expect(await screen.findByText("LLM unavailable")).toBeVisible();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("names both problems when the database is down too", async () => {
    stubHealth({ ...HEALTHY, db: "error", llm: "error" });
    renderApp("/");
    expect(await screen.findByText("database & LLM unavailable")).toBeVisible();
  });

  it("says when the backend is offline", async () => {
    stubHealth("offline");
    renderApp("/");
    expect(await screen.findByText("Backend offline")).toBeVisible();
  });
});
