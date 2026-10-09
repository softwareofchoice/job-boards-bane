import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../../lib/api";
import { formatBytes, formatDateTime } from "../../lib/format";
import {
  changeStatus,
  deleteApplication,
  getApplication,
  trackerKeys,
  undoStatusChange,
  type Application,
  type Status,
} from "./api";
import { StatusBadge } from "./StatusBadge";
import { MOVE_LABELS, STATUS_LABELS } from "./status";

/** Current status, the allowed next steps, undo and the history (TRK-4.5, TRK-4.6). */
function StatusPanel({ application }: { application: Application }) {
  const queryClient = useQueryClient();
  const id = application.id;

  async function saved(updated: Application) {
    queryClient.setQueryData(trackerKeys.detail(id), updated);
    await queryClient.invalidateQueries({ queryKey: trackerKeys.all });
  }

  const move = useMutation({
    mutationFn: (status: Status) => changeStatus(id, status),
    onSuccess: saved,
  });
  const undo = useMutation({ mutationFn: () => undoStatusChange(id), onSuccess: saved });

  const busy = move.isPending || undo.isPending;
  const error = move.error ?? undo.error;
  const history = application.status_history;
  const latest = history[history.length - 1];
  const canUndo = history.length > 1;

  return (
    <section className="status-panel" aria-labelledby="status-heading">
      <h2 id="status-heading">
        Status <StatusBadge status={application.status} />
      </h2>
      {application.allowed_next.length > 0 ? (
        <div className="button-row">
          {application.allowed_next.map((next) => (
            <button
              key={next}
              type="button"
              className="button"
              disabled={busy}
              onClick={() => {
                undo.reset();
                move.mutate(next);
              }}
            >
              {MOVE_LABELS[next]}
            </button>
          ))}
        </div>
      ) : (
        <p className="muted">This is a final status.</p>
      )}
      {error ? (
        <p role="alert" className="field-error">
          {error instanceof ApiError ? error.displayMessage : "Couldn't change the status."}
        </p>
      ) : null}
      <ol className="status-history" aria-label="Status history">
        {history.map((change) => (
          <li key={change.changed_at + change.to_status}>
            <strong>{STATUS_LABELS[change.to_status]}</strong>{" "}
            <span className="muted">
              <time dateTime={change.changed_at}>{formatDateTime(change.changed_at)}</time>
            </span>
          </li>
        ))}
      </ol>
      {canUndo && latest ? (
        <button
          type="button"
          className="button button-small"
          disabled={busy}
          onClick={() => {
            move.reset();
            undo.mutate();
          }}
        >
          Undo “{STATUS_LABELS[latest.to_status]}”
        </button>
      ) : null}
    </section>
  );
}

/** One application: all fields, the screenshot and the resume download (TRK-2.4, TRK-3.1). */
export function ApplicationDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);

  const { data, isPending, error } = useQuery({
    queryKey: trackerKeys.detail(id),
    queryFn: () => getApplication(id),
  });

  const remove = useMutation({
    mutationFn: () => deleteApplication(id),
    onSuccess: async () => {
      queryClient.removeQueries({ queryKey: trackerKeys.detail(id) });
      await queryClient.invalidateQueries({ queryKey: trackerKeys.all });
      navigate("/tracker");
    },
  });

  const back = (
    <p>
      <Link to="/tracker">← All applications</Link>
    </p>
  );

  if (isPending) {
    return <p aria-busy="true">Loading…</p>;
  }
  if (error) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <section>
        {back}
        <h1>{notFound ? "Application not found" : "Couldn't load this application"}</h1>
        {!notFound && error instanceof ApiError ? <p>{error.displayMessage}</p> : null}
      </section>
    );
  }

  return (
    <section>
      {back}
      <h1>{data.job_title}</h1>
      <dl className="details">
        <dt>Company</dt>
        <dd>{data.company_name}</dd>
        <dt>Job posting</dt>
        <dd>
          <a href={data.posting_url} target="_blank" rel="noopener noreferrer">
            {data.posting_url}
          </a>
        </dd>
        <dt>Applied</dt>
        <dd>
          <time dateTime={data.created_at}>{formatDateTime(data.created_at)}</time>
        </dd>
        <dt>Resume</dt>
        <dd>
          <a href={data.resume.url} download={data.resume.original_name}>
            Download {data.resume.original_name}
          </a>{" "}
          <span className="muted">({formatBytes(data.resume.size_bytes)})</span>
        </dd>
        <dt>Screenshot</dt>
        <dd>
          {data.screenshot ? (
            <a href={data.screenshot.url} target="_blank" rel="noopener noreferrer">
              <img
                className="screenshot"
                src={data.screenshot.url}
                alt={`Screenshot of the ${data.job_title} posting`}
              />
            </a>
          ) : (
            <span className="muted">None</span>
          )}
        </dd>
      </dl>

      <StatusPanel application={data} />

      <div className="danger-zone">
        {confirming ? (
          <div role="alertdialog" aria-labelledby="confirm-delete" className="confirm">
            <p id="confirm-delete">
              Delete this application and its files? This can&apos;t be undone.
            </p>
            <button
              type="button"
              className="button button-danger"
              disabled={remove.isPending}
              onClick={() => remove.mutate()}
            >
              {remove.isPending ? "Deleting…" : "Yes, delete"}
            </button>
            <button type="button" className="button" onClick={() => setConfirming(false)}>
              Cancel
            </button>
          </div>
        ) : (
          <button
            type="button"
            className="button button-danger"
            onClick={() => setConfirming(true)}
          >
            Delete application
          </button>
        )}
        {remove.isError ? (
          <p role="alert" className="field-error">
            {remove.error instanceof ApiError ? remove.error.displayMessage : "Couldn't delete."}
          </p>
        ) : null}
      </div>
    </section>
  );
}
