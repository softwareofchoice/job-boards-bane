import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderApp, stubApi } from "../../test/render";
import { OPTIONS, makeRun } from "./fixtures";
import { toYaml } from "./options";

const RUNS = "GET /api/scraper/runs";
const START = "POST /api/scraper/runs";

afterEach(() => vi.unstubAllGlobals());

async function openPage() {
  renderApp("/scraper");
  await screen.findByRole("heading", { level: 1, name: "Web Job Scraper" });
}

async function fill(user = userEvent.setup()) {
  await user.type(screen.getByLabelText(/^Job title/), "Python Developer");
  await user.type(screen.getByLabelText(/^Location/), "Austin, TX");
  await user.selectOptions(screen.getByLabelText(/^Job level/), "senior");
  await user.type(screen.getByLabelText(/^Years of experience/), "5");
  await user.type(
    screen.getByRole("textbox", { name: /^Relevant skills/ }),
    "Python{Enter}PostgreSQL{Enter}",
  );
  await user.clear(screen.getByLabelText(/^Number of jobs pulled/));
  await user.type(screen.getByLabelText(/^Number of jobs pulled/), "10");
  await user.clear(screen.getByLabelText(/^Number of jobs selected/));
  await user.type(screen.getByLabelText(/^Number of jobs selected/), "3");
  return user;
}

describe("SearchPage", () => {
  it("starts a search with the form values and opens the run", async () => {
    const calls = stubApi({
      [RUNS]: () => [],
      [START]: () => jsonResponse(202, { run_id: "r1", job_id: "j1" }),
      "GET /api/scraper/runs/r1": () => makeRun(),
    });
    await openPage();
    const user = await fill();

    await user.click(screen.getByRole("button", { name: "Run search" }));

    expect(await screen.findByRole("heading", { level: 2, name: "Top 1 of 10" })).toBeVisible();
    const post = calls.find((c) => c.method === "POST");
    expect(JSON.parse(String(post?.init?.body))).toEqual(OPTIONS);
  });

  it("shows errors and doesn't call the API when the form is invalid", async () => {
    const calls = stubApi({ [RUNS]: () => [] });
    await openPage();
    const user = await fill();
    await user.clear(screen.getByLabelText(/^Number of jobs selected/));
    await user.type(screen.getByLabelText(/^Number of jobs selected/), "50");

    await user.click(screen.getByRole("button", { name: "Run search" }));

    expect(screen.getByLabelText(/^Number of jobs selected/)).toHaveAccessibleDescription(
      "Jobs selected can't be more than jobs pulled.",
    );
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });

  it("shows the server's message when a search is already running", async () => {
    stubApi({
      [RUNS]: () => [],
      [START]: () =>
        jsonResponse(409, {
          error: {
            code: "search_running",
            message: "A search is already running.",
            request_id: "r",
          },
        }),
    });
    await openPage();
    const user = await fill();
    await user.click(screen.getByRole("button", { name: "Run search" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("A search is already running.");
  });

  it("imports a YAML file into the form", async () => {
    stubApi({ [RUNS]: () => [] });
    await openPage();
    const file = new File([`${toYaml(OPTIONS)}extra: true\n`], "saved.yaml");

    await userEvent.upload(screen.getByTestId("yaml-input"), file);

    expect(await screen.findByRole("status")).toHaveTextContent("Loaded saved.yaml.");
    expect(screen.getByRole("status")).toHaveTextContent("Ignored unknown keys: extra.");
    expect(screen.getByLabelText(/^Job title/)).toHaveValue("Python Developer");
    expect(screen.getByLabelText(/^Job level/)).toHaveValue("senior");
    const tags = within(screen.getByRole("list", { name: "Relevant skills tags" }));
    expect(tags.getAllByRole("listitem").map((li) => li.firstChild?.textContent)).toEqual([
      "Python",
      "PostgreSQL",
    ]);
  });

  it("leaves the form unchanged when the YAML file is bad", async () => {
    stubApi({ [RUNS]: () => [] });
    await openPage();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/^Job title/), "Keep me");
    const bad = toYaml(OPTIONS).replace("version: 1", "version: 2");

    await userEvent.upload(screen.getByTestId("yaml-input"), new File([bad], "bad.yaml"));

    expect(await screen.findByRole("alert")).toHaveTextContent("Unsupported version 2");
    expect(screen.getByLabelText(/^Job title/)).toHaveValue("Keep me");
  });

  it("exports the options as a YAML download", async () => {
    stubApi({ [RUNS]: () => [] });
    const blobs: Blob[] = [];
    URL.createObjectURL = vi.fn((blob: Blob) => {
      blobs.push(blob);
      return "blob:x";
    });
    URL.revokeObjectURL = vi.fn();
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    await openPage();
    const user = await fill();

    await user.click(screen.getByRole("button", { name: "Export YAML" }));

    expect(click).toHaveBeenCalledOnce();
    expect(await blobs[0]!.text()).toBe(toYaml(OPTIONS));
    click.mockRestore();
  });

  it("lists past searches", async () => {
    stubApi({ [RUNS]: () => [makeRun({ id: "r9", selected_count: 3 })] });
    await openPage();
    const link = await screen.findByRole("link", { name: "Python Developer" });
    expect(link).toHaveAttribute("href", "/scraper/runs/r9");
    await waitFor(() => expect(screen.getByText("3 of 10")).toBeVisible());
    expect(screen.getByText("Done")).toBeVisible();
  });
});
