import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { useDebouncedValue } from "../../lib/useDebouncedValue";
import { listApplications, trackerKeys } from "./api";

/** All logged applications, newest first, with search and pagination (TRK-2.1 to TRK-2.3). */
export function ApplicationListPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const q = useDebouncedValue(search.trim(), 300);

  const { data, isPending, isError, error, isPlaceholderData } = useQuery({
    queryKey: trackerKeys.list(q, page),
    queryFn: () => listApplications(q, page),
    placeholderData: keepPreviousData,
  });

  const pageCount = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <section>
      <div className="page-header">
        <h1>Job Application Tracker</h1>
        <Link to="/tracker/new" className="button button-primary">
          Log application
        </Link>
      </div>

      <div className="field search-field">
        <label htmlFor="tracker-search">Search by title or company</label>
        <input
          id="tracker-search"
          type="search"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
        />
      </div>

      {isPending ? <p aria-busy="true">Loading…</p> : null}
      {isError ? (
        <div role="alert" className="banner banner-error">
          {error instanceof ApiError ? error.displayMessage : "Couldn't load applications."}
        </div>
      ) : null}

      {data && data.items.length === 0 ? (
        <p className="empty">
          {q ? (
            <>No applications match “{q}”.</>
          ) : (
            <>
              No applications yet. <Link to="/tracker/new">Log your first one.</Link>
            </>
          )}
        </p>
      ) : null}

      {data && data.items.length > 0 ? (
        <>
          <table className="table" aria-busy={isPlaceholderData}>
            <thead>
              <tr>
                <th scope="col">Job title</th>
                <th scope="col">Company</th>
                <th scope="col">Posting</th>
                <th scope="col">Applied</th>
                <th scope="col">Screenshot</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((a) => (
                <tr key={a.id}>
                  <td>
                    <Link to={`/tracker/${a.id}`}>{a.job_title}</Link>
                  </td>
                  <td>{a.company_name}</td>
                  <td>
                    <a href={a.posting_url} target="_blank" rel="noopener noreferrer">
                      Open posting
                    </a>
                  </td>
                  <td>
                    <time dateTime={a.created_at}>{formatDateTime(a.created_at)}</time>
                  </td>
                  <td>{a.screenshot ? "Yes" : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <nav className="pagination" aria-label="Pagination">
            <button
              type="button"
              className="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </button>
            <span>
              Page {page} of {pageCount} · {data.total} application{data.total === 1 ? "" : "s"}
            </span>
            <button
              type="button"
              className="button"
              disabled={page >= pageCount}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </nav>
        </>
      ) : null}
    </section>
  );
}
