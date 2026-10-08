import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { ApiError } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { deleteRun, isActive, listRuns, scraperKeys, type RunSummary } from "./api";

const STATUS_LABEL: Record<RunSummary["status"], string> = {
  queued: "Queued",
  running: "Running",
  succeeded: "Done",
  failed: "Failed",
};

/** Previous searches, newest first (SCR-5.5). */
export function PastRuns() {
  const queryClient = useQueryClient();
  const { data, error } = useQuery({
    queryKey: scraperKeys.runs,
    queryFn: listRuns,
    refetchInterval: (query) => (query.state.data?.some((r) => isActive(r.status)) ? 3000 : false),
  });
  const remove = useMutation({
    mutationFn: deleteRun,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: scraperKeys.runs }),
  });

  return (
    <section className="past-runs" aria-labelledby="past-searches-heading">
      <h2 id="past-searches-heading">Past searches</h2>
      {error ? (
        <p role="alert" className="field-error">
          {error instanceof ApiError ? error.displayMessage : "Couldn't load past searches."}
        </p>
      ) : null}
      {data && data.length === 0 ? <p className="empty">No searches yet.</p> : null}
      {data && data.length > 0 ? (
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Search</th>
              <th scope="col">When</th>
              <th scope="col">Status</th>
              <th scope="col">Results</th>
              <th scope="col">
                <span className="visually-hidden">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {data.map((run) => (
              <tr key={run.id}>
                <td>
                  <Link to={`/scraper/runs/${run.id}`}>{run.options.job_title}</Link>
                  {run.options.location ? (
                    <span className="muted"> · {run.options.location}</span>
                  ) : null}
                </td>
                <td>
                  <time dateTime={run.created_at}>{formatDateTime(run.created_at)}</time>
                </td>
                <td>{STATUS_LABEL[run.status]}</td>
                <td>
                  {run.selected_count} of {run.pulled_count}
                </td>
                <td>
                  <button
                    type="button"
                    className="button button-small"
                    disabled={isActive(run.status) || remove.isPending}
                    aria-label={`Delete search for ${run.options.job_title}`}
                    onClick={() => remove.mutate(run.id)}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
