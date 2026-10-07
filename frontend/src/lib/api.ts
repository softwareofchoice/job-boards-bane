/** Fetch wrapper for the backend API. Turns error bodies into `ApiError` (FND-5). */

export type FieldErrors = Record<string, string>;

interface ValidationIssue {
  loc: (string | number)[];
  msg: string;
}

interface AppErrorBody {
  error: { code: string; message: string; request_id: string };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;
  /** Server-side validation errors by field name, for showing next to each field (FND-5.1). */
  readonly fieldErrors: FieldErrors;

  constructor(opts: {
    status: number;
    code: string;
    message: string;
    requestId?: string | null;
    fieldErrors?: FieldErrors;
  }) {
    super(opts.message);
    this.name = "ApiError";
    this.status = opts.status;
    this.code = opts.code;
    this.requestId = opts.requestId ?? null;
    this.fieldErrors = opts.fieldErrors ?? {};
  }

  /** The message to show the user, with the request ID when there is one (FND-5.2). */
  get displayMessage(): string {
    return this.requestId ? `${this.message} (reference: ${this.requestId})` : this.message;
  }
}

const LOCATION_PREFIXES = new Set(["body", "query", "path", "header", "form"]);

/** Map FastAPI's 422 `detail` list to `{field: message}`, keeping the first message per field. */
export function toFieldErrors(detail: ValidationIssue[]): FieldErrors {
  const errors: FieldErrors = {};
  for (const issue of detail) {
    const path = issue.loc.filter((part, i) => !(i === 0 && LOCATION_PREFIXES.has(String(part))));
    const field = path.length > 0 ? path.join(".") : "_form";
    errors[field] ??= issue.msg.replace(/^Value error, /, "");
  }
  return errors;
}

function isAppErrorBody(body: unknown): body is AppErrorBody {
  return typeof body === "object" && body !== null && "error" in body;
}

function isValidationBody(body: unknown): body is { detail: ValidationIssue[] } {
  return (
    typeof body === "object" &&
    body !== null &&
    "detail" in body &&
    Array.isArray((body as { detail: unknown }).detail)
  );
}

export async function toApiError(response: Response): Promise<ApiError> {
  const requestId = response.headers.get("X-Request-ID");
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // Not JSON (e.g. a proxy error page); fall through to the generic message.
  }
  if (isAppErrorBody(body)) {
    return new ApiError({
      status: response.status,
      code: body.error.code,
      message: body.error.message,
      requestId: body.error.request_id ?? requestId,
    });
  }
  if (response.status === 422 && isValidationBody(body)) {
    return new ApiError({
      status: 422,
      code: "validation_error",
      message: "Please fix the highlighted fields.",
      requestId,
      fieldErrors: toFieldErrors(body.detail),
    });
  }
  return new ApiError({
    status: response.status,
    code: "http_error",
    message: `The server responded with ${response.status}.`,
    requestId,
  });
}

/** Call the API. JSON bodies are encoded for you; pass `FormData` for uploads. */
export async function api<T>(
  path: string,
  init: Omit<RequestInit, "body"> & { body?: unknown } = {},
): Promise<T> {
  const { body, headers, ...rest } = init;
  const isForm = body instanceof FormData;
  let response: Response;
  try {
    response = await fetch(path, {
      ...rest,
      headers: {
        Accept: "application/json",
        ...(body !== undefined && !isForm ? { "Content-Type": "application/json" } : {}),
        ...headers,
      },
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    });
  } catch {
    throw new ApiError({
      status: 0,
      code: "network_error",
      message: "Can't reach the server. Is the backend running?",
    });
  }
  if (!response.ok) {
    throw await toApiError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
