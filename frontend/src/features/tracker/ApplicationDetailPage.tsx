import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../../lib/api";
import { formatBytes, formatDateTime } from "../../lib/format";
import { deleteApplication, getApplication, trackerKeys } from "./api";

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
