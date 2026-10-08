import { load } from "js-yaml";

import { OPTIONS } from "./fixtures";
import { EMPTY_FORM, fromYaml, toForm, toYaml, validateForm, yamlFilename } from "./options";

describe("validateForm", () => {
  it("converts a valid form to options", () => {
    const result = validateForm({ ...toForm(OPTIONS), location: "  " });
    expect(result.errors).toBeNull();
    expect(result.options).toEqual({ ...OPTIONS, location: null });
  });

  it("lists every problem", () => {
    const result = validateForm(EMPTY_FORM);
    expect(Object.keys(result.errors ?? {}).sort()).toEqual([
      "job_level",
      "job_title",
      "skills",
      "years_experience",
    ]);
  });

  it("rejects selected > pulled and out-of-range numbers", () => {
    const form = { ...toForm(OPTIONS), jobs_pulled: "5", jobs_selected: "6" };
    expect(validateForm(form).errors).toEqual({
      jobs_selected: "Jobs selected can't be more than jobs pulled.",
    });
    expect(validateForm({ ...form, jobs_pulled: "101" }).errors?.jobs_pulled).toMatch(/1 to 100/);
    expect(validateForm({ ...form, days_since_posting: "2.5" }).errors?.days_since_posting).toBe(
      "Enter a whole number.",
    );
  });
});

describe("YAML", () => {
  it("exports the documented format", () => {
    const doc = load(toYaml(OPTIONS));
    expect(doc).toEqual({
      version: 1,
      search: {
        job_title: "Python Developer",
        location: "Austin, TX",
        days_since_posting: 7,
        skills: ["Python", "PostgreSQL"],
        years_experience: 5,
        job_level: "senior",
      },
      results: { jobs_pulled: 10, jobs_selected: 3 },
    });
    expect(toYaml(OPTIONS).startsWith("# Job Board's Bane")).toBe(true);
  });

  it("round-trips: export then import gives the same values", () => {
    const result = fromYaml(toYaml(OPTIONS));
    expect(result).toEqual({ ok: true, form: toForm(OPTIONS), ignoredKeys: [] });
  });

  it("reports ignored keys", () => {
    const text = `${toYaml(OPTIONS)}extra: 1\nsearch_x: 2\n`;
    const withNested = text.replace("search:\n", "search:\n  remote_only: true\n");
    const result = fromYaml(withNested);
    expect(result.ok && result.ignoredKeys).toEqual(["extra", "search_x", "search.remote_only"]);
  });

  it.each([
    ["not YAML", "search: [unclosed", /isn't valid YAML/],
    ["wrong version", toYaml(OPTIONS).replace("version: 1", "version: 2"), /Unsupported version 2/],
    ["no version", "search: {}\n", /Unsupported version \(missing\)/],
    ["a list", "- a\n- b\n", /doesn't contain search options/],
    [
      "X > N",
      toYaml(OPTIONS).replace("jobs_selected: 3", "jobs_selected: 30"),
      /jobs_selected: Jobs selected can't be more than jobs pulled/,
    ],
    ["bad level", toYaml(OPTIONS).replace("job_level: senior", "job_level: wizard"), /job_level/],
  ])("rejects %s", (_name, text, problem) => {
    const result = fromYaml(text);
    expect(result.ok).toBe(false);
    expect(!result.ok && result.problems.join("\n")).toMatch(problem);
  });

  it("names the file after the title and date", () => {
    expect(yamlFilename(OPTIONS, new Date("2026-10-08T12:00:00Z"))).toBe(
      "job-search-python-developer-20261008.yaml",
    );
  });
});
