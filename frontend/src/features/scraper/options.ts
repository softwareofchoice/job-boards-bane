/**
 * Search options: the form's rules (mirroring the backend's SearchOptions, SCR-1.1) and the
 * YAML file format for saving and loading them (SCR-2).
 */
import { dump, load } from "js-yaml";

import type { FieldErrors } from "../../lib/api";

export const JOB_LEVELS = [
  ["internship", "Internship"],
  ["entry", "Entry level"],
  ["mid", "Mid level"],
  ["senior", "Senior"],
  ["staff_principal", "Staff / Principal"],
  ["manager", "Manager"],
  ["director_plus", "Director or above"],
] as const;

export type JobLevel = (typeof JOB_LEVELS)[number][0];

export interface SearchOptions {
  job_title: string;
  location: string | null;
  days_since_posting: number;
  skills: string[];
  years_experience: number;
  job_level: JobLevel;
  jobs_pulled: number;
  jobs_selected: number;
}

/** What the form edits: numbers stay as typed until submitted. */
export interface SearchForm {
  job_title: string;
  location: string;
  days_since_posting: string;
  skills: string[];
  years_experience: string;
  job_level: JobLevel | "";
  jobs_pulled: string;
  jobs_selected: string;
}

export const EMPTY_FORM: SearchForm = {
  job_title: "",
  location: "",
  days_since_posting: "7",
  skills: [],
  years_experience: "",
  job_level: "",
  jobs_pulled: "25",
  jobs_selected: "10",
};

export const YAML_VERSION = 1;
const MAX_YAML_BYTES = 64 * 1024;

export function levelLabel(level: string): string {
  return JOB_LEVELS.find(([value]) => value === level)?.[1] ?? level;
}

function wholeNumber(
  errors: FieldErrors,
  field: string,
  raw: string,
  min: number,
  max: number,
): number | null {
  const text = raw.trim();
  if (text === "") {
    errors[field] = "Enter a number.";
    return null;
  }
  const n = Number(text);
  if (!Number.isInteger(n)) {
    errors[field] = "Enter a whole number.";
    return null;
  }
  if (n < min || n > max) {
    errors[field] = `Enter a number from ${min} to ${max}.`;
    return null;
  }
  return n;
}

/** Check the form; returns the options to send, or the errors to show. */
export function validateForm(
  form: SearchForm,
): { options: SearchOptions; errors: null } | { options: null; errors: FieldErrors } {
  const errors: FieldErrors = {};
  const title = form.job_title.trim();
  if (!title) errors.job_title = "Enter the job title.";
  else if (title.length > 200) errors.job_title = "Use at most 200 characters.";

  const location = form.location.trim();
  if (location.length > 200) errors.location = "Use at most 200 characters.";

  const days = wholeNumber(errors, "days_since_posting", form.days_since_posting, 1, 60);
  const years = wholeNumber(errors, "years_experience", form.years_experience, 0, 50);
  const pulled = wholeNumber(errors, "jobs_pulled", form.jobs_pulled, 1, 100);
  const selected = wholeNumber(errors, "jobs_selected", form.jobs_selected, 1, 100);
  if (pulled !== null && selected !== null && selected > pulled) {
    errors.jobs_selected = "Jobs selected can't be more than jobs pulled.";
  }

  const skills = form.skills.map((s) => s.trim()).filter(Boolean);
  if (skills.length === 0) errors.skills = "Add at least one skill.";
  else if (skills.length > 30) errors.skills = "Use at most 30 skills.";
  else if (skills.some((s) => s.length > 50))
    errors.skills = "Each skill can be at most 50 characters.";

  if (!form.job_level) errors.job_level = "Choose a job level.";

  if (Object.keys(errors).length > 0) {
    return { options: null, errors };
  }
  return {
    errors: null,
    options: {
      job_title: title,
      location: location || null,
      days_since_posting: days!,
      skills,
      years_experience: years!,
      job_level: form.job_level as JobLevel,
      jobs_pulled: pulled!,
      jobs_selected: selected!,
    },
  };
}

