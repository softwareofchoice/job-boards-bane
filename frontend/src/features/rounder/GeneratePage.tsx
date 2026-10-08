import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  FileField,
  SelectField,
  TextAreaField,
  TextField,
  UrlField,
} from "../../components/fields";
import { ApiError, type FieldErrors } from "../../lib/api";
import {
  listSkills,
  preflight,
  rounderKeys,
  startGeneration,
  TARGET_OPTIONS,
  type GenerationRequest,
  type Heading,
  type Preflight,
} from "./api";
import { PastGenerations } from "./PastGenerations";
import { MAX_POSTING, TEMPLATE_ACCEPT, validateGenerate, type FormValues } from "./validation";

const EMPTY: FormValues = {
  template: null,
  mode: "text",
  posting_url: "",
  posting_text: "",
  job_title: "",
  company_name: "",
};

function toTarget(value: string): string {
  return String(Number(value));
}

function PreflightSummary({ result }: { result: Preflight }) {
  const roles = result.experience_entries.length;
  return (
    <div role="status" className="banner banner-success">
      {result.experience_found
        ? `Found ${roles} ${roles === 1 ? "role" : "roles"} in your experience section. `
        : null}
      Your resume is {result.template_pages.toFixed(1)} pages; the posting has{" "}
      {result.posting_chars.toLocaleString()} characters.
    </div>
  );
}

