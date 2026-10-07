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
