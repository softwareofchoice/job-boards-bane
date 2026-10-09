import { api } from "../../lib/api";

export interface StoredFileInfo {
  id: string;
  url: string;
  original_name: string;
  content_type: string;
  size_bytes: number;
}

export type Status = "applied" | "interviewing" | "offer" | "rejected";

export interface StatusChange {
  from_status: Status | null;
  to_status: Status;
  changed_at: string;
}

export interface FlowPath {
  statuses: [Status, Status, Status];
  count: number;
}

export interface StatusFlow {
  total: number;
  paths: FlowPath[];
}

export interface Application {
  id: string;
  job_title: string;
  company_name: string;
  posting_url: string;
  screenshot: StoredFileInfo | null;
  resume: StoredFileInfo;
  created_at: string;
  status: Status;
  allowed_next: Status[];
  status_history: StatusChange[];
}

export interface ApplicationPage {
  items: Application[];
  total: number;
  page: number;
  page_size: number;
}

export interface DuplicateCheck {
  duplicate: boolean;
  previous_created_at: string | null;
}

export interface NewApplication {
  job_title: string;
  company_name: string;
  posting_url: string;
  resume: File;
  screenshot: File | null;
}

const BASE = "/api/tracker/applications";

export const trackerKeys = {
  all: ["tracker"] as const,
  list: (q: string, page: number, status: Status | "") =>
    ["tracker", "list", q, page, status] as const,
  flow: ["tracker", "flow"] as const,
  detail: (id: string) => ["tracker", "detail", id] as const,
};

export function createApplication(input: NewApplication): Promise<Application> {
  const form = new FormData();
  form.set("job_title", input.job_title);
  form.set("company_name", input.company_name);
  form.set("posting_url", input.posting_url);
  form.set("resume", input.resume);
  if (input.screenshot) {
    form.set("screenshot", input.screenshot);
  }
  return api<Application>(BASE, { method: "POST", body: form });
}

export function listApplications(
  q: string,
  page: number,
  status: Status | "" = "",
): Promise<ApplicationPage> {
  const params = new URLSearchParams({ page: String(page) });
  if (q) {
    params.set("q", q);
  }
  if (status) {
    params.set("status", status);
  }
  return api<ApplicationPage>(`${BASE}?${params}`);
}

export function getApplication(id: string): Promise<Application> {
  return api<Application>(`${BASE}/${encodeURIComponent(id)}`);
}

export function deleteApplication(id: string): Promise<void> {
  return api<void>(`${BASE}/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export function checkUrl(url: string): Promise<DuplicateCheck> {
  return api<DuplicateCheck>(`${BASE}/check-url?${new URLSearchParams({ url })}`);
}

export function changeStatus(id: string, status: Status): Promise<Application> {
  return api<Application>(`${BASE}/${encodeURIComponent(id)}/status`, {
    method: "POST",
    body: { status },
  });
}

export function undoStatusChange(id: string): Promise<Application> {
  return api<Application>(`${BASE}/${encodeURIComponent(id)}/status/latest`, {
    method: "DELETE",
  });
}

export function getStatusFlow(): Promise<StatusFlow> {
  return api<StatusFlow>("/api/tracker/status-flow");
}