/** The generate form: check the inputs first (preflight), then start (RND-2). */
export function GeneratePage() {
  const navigate = useNavigate();
  const [values, setValues] = useState<FormValues>(EMPTY);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [checked, setChecked] = useState<Preflight | null>(null);
  const [target, setTarget] = useState("");
  const [headingIdx, setHeadingIdx] = useState("");
  // Set when the experience section wasn't found: the headings to choose from (RND-2.5).
  const [headingChoices, setHeadingChoices] = useState<Heading[] | null>(null);

  const skills = useQuery({ queryKey: rounderKeys.skills, queryFn: listSkills });
  const noSkills = skills.data !== undefined && skills.data.length === 0;

  function request(): GenerationRequest {
    return {
      template: values.template!,
      job_title: values.job_title.trim(),
      company_name: values.company_name.trim(),
      posting_url: values.mode === "url" ? values.posting_url.trim() : "",
      posting_text: values.mode === "text" ? values.posting_text.trim() : "",
      experience_heading_idx: headingIdx === "" ? null : Number(headingIdx),
    };
  }

  function onError(error: Error) {
    if (error instanceof ApiError && Object.keys(error.fieldErrors).length > 0) {
      setErrors(error.fieldErrors);
    } else {
      setFormError(error instanceof ApiError ? error.displayMessage : "Something went wrong.");
    }
  }

  const check = useMutation({
    mutationFn: preflight,
    onSuccess: (result) => {
      setChecked(result);
      setTarget(toTarget(result.suggested_target));
      if (!result.experience_found) setHeadingChoices(result.headings);
    },
    onError,
  });

  const start = useMutation({
    mutationFn: startGeneration,
    onSuccess: ({ generation_id }) => navigate(`/resume-rounder/generations/${generation_id}`),
    onError,
  });

  function set<K extends keyof FormValues>(key: K, value: FormValues[K]) {
    setValues((v) => ({ ...v, [key]: value }));
    setErrors(({ [key]: _a, posting: _b, ...rest }) => rest);
    setChecked(null);
    if (key === "template") {
      setHeadingIdx("");
      setHeadingChoices(null);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    const clientErrors = validateGenerate(values);
    setErrors(clientErrors);
    if (Object.keys(clientErrors).length > 0) return;
    if (checked?.experience_found) {
      start.mutate({ ...request(), target_pages: target });
    } else {
      check.mutate(request());
    }
  }

  const needsHeading = checked !== null && !checked.experience_found;
  const ready = checked !== null && !needsHeading;
  const busy = check.isPending || start.isPending;

  return (
    <section>
      <div className="page-header">
        <h1>Resume Rounder</h1>
        <Link to="/resume-rounder/skills" className="button">
          Your skills{skills.data ? ` (${skills.data.length})` : ""}
        </Link>
      </div>
      <p className="muted">
        Tailor your resume to a job posting. Only the bullet points in your experience section are
        rewritten, using your saved skills; everything else stays exactly as it is.
      </p>

      {noSkills ? (
        <div role="alert" className="banner banner-warning">
          Add your skills before generating a resume.{" "}
          <Link to="/resume-rounder/skills">Add skills</Link>
        </div>
      ) : null}
      {formError ? (
        <div role="alert" className="banner banner-error">
          {formError}
        </div>
      ) : null}

      <form className="narrow" onSubmit={onSubmit} noValidate aria-label="Generate a resume">
        <FileField
          label="Your resume"
          required
          accept={TEMPLATE_ACCEPT}
          hint="A Word (.docx) file, used as the format for the new resume."
          onChange={(e) => set("template", e.target.files?.[0] ?? null)}
          error={errors.template}
        />
        <fieldset className="choice-group">
          <legend>Job posting</legend>
          <label className="toggle">
            <input
              type="radio"
              name="posting-mode"
              checked={values.mode === "text"}
              onChange={() => set("mode", "text")}
            />{" "}
            Paste the description
          </label>{" "}
          <label className="toggle">
            <input
              type="radio"
              name="posting-mode"
              checked={values.mode === "url"}
              onChange={() => set("mode", "url")}
            />{" "}
            Use its web address
          </label>
          {errors.posting ? (
            <p className="field-error" role="alert">
              {errors.posting}
            </p>
          ) : null}
        </fieldset>
        {values.mode === "url" ? (
          <UrlField
            label="Job posting URL"
            required
            value={values.posting_url}
            onChange={(e) => set("posting_url", e.target.value)}
            error={errors.posting_url}
          />
        ) : (
          <TextAreaField
            label="Job description"
            required
            rows={8}
            maxLength={MAX_POSTING}
            value={values.posting_text}
            onChange={(e) => set("posting_text", e.target.value)}
            error={errors.posting_text}
          />
        )}
        <TextField
          label="Job title"
          required
          maxLength={200}
          value={values.job_title}
          onChange={(e) => set("job_title", e.target.value)}
          error={errors.job_title}
        />
        <TextField
          label="Company name"
          required
          maxLength={200}
          value={values.company_name}
          onChange={(e) => set("company_name", e.target.value)}
          error={errors.company_name}
        />

        {checked ? <PreflightSummary result={checked} /> : null}
        {checked?.warnings.map((w) => (
          <div key={w} role="status" className="banner banner-warning">
            {w}
          </div>
        ))}
        {headingChoices ? (
          <>
            {needsHeading ? (
              <div role="alert" className="banner banner-warning">
                Couldn't find the experience section in your resume. Choose the heading it starts
                with.
              </div>
            ) : null}
            <SelectField
              label="Experience section heading"
              required
              placeholder="Choose a heading"
              options={headingChoices.map((h) => [String(h.index), h.text] as const)}
              value={headingIdx}
              onChange={(e) => {
                setHeadingIdx(e.target.value);
                setChecked(null);
              }}
              error={errors.experience_heading_idx}
            />
          </>
        ) : null}
        {ready ? (
          <SelectField
            label="Target length"
            required
            options={TARGET_OPTIONS}
            value={target}
            hint="Defaults to your resume's current length."
            onChange={(e) => setTarget(e.target.value)}
            error={errors.target_pages}
          />
        ) : null}

        <button
          type="submit"
          className="button button-primary"
          disabled={busy || noSkills || (headingChoices !== null && headingIdx === "")}
        >
          {check.isPending
            ? "Checking…"
            : start.isPending
              ? "Starting…"
              : ready
                ? "Generate resume"
                : "Check resume"}
        </button>
      </form>

      <PastGenerations />
    </section>
  );
}
