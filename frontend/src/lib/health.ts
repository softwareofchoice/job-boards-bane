import { useQuery } from "@tanstack/react-query";

import { api } from "./api";

export interface Health {
  db: "ok" | "error";
  llm: "ok" | "error";
  model: string;
  llm_message: string | null;
}

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => api<Health>("/api/health"),
    refetchInterval: 30_000,
    retry: false,
  });
}