export function toForm(options: SearchOptions): SearchForm {
  return {
    job_title: options.job_title,
    location: options.location ?? "",
    days_since_posting: String(options.days_since_posting),
    skills: [...options.skills],
    years_experience: String(options.years_experience),
    job_level: options.job_level,
    jobs_pulled: String(options.jobs_pulled),
    jobs_selected: String(options.jobs_selected),
  };
}

/** The YAML file for a set of options (SCR-2.1). */
export function toYaml(options: SearchOptions): string {
  const doc = {
    version: YAML_VERSION,
    search: {
      job_title: options.job_title,
      location: options.location,
      days_since_posting: options.days_since_posting,
      skills: options.skills,
      years_experience: options.years_experience,
      job_level: options.job_level,
    },
    results: {
      jobs_pulled: options.jobs_pulled,
      jobs_selected: options.jobs_selected,
    },
  };
  return `# Job Board's Bane: job search options\n${dump(doc, { lineWidth: 100 })}`;
}

export function yamlFilename(options: SearchOptions, now = new Date()): string {
  const slug =
    options.job_title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 40) || "search";
  const date = now.toISOString().slice(0, 10).replaceAll("-", "");
  return `job-search-${slug}-${date}.yaml`;
}

export type YamlImport =
  { ok: true; form: SearchForm; ignoredKeys: string[] } | { ok: false; problems: string[] };

const SEARCH_KEYS = [
  "job_title",
  "location",
  "days_since_posting",
  "skills",
  "years_experience",
  "job_level",
] as const;
const RESULT_KEYS = ["jobs_pulled", "jobs_selected"] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asText(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

/**
 * Read a YAML file into form values (SCR-2.2). On any problem the form must stay unchanged and
 * every problem is listed (SCR-2.3); unknown keys are ignored and reported (SCR-2.4).
 */
export function fromYaml(text: string): YamlImport {
  if (new Blob([text]).size > MAX_YAML_BYTES) {
    return { ok: false, problems: ["The file is larger than 64 KB."] };
  }
  let doc: unknown;
  try {
    doc = load(text);
  } catch (e) {
    return { ok: false, problems: [`The file isn't valid YAML: ${(e as Error).message}`] };
  }
  if (!isRecord(doc)) {
    return { ok: false, problems: ["The file doesn't contain search options."] };
  }
  if (doc.version !== YAML_VERSION) {
    return {
      ok: false,
      problems: [
        `Unsupported version ${String(doc.version ?? "(missing)")}; expected ${YAML_VERSION}.`,
      ],
    };
  }
  const search = isRecord(doc.search) ? doc.search : {};
  const results = isRecord(doc.results) ? doc.results : {};
  const ignoredKeys = [
    ...Object.keys(doc).filter((k) => !["version", "search", "results"].includes(k)),
    ...Object.keys(search)
      .filter((k) => !(SEARCH_KEYS as readonly string[]).includes(k))
      .map((k) => `search.${k}`),
    ...Object.keys(results)
      .filter((k) => !(RESULT_KEYS as readonly string[]).includes(k))
      .map((k) => `results.${k}`),
  ];

  const skills = search.skills;
  const level = asText(search.job_level);
  const form: SearchForm = {
    job_title: asText(search.job_title),
    location: asText(search.location),
    days_since_posting: asText(search.days_since_posting),
    skills: Array.isArray(skills) ? skills.map(asText) : [],
    years_experience: asText(search.years_experience),
    job_level: JOB_LEVELS.some(([v]) => v === level) ? (level as JobLevel) : "",
    jobs_pulled: asText(results.jobs_pulled),
    jobs_selected: asText(results.jobs_selected),
  };

  const problems: string[] = [];
  if (skills !== undefined && !Array.isArray(skills)) problems.push("skills: must be a list.");
  if (level && !form.job_level) {
    problems.push(`job_level: "${level}" isn't one of ${JOB_LEVELS.map(([v]) => v).join(", ")}.`);
  }
  const checked = validateForm(form);
  if (checked.errors) {
    for (const [field, message] of Object.entries(checked.errors)) {
      if (!problems.some((p) => p.startsWith(`${field}:`))) problems.push(`${field}: ${message}`);
    }
  }
  return problems.length > 0 ? { ok: false, problems } : { ok: true, form, ignoredKeys };
}

/** Save text as a download in the browser. */
export function downloadText(filename: string, text: string, type = "application/yaml"): void {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
