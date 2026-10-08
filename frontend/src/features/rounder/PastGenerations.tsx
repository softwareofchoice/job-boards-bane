import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { formatDateTime } from "../../lib/format";
import { isActive, listGenerations, rounderKeys, type GenerationSummary } from "./api";

const STATUS_LABEL: Record<GenerationSummary["status"], string> = {
  queued: "Queued",
  running: "Running",
  succeeded: "Done",
  failed: "Failed",
};

/** Previously generated resumes, newest first (RND-4.4). */
export function PastGenerations() {
  const { data, error } = useQuery({
    queryKey: rounderKeys.generations,
    queryFn: listGenerations,
    refetchInterval: (query) => (query.state.data?.some((g) => isActive(g.status)) ? 3000 : false),
  });

  return (
    <section className="past-runs" aria-labelledby="past-generations-heading">
      <h2 id="past-generations-heading">Past resumes</h2>
      {error ? (
        <p role="alert" className="field-error">
          Couldn't load past resumes.
        </p>
      ) : null}
      {data && data.length === 0 ? <p className="empty">No resumes generated yet.</p> : null}
      {data && data.length > 0 ? (
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Job</th>
              <th scope="col">When</th>
              <th scope="col">Status</th>
              <th scope="col">Pages</th>
            </tr>
          </thead>
          <tbody>
            {data.map((g) => (
              <tr key={g.id}>
                <td>
                  <Link to={`/resume-rounder/generations/${g.id}`}>{g.job_title}</Link>
                  <span className="muted"> · {g.company_name}</span>
                </td>
                <td>
                  <time dateTime={g.created_at}>{formatDateTime(g.created_at)}</time>
                </td>
                <td>{STATUS_LABEL[g.status]}</td>
                <td>
                  {g.final_pages ?? "–"} of {Number(g.target_pages)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
