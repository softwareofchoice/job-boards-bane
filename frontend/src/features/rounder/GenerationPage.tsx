import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import {
  getGeneration,
  isActive,
  rounderKeys,
  type EntryReport,
  type GenerationDetail,
  type GenerationStep,
  type Report,
} from "./api";

const STEPS: [GenerationStep, string][] = [
  ["reading_posting", "Reading the posting"],
  ["finding_skills", "Finding skills"],
  ["rewriting", "Rewriting"],
  ["checking_length", "Checking length"],
];

function Steps({ generation }: { generation: GenerationDetail }) {
  const { step, done, total, attempt, max_attempts } = generation.progress;
  const current = STEPS.findIndex(([key]) => key === step);
  let detail = "";
  if (step === "rewriting" && total) detail = ` (${done ?? 0} of ${total} jobs)`;
  if (step === "checking_length" && attempt) detail = ` (attempt ${attempt} of ${max_attempts})`;
  const label = current >= 0 ? `${STEPS[current]?.[1]}${detail}…` : "Starting…";
  return (
    <div className="run-progress">
      <p role="status">{label}</p>
      <ol className="steps" aria-label="Steps">
        {STEPS.map(([key, text], i) => (
          <li
            key={key}
            className={i < current ? "step-done" : i === current ? "step-current" : undefined}
            aria-current={i === current ? "step" : undefined}
          >
            {text}
          </li>
        ))}
      </ol>
    </div>
  );
}

function Coverage({ report }: { report: Report }) {
  const covered = report.posting_skills.filter((s) => s.covered_by);
  const missing = report.posting_skills.filter((s) => !s.covered_by);
  return (
    <section aria-labelledby="coverage-heading">
      <h2 id="coverage-heading">Posting skills</h2>
      {report.posting_skills.length === 0 ? <p className="empty">No skills found.</p> : null}
      {covered.length > 0 ? (
        <p>
          <strong>Covered by your skills:</strong>{" "}
          <span className="chips" aria-label="Covered skills">
            {covered.map((s) => (
              <span key={s.skill} className="chip chip-match" title={`Matched ${s.covered_by}`}>
                {s.skill}
                {s.covered_by && s.covered_by !== s.skill ? ` (${s.covered_by})` : ""}
              </span>
            ))}
          </span>
        </p>
      ) : null}
      {missing.length > 0 ? (
        <p>
          <strong>Not covered:</strong>{" "}
          <span className="chips" aria-label="Skills not covered">
            {missing.map((s) => (
              <span key={s.skill} className="chip">
                {s.skill}
                {s.kind === "required" ? " (required)" : ""}
              </span>
            ))}
          </span>
        </p>
      ) : null}
      {report.unmatched_roles.length > 0 ? (
        <div role="status" className="banner banner-warning">
          These roles in your skills didn't match a job in your resume, so their skills weren't
          used: {report.unmatched_roles.join(", ")}.{" "}
          <Link to="/resume-rounder/skills">Edit your skills</Link>
        </div>
      ) : null}
    </section>
  );
}

function Entry({ entry }: { entry: EntryReport }) {
  const changed = entry.before.join("\n") !== entry.after.join("\n");
  return (
    <section className="entry" aria-label={entry.header}>
      <h3>{entry.header}</h3>
      {entry.skills_used.length > 0 ? (
        <p className="muted">Skills used: {entry.skills_used.join(", ")}</p>
      ) : null}
      {entry.kept_original_reason ? (
        <p className="muted">Kept as it was: {entry.kept_original_reason}</p>
      ) : null}
      {changed ? (
        <div className="before-after">
          <div>
            <h4>Before</h4>
            <ul>
              {entry.before.map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
          </div>
          <div>
            <h4>After</h4>
            <ul>
              {entry.after.map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
          </div>
        </div>
      ) : (
        <ul>
          {entry.after.map((b, i) => (
            <li key={i}>{b}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** One generated resume: progress while it runs, then the report and downloads (RND-4). */
export function GenerationPage() {
  const { id = "" } = useParams();
  const {
    data: generation,
    error,
    isPending,
  } = useQuery({
    queryKey: rounderKeys.generation(id),
    queryFn: () => getGeneration(id),
    refetchInterval: (query) =>
      query.state.data && isActive(query.state.data.status) ? 2000 : false,
  });

  const back = (
    <p>
      <Link to="/resume-rounder">← Tailor another resume</Link>
    </p>
  );
  if (isPending) return <p aria-busy="true">Loading…</p>;
  if (error || !generation) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <section>
        {back}
        <h1>{notFound ? "Resume not found" : "Couldn't load this resume"}</h1>
      </section>
    );
  }

  const report = generation.report;
  return (
    <section>
      {back}
      <div className="page-header">
        <h1>
          {generation.job_title}
          <span className="muted"> · {generation.company_name}</span>
        </h1>
        <div className="button-row">
          {generation.docx ? (
            <a className="button button-primary" href={generation.docx.url} download>
              Download .docx
            </a>
          ) : null}
          {generation.pdf ? (
            <a className="button" href={generation.pdf.url} download>
              Download PDF
            </a>
          ) : null}
        </div>
      </div>
      <p className="muted">
        Started {formatDateTime(generation.created_at)} · model {generation.model}
        {generation.posting_url ? (
          <>
            {" · "}
            <a href={generation.posting_url} target="_blank" rel="noopener noreferrer">
              posting
            </a>
          </>
        ) : null}
      </p>

      {isActive(generation.status) ? <Steps generation={generation} /> : null}
      {generation.status === "failed" ? (
        <div role="alert" className="banner banner-error">
          Generating the resume failed: {generation.error ?? "unknown error"}
        </div>
      ) : null}

      {report ? (
        <>
          <p role="status" className="pages-summary">
            {report.pages.final.toFixed(1)} pages (target {report.pages.target}, your resume was{" "}
            {report.pages.template.toFixed(1)})
          </p>
          {report.warnings.map((w) => (
            <div key={w} role="alert" className="banner banner-warning">
              {w}
            </div>
          ))}
          <Coverage report={report} />
          <h2>Experience</h2>
          {report.entries.map((entry, i) => (
            <Entry key={i} entry={entry} />
          ))}
        </>
      ) : null}
    </section>
  );
}
