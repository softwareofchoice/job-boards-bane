/**
 * Client-side checks that mirror the server's rules (TRK-1.1), so most mistakes are caught
 * before upload. The server checks again and its errors are shown the same way.
 */
import type { FieldErrors } from "../../lib/api";

export const MAX_NAME = 200;
export const MAX_URL = 2048;
export const RESUME_ACCEPT =
  ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";
export const SCREENSHOT_ACCEPT = ".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp";

const RESUME_EXTENSIONS = [".pdf", ".docx"];
const SCREENSHOT_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp"];

export interface ApplicationFormValues {
  job_title: string;
  company_name: string;
  posting_url: string;
  resume: File | null;
  screenshot: File | null;
}

export function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return (url.protocol === "http:" || url.protocol === "https:") && url.hostname !== "";
  } catch {
    return false;
  }
}

function hasExtension(file: File, extensions: string[]): boolean {
  const name = file.name.toLowerCase();
  return extensions.some((ext) => name.endsWith(ext));
}

export function validateApplication(
  values: ApplicationFormValues,
  maxUploadBytes: number,
): FieldErrors {
  const errors: FieldErrors = {};
  const title = values.job_title.trim();
  const company = values.company_name.trim();
  const url = values.posting_url.trim();

  if (!title) errors.job_title = "Enter the job title.";
  else if (title.length > MAX_NAME) errors.job_title = `Use at most ${MAX_NAME} characters.`;

  if (!company) errors.company_name = "Enter the company name.";
  else if (company.length > MAX_NAME) errors.company_name = `Use at most ${MAX_NAME} characters.`;

  if (!url) errors.posting_url = "Enter the job posting URL.";
  else if (url.length > MAX_URL) errors.posting_url = `Use at most ${MAX_URL} characters.`;
  else if (!isHttpUrl(url))
    errors.posting_url = "Enter a full web address starting with http:// or https://";

  const tooBig = `The file is larger than the ${Math.round(maxUploadBytes / 1024 / 1024)} MB limit.`;
  if (!values.resume) errors.resume = "Choose a file.";
  else if (!hasExtension(values.resume, RESUME_EXTENSIONS))
    errors.resume = "Upload a PDF or DOCX file.";
  else if (values.resume.size > maxUploadBytes) errors.resume = tooBig;

  if (values.screenshot) {
    if (!hasExtension(values.screenshot, SCREENSHOT_EXTENSIONS))
      errors.screenshot = "Upload a PNG, JPEG or WebP image.";
    else if (values.screenshot.size > maxUploadBytes) errors.screenshot = tooBig;
  }
  return errors;
}
