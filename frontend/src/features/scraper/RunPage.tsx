import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../lib/api";
import { formatDate, formatDateTime } from "../../lib/format";
import { csvUrl, getRun, isActive, scraperKeys, type Posting, type RunDetail } from "./api";
import { downloadText, levelLabel, toForm, toYaml, yamlFilename } from "./options";

const STOP_MESSAGES: Record<string, string> = {
  blocked:
    "Google blocked the search (CAPTCHA or rate limit), so collecting stopped early. " +
    "The postings found before that were scored.",
  layout_changed:
    "Google's page didn't look as expected, so collecting stopped early. The scraper may need " +
    "updating (run `make scraper-canary`).",
};

const SUB_SCORE_LABELS: [keyof NonNullable<Posting["sub_scores"]>, string][] = [
  ["title_fit", "Title"],
  ["skills", "Skills"],
  ["experience", "Experience"],
  ["level", "Level"],
  ["location", "Location"],
];

function scoreClass(score: number): string {
  if (score >= 75) return "score score-high";
  if (score >= 50) return "score score-mid";
  return "score score-low";
}

function Progress({ run }: { run: RunDetail }) {
  const { step, done = 0, total = run.options.jobs_pulled } = run.progress;
  const label =
    step === "scoring"
      ? `Scoring ${done} of ${total}`
      : step === "collecting"
        ? `Collecting postings: ${done} of up to ${total}`
        : "Starting…";
  return (
    <div className="run-progress">
      <p role="status">{label}</p>
      <progress max={total || 1} value={step ? done : undefined} aria-label={label} />
    </div>
  );
}

function PostingItem({ posting }: { posting: Posting }) {
  return (
    <li className="posting">
      <details>
        <summary>
          <span className={posting.score !== null ? scoreClass(posting.score) : "score"}>
            {posting.score ?? "–"}
          </span>
          <span className="posting-main">
            <span className="posting-title">
              <a href={posting.url} target="_blank" rel="noopener noreferrer">
                {posting.title}
              </a>
            </span>
            <span className="muted">
              {posting.company}
              {posting.location ? ` · ${posting.location}` : ""}
              {" · "}
              {posting.posted_at ? formatDate(posting.posted_at) : "date unknown"}
              {posting.salary_text ? ` · ${posting.salary_text}` : ""}
            </span>
            {posting.rationale ? <span>{posting.rationale}</span> : null}
            {posting.score_error ? (
              <span className="field-error">Not scored: {posting.score_error}</span>
            ) : null}
            {posting.matched_skills.length > 0 ? (
              <span className="chips" aria-label="Matched skills">
                {posting.matched_skills.map((s) => (
                  <span key={s} className="chip chip-match">
                    {s}
                  </span>
                ))}
              </span>
            ) : null}
          </span>
        </summary>
        <div className="posting-details">
          {posting.sub_scores ? (
            <dl className="sub-scores">
              {SUB_SCORE_LABELS.map(([key, label]) => (
                <div key={key}>
                  <dt>{label}</dt>
                  <dd>{posting.sub_scores![key]}/10</dd>
                </div>
              ))}
            </dl>
          ) : null}
          {posting.missing_skills.length > 0 ? (
            <p>
              <strong>Missing skills:</strong> {posting.missing_skills.join(", ")}
            </p>
          ) : null}
          {posting.via ? <p className="muted">Via {posting.via}</p> : null}
          <div className="description">{posting.description || "No description."}</div>
        </div>
      </details>
    </li>
  );
}

/** A search: live progress while it runs, then the ranked results (SCR-4.5, SCR-5). */
export function RunPage() {
  const { id = "" } = useParams();
  const [showAll, setShowAll] = useState(false);
  const {
    data: run,
    error,
    isPending,
  } = useQuery({
    queryKey: scraperKeys.run(id, showAll),
    queryFn: () => getRun(id, showAll),
    placeholderData: keepPreviousData,
    refetchInterval: (query) =>
      query.state.data && isActive(query.state.data.status) ? 2000 : false,
  });

  const back = (
    <p>
      <Link to="/scraper">← New search</Link>
    </p>
  );
  if (isPending) return <p aria-busy="true">Loading…</p>;
  if (error || !run) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <section>
        {back}
        <h1>{notFound ? "Search not found" : "Couldn't load this search"}</h1>
      </section>
    );
  }

  const opts = run.options;
  const active = isActive(run.status);
  const done = run.status === "succeeded";
  const short = done && run.pulled_count < opts.jobs_pulled;

  return (
    <section>
      {back}
      <div className="page-header">
        <h1>
          {opts.job_title}
          {opts.location ? <span className="muted"> · {opts.location}</span> : null}
        </h1>
        <div className="button-row">
          <Link to="/scraper" state={{ form: toForm(opts) }} className="button">
            Search again
          </Link>
          <button
            type="button"
            className="button"
            onClick={() => downloadText(yamlFilename(opts), toYaml(opts))}
          >
            Export options
          </button>
          {done ? (
            <a className="button button-primary" href={csvUrl(id, showAll)} download>
              Download CSV
            </a>
          ) : null}
        </div>
      </div>
      <p className="muted">
        {levelLabel(opts.job_level)} · {opts.years_experience} years · posted in the last{" "}
        {opts.days_since_posting} days · skills: {opts.skills.join(", ")} · started{" "}
        {formatDateTime(run.created_at)} · model {run.model}
      </p>

      {active ? <Progress run={run} /> : null}
      {run.status === "failed" ? (
        <div role="alert" className="banner banner-error">
          The search failed: {run.error ?? "unknown error"}.
        </div>
      ) : null}
      {run.stopped_reason && STOP_MESSAGES[run.stopped_reason] ? (
        <div role="alert" className="banner banner-warning">
          {STOP_MESSAGES[run.stopped_reason]}
        </div>
      ) : null}
      {short ? (
        <div role="status" className="banner banner-warning">
          Found {run.pulled_count} of the {opts.jobs_pulled} postings asked for.
        </div>
      ) : null}

      {done ? (
        <>
          <div className="results-header">
            <h2>
              {showAll
                ? `All ${run.pulled_count} postings`
                : `Top ${run.selected_count} of ${run.pulled_count}`}
            </h2>
            <label className="toggle">
              <input
                type="checkbox"
                checked={showAll}
                onChange={(e) => setShowAll(e.target.checked)}
              />{" "}
              Show all {run.pulled_count}
            </label>
          </div>
          {run.postings.length === 0 ? (
            <p className="empty">No postings to show.</p>
          ) : (
            <ol className="postings">
              {run.postings.map((p) => (
                <PostingItem key={p.id} posting={p} />
              ))}
            </ol>
          )}
        </>
      ) : null}
    </section>
  );
}
