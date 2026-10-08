import type { FieldErrors } from "../../lib/api";
import { MAX_UPLOAD_BYTES } from "../../lib/config";
import type { Skill, SkillInput } from "./api";

const LIMITS: Record<keyof SkillInput, [number, string]> = {
  skill_name: [100, "Skill name"],
  role: [200, "Role"],
  summary: [1000, "Summary"],
};

export function validateSkill(values: SkillInput): FieldErrors {
  const errors: FieldErrors = {};
  for (const [key, [max, label]] of Object.entries(LIMITS)) {
    const value = values[key as keyof SkillInput].trim();
    if (!value) errors[key] = `Enter the ${label.toLowerCase()}.`;
    else if (value.length > max) errors[key] = `${label} must be at most ${max} characters.`;
  }
  return errors;
}

/** Saved skills grouped by role, in the order the API returns them. */
export function groupByRole(skills: Skill[]): [string, Skill[]][] {
  const groups = new Map<string, [string, Skill[]]>();
  for (const skill of skills) {
    const key = skill.role.toLowerCase();
    if (!groups.has(key)) groups.set(key, [skill.role, []]);
    groups.get(key)![1].push(skill);
  }
  return [...groups.values()];
}

const MIN_POSTING = 200;
export const MAX_POSTING = 20_000;
const POSTING_CHOICE = "Provide a job posting URL or paste the description";
export const TEMPLATE_ACCEPT =
  ".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

export type PostingMode = "url" | "text";

export interface FormValues {
  template: File | null;
  mode: PostingMode;
  posting_url: string;
  posting_text: string;
  job_title: string;
  company_name: string;
}

export function validateGenerate(values: FormValues): FieldErrors {
  const errors: FieldErrors = {};
  if (!values.template) errors.template = "Choose your resume (.docx).";
  else if (!values.template.name.toLowerCase().endsWith(".docx"))
    errors.template = "Upload a Word (.docx) file.";
  else if (values.template.size > MAX_UPLOAD_BYTES)
    errors.template = `The file is larger than the ${MAX_UPLOAD_BYTES / 1024 / 1024} MB limit.`;
  if (values.mode === "url") {
    const url = values.posting_url.trim();
    if (!url) errors.posting = POSTING_CHOICE;
    else if (!/^https?:\/\/[^\s/]+/i.test(url))
      errors.posting_url = "Enter a full web address starting with http:// or https://";
  } else {
    const text = values.posting_text.trim();
    if (!text) errors.posting = POSTING_CHOICE;
    else if (text.length < MIN_POSTING)
      errors.posting_text = `Paste the whole job description (at least ${MIN_POSTING} characters).`;
    else if (text.length > MAX_POSTING)
      errors.posting_text = `The description is too long (at most 20,000 characters).`;
  }
  if (!values.job_title.trim()) errors.job_title = "Enter the job title.";
  if (!values.company_name.trim()) errors.company_name = "Enter the company name.";
  return errors;
}
