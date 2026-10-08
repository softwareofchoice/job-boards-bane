import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { jsonResponse, renderApp, stubApi } from "../../test/render";
import { makeSkill } from "./fixtures";
import { groupByRole, validateSkill } from "./validation";

afterEach(() => vi.unstubAllGlobals());

const SKILLS = [
  makeSkill({ id: "a", skill_name: "Go", role: "A role" }),
  makeSkill({ id: "b", skill_name: "Docker", role: "b role" }),
  makeSkill({ id: "c", skill_name: "Python", role: "B ROLE" }),
];

async function fill(name: string, role: string, summary: string) {
  await userEvent.type(screen.getByLabelText(/^Skill name/), name);
  await userEvent.type(screen.getByLabelText(/^Role/), role);
  await userEvent.type(screen.getByLabelText(/^Skill summary/), summary);
}

describe("skills helpers", () => {
  it("groups by role ignoring case, keeping order", () => {
    const groups = groupByRole(SKILLS);
    expect(groups.map(([role, items]) => [role, items.map((s) => s.skill_name)])).toEqual([
      ["A role", ["Go"]],
      ["b role", ["Docker", "Python"]],
    ]);
  });

  it("requires every field and checks lengths", () => {
    expect(validateSkill({ skill_name: " ", role: "r".repeat(201), summary: "ok" })).toEqual({
      skill_name: "Enter the skill name.",
      role: "Role must be at most 200 characters.",
    });
  });
});

describe("SkillsPage", () => {
  it("lists saved skills grouped by role", async () => {
    stubApi({ "GET /api/rounder/skills": () => SKILLS, "GET /api/rounder/skills/roles": () => [] });
    renderApp("/resume-rounder/skills");
    const group = await screen.findByRole("region", { name: "b role" });
    expect(within(group).getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByRole("region", { name: "A role" })).toHaveTextContent("Go");
  });

  it("adds a skill and suggests existing roles", async () => {
    let saved = false;
    const calls = stubApi({
      "GET /api/rounder/skills": () => (saved ? [makeSkill()] : []),
      "GET /api/rounder/skills/roles": () => ["Software Engineer at Acme"],
      "POST /api/rounder/skills": () => {
        saved = true;
        return jsonResponse(201, makeSkill());
      },
    });
    const { container } = renderApp("/resume-rounder/skills");
    expect(await screen.findByText("No skills yet. Add your first one.")).toBeVisible();
    await waitFor(() =>
      expect(container.querySelector("datalist option")).toHaveAttribute(
        "value",
        "Software Engineer at Acme",
      ),
    );

    await fill("PostgreSQL", "Software Engineer at Acme", "Designed the reporting schema.");
    await userEvent.click(screen.getByRole("button", { name: "Add skill" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Saved “PostgreSQL” for Software Engineer at Acme.",
    );
    const post = calls.find((c) => c.method === "POST");
    expect(JSON.parse(String(post?.init?.body))).toEqual({
      skill_name: "PostgreSQL",
      role: "Software Engineer at Acme",
      summary: "Designed the reporting schema.",
    });
    expect(await screen.findByRole("region", { name: "Software Engineer at Acme" })).toBeVisible();
  });

  it("offers to edit the existing entry when the skill is a duplicate", async () => {
    const existing = makeSkill({ id: "s9", summary: "The saved summary." });
    const calls = stubApi({
      "GET /api/rounder/skills": () => [existing],
      "GET /api/rounder/skills/roles": () => [],
      "POST /api/rounder/skills": () =>
        jsonResponse(409, {
          error: {
            code: "duplicate_skill",
            message: "“PostgreSQL” is already saved for the role “Software Engineer at Acme”.",
            request_id: "r1",
            existing_id: "s9",
          },
        }),
      "PUT /api/rounder/skills/s9": () => existing,
    });
    renderApp("/resume-rounder/skills");
    await screen.findByRole("region", { name: "Software Engineer at Acme" });

    await fill("postgresql", "Software Engineer at Acme", "Another summary.");
    await userEvent.click(screen.getByRole("button", { name: "Add skill" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("is already saved");

    await userEvent.click(within(alert).getByRole("button", { name: "Edit existing" }));
    expect(screen.getByRole("heading", { name: "Edit “PostgreSQL”" })).toBeVisible();
    expect(screen.getByLabelText(/^Skill summary/)).toHaveValue("The saved summary.");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
  });

  it("shows the client-side errors without calling the API", async () => {
    const calls = stubApi({
      "GET /api/rounder/skills": () => [],
      "GET /api/rounder/skills/roles": () => [],
    });
    renderApp("/resume-rounder/skills");
    await userEvent.click(await screen.findByRole("button", { name: "Add skill" }));
    expect(screen.getByText("Enter the skill name.")).toBeVisible();
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });

  it("deletes a skill", async () => {
    let deleted = false;
    stubApi({
      "GET /api/rounder/skills": () => (deleted ? [] : [makeSkill()]),
      "GET /api/rounder/skills/roles": () => [],
      "DELETE /api/rounder/skills/s1": () => {
        deleted = true;
        return new Response(null, { status: 204 });
      },
    });
    renderApp("/resume-rounder/skills");
    await userEvent.click(
      await screen.findByRole("button", { name: "Delete PostgreSQL (Software Engineer at Acme)" }),
    );
    expect(await screen.findByText("No skills yet. Add your first one.")).toBeVisible();
  });
});
