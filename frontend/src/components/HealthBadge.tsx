import { useHealth } from "../lib/health";

/** Header badge showing whether the database and the local LLM are reachable (FND-3.5). */
export function HealthBadge() {
  const { data, isError, isPending } = useHealth();

  if (isPending) {
    return <span className="badge badge-muted">Checking…</span>;
  }
  if (isError) {
    return (
      <span className="badge badge-error" title="The backend isn't responding.">
        Backend offline
      </span>
    );
  }
  const problems = [data.db !== "ok" && "database", data.llm !== "ok" && "LLM"].filter(Boolean);
  if (problems.length === 0) {
    return (
      <span className="badge badge-ok" title={`Model: ${data.model}`}>
        All systems ok
      </span>
    );
  }
  return (
    <span className="badge badge-error" title={data.llm_message ?? undefined}>
      {problems.join(" & ")} unavailable
    </span>
  );
}
