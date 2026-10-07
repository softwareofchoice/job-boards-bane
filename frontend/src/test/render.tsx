import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";

import { routes } from "../app/routes";
import type { Health } from "../lib/health";

export const HEALTHY: Health = { db: "ok", llm: "ok", model: "llama3.1:8b", llm_message: null };

/** Stub `fetch` so `/api/health` returns `health` and anything else 404s. */
export function stubHealth(health: Health | "offline" = HEALTHY) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/api/health") {
        if (health === "offline") {
          throw new TypeError("Failed to fetch");
        }
        return new Response(JSON.stringify(health), {
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response("{}", { status: 404 });
    }),
  );
}

export function renderApp(path = "/") {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

type Handler = (url: URL, init: RequestInit | undefined) => unknown;

export interface RecordedCall {
  method: string;
  url: URL;
  init: RequestInit | undefined;
}

/**
 * Stub `fetch` with handlers keyed by "METHOD /path" (path without query string).
 * A handler returns a JSON body (status 200), or a `Response` for anything else.
 * `/api/health` answers healthy unless overridden. Returns the list of calls made.
 */
export function stubApi(handlers: Record<string, Handler>): RecordedCall[] {
  const calls: RecordedCall[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), "http://localhost");
      const method = (init?.method ?? "GET").toUpperCase();
      calls.push({ method, url, init });
      const handler =
        handlers[`${method} ${url.pathname}`] ??
        (url.pathname === "/api/health" ? () => HEALTHY : undefined);
      if (!handler) {
        return new Response(JSON.stringify({ detail: "Not Found" }), { status: 404 });
      }
      const result = await handler(url, init);
      if (result instanceof Response) {
        return result;
      }
      return new Response(JSON.stringify(result), {
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  return calls;
}

export function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
