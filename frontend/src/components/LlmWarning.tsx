import { useHealth } from "../lib/health";

/** Banner for pages that need the local LLM, shown when it can't be used (FND-3.5). */
export function LlmWarning() {
  const { data } = useHealth();
  if (!data || data.llm === "ok") {
    return null;
  }
  return (
    <div role="alert" className="banner banner-warning">
      <strong>The local LLM isn't available.</strong>{" "}
      {data.llm_message ?? "Start Ollama with `ollama serve`."}
    </div>
  );
}
