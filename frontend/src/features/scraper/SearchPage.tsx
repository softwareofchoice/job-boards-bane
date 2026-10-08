import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { NumberField, SelectField, TagInput, TextField } from "../../components/fields";
import { ApiError, type FieldErrors } from "../../lib/api";
import { scraperKeys, startRun } from "./api";
import { PastRuns } from "./PastRuns";
import {
  downloadText,
  EMPTY_FORM,
  fromYaml,
  JOB_LEVELS,
  toYaml,
  validateForm,
  yamlFilename,
  type SearchForm,
  type SearchOptions,
} from "./options";

interface ImportNotice {
  kind: "error" | "info";
  lines: string[];
}

/** The search form (SCR-1) with YAML import and export (SCR-2), and past searches (SCR-5.5). */
export function SearchPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  // "Search again" on a run page passes that run's options here.
  const initial = (useLocation().state as { form?: SearchForm } | null)?.form ?? EMPTY_FORM;
  const [form, setForm] = useState<SearchForm>(initial);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<ImportNotice | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const run = useMutation({
    mutationFn: startRun,
    onSuccess: async ({ run_id }) => {
      await queryClient.invalidateQueries({ queryKey: scraperKeys.runs });
      navigate(`/scraper/runs/${run_id}`);
    },
    onError: (error) => {
      if (error instanceof ApiError && Object.keys(error.fieldErrors).length > 0) {
        setErrors(error.fieldErrors);
      } else {
        setFormError(
          error instanceof ApiError ? error.displayMessage : "Couldn't start the search.",
        );
      }
    },
  });

  function set<K extends keyof SearchForm>(key: K, value: SearchForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
    setErrors(({ [key]: _cleared, ...rest }) => rest);
  }

  function checked(): SearchOptions | null {
    const result = validateForm(form);
    setErrors(result.errors ?? {});
    return result.options;
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    const options = checked();
    if (options) run.mutate(options);
  }

  function onExport() {
    const options = checked();
    if (options) {
      downloadText(yamlFilename(options), toYaml(options));
      setNotice(null);
    }
  }

  async function onImport(file: File | undefined) {
    if (!file) return;
    const result = fromYaml(await file.text());
    if (fileInput.current) fileInput.current.value = "";
    if (!result.ok) {
      setNotice({ kind: "error", lines: [`Couldn't load ${file.name}:`, ...result.problems] });
      return;
    }
    setForm(result.form);
    setErrors({});
    setNotice({
      kind: "info",
      lines: [
        `Loaded ${file.name}.`,
        ...(result.ignoredKeys.length > 0
          ? [`Ignored unknown keys: ${result.ignoredKeys.join(", ")}.`]
          : []),
      ],
    });
  }

  return (
    <section>
      <div className="page-header">
        <h1>Web Job Scraper</h1>
        <div className="button-row">
          <button type="button" className="button" onClick={() => fileInput.current?.click()}>
            Import YAML
          </button>
          <button type="button" className="button" onClick={onExport}>
            Export YAML
          </button>
          <input
            ref={fileInput}
            type="file"
            accept=".yaml,.yml,application/yaml,text/yaml"
            hidden
            data-testid="yaml-input"
            onChange={(e) => void onImport(e.target.files?.[0])}
          />
        </div>
      </div>
      <p className="lead">
        Find recent postings, then let the local LLM score them against what you&apos;re looking
        for.
      </p>

      {notice ? (
        <div
          role={notice.kind === "error" ? "alert" : "status"}
          className={`banner ${notice.kind === "error" ? "banner-error" : "banner-success"}`}
        >
          {notice.lines.map((line) => (
            <div key={line}>{line}</div>
          ))}
        </div>
      ) : null}
      {formError ? (
        <div role="alert" className="banner banner-error">
          {formError}
        </div>
      ) : null}

      <form onSubmit={onSubmit} noValidate className="form-grid">
        <TextField
          label="Job title"
          required
          maxLength={200}
          value={form.job_title}
          onChange={(e) => set("job_title", e.target.value)}
          error={errors.job_title}
        />
        <TextField
          label="Location"
          maxLength={200}
          hint="Optional, e.g. “Austin, TX” or “Remote”."
          value={form.location}
          onChange={(e) => set("location", e.target.value)}
          error={errors.location}
        />
        <SelectField
          label="Job level"
          required
          options={JOB_LEVELS}
          placeholder="Choose…"
          value={form.job_level}
          onChange={(e) => set("job_level", e.target.value as SearchForm["job_level"])}
          error={errors.job_level}
        />
        <NumberField
          label="Years of experience"
          required
          min={0}
          max={50}
          value={form.years_experience}
          onChange={(e) => set("years_experience", e.target.value)}
          error={errors.years_experience}
        />
        <div className="span-2">
          <TagInput
            label="Relevant skills"
            required
            maxTags={30}
            value={form.skills}
            onChange={(skills) => set("skills", skills)}
            error={errors.skills}
            hint="Press Enter or comma after each skill."
          />
        </div>
        <NumberField
          label="Days since posting"
          required
          min={1}
          max={60}
          value={form.days_since_posting}
          onChange={(e) => set("days_since_posting", e.target.value)}
          error={errors.days_since_posting}
        />
        <div />
        <NumberField
          label="Number of jobs pulled"
          required
          min={1}
          max={100}
          hint="How many postings to collect and score (up to 100)."
          value={form.jobs_pulled}
          onChange={(e) => set("jobs_pulled", e.target.value)}
          error={errors.jobs_pulled}
        />
        <NumberField
          label="Number of jobs selected"
          required
          min={1}
          max={100}
          hint="How many of the best-scoring postings to keep."
          value={form.jobs_selected}
          onChange={(e) => set("jobs_selected", e.target.value)}
          error={errors.jobs_selected ?? errors._form}
        />
        <div className="span-2">
          <button type="submit" className="button button-primary" disabled={run.isPending}>
            {run.isPending ? "Starting…" : "Run search"}
          </button>
        </div>
      </form>

      <PastRuns />
    </section>
  );
}
