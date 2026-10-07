import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { FileField, TextField, UrlField } from "../../components/fields";
import { ApiError, type FieldErrors } from "../../lib/api";
import { MAX_UPLOAD_BYTES } from "../../lib/config";
import { formatDate } from "../../lib/format";
import { checkUrl, createApplication, trackerKeys, type Application } from "./api";
import {
  isHttpUrl,
  RESUME_ACCEPT,
  SCREENSHOT_ACCEPT,
  validateApplication,
  type ApplicationFormValues,
} from "./validation";

const EMPTY: ApplicationFormValues = {
  job_title: "",
  company_name: "",
  posting_url: "",
  resume: null,
  screenshot: null,
};

/** Object URL for previewing the chosen image. Created and revoked in event handlers. */
function usePreviewUrl(): [string | null, (file: File | null) => void] {
  const [url, setUrl] = useState<string | null>(null);
  const current = useRef<string | null>(null);

  const update = useCallback((file: File | null) => {
    if (current.current) URL.revokeObjectURL(current.current);
    current.current = file ? URL.createObjectURL(file) : null;
    setUrl(current.current);
  }, []);

  useEffect(
    () => () => {
      if (current.current) URL.revokeObjectURL(current.current);
    },
    [],
  );
  return [url, update];
}

/** Form to log an application (TRK-1). */
export function NewApplicationPage() {
  const queryClient = useQueryClient();
  const [values, setValues] = useState<ApplicationFormValues>(EMPTY);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [duplicateOn, setDuplicateOn] = useState<string | null>(null);
  const [saved, setSaved] = useState<Application | null>(null);
  // Changing the key remounts the file inputs, which is the only way to clear them.
  const [fileInputsKey, setFileInputsKey] = useState(0);
  const [previewUrl, setPreview] = usePreviewUrl();

  const mutation = useMutation({
    mutationFn: createApplication,
    onSuccess: async (application) => {
      setSaved(application);
      setValues(EMPTY);
      setErrors({});
      setDuplicateOn(null);
      setFileInputsKey((k) => k + 1);
      setPreview(null);
      await queryClient.invalidateQueries({ queryKey: trackerKeys.all });
    },
    onError: (error) => {
      if (error instanceof ApiError && Object.keys(error.fieldErrors).length > 0) {
        setErrors(error.fieldErrors);
        setFormError(null);
      } else {
        setFormError(error instanceof ApiError ? error.displayMessage : "Couldn't save.");
      }
    },
  });

  function set<K extends keyof ApplicationFormValues>(key: K, value: ApplicationFormValues[K]) {
    setValues((v) => ({ ...v, [key]: value }));
    setErrors(({ [key]: _cleared, ...rest }) => rest);
    setSaved(null);
  }

  async function onUrlBlur() {
    const url = values.posting_url.trim();
    if (!isHttpUrl(url)) {
      setDuplicateOn(null);
      return;
    }
    try {
      const check = await checkUrl(url);
      setDuplicateOn(check.duplicate ? check.previous_created_at : null);
    } catch {
      setDuplicateOn(null); // The warning is a nice-to-have; never block on it.
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    const clientErrors = validateApplication(values, MAX_UPLOAD_BYTES);
    setErrors(clientErrors);
    if (Object.keys(clientErrors).length > 0 || !values.resume) {
      return;
    }
    mutation.mutate({
      job_title: values.job_title.trim(),
      company_name: values.company_name.trim(),
      posting_url: values.posting_url.trim(),
      resume: values.resume,
      screenshot: values.screenshot,
    });
  }

  return (
    <section className="narrow">
      <p>
        <Link to="/tracker">← All applications</Link>
      </p>
      <h1>Log an application</h1>

      {saved ? (
        <div role="status" className="banner banner-success">
          Saved “{saved.job_title}” at {saved.company_name}.{" "}
          <Link to={`/tracker/${saved.id}`}>View it</Link>
        </div>
      ) : null}
      {formError ? (
        <div role="alert" className="banner banner-error">
          {formError}
        </div>
      ) : null}

      <form onSubmit={onSubmit} noValidate>
        <TextField
          label="Job posting title"
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
        <UrlField
          label="Job posting URL"
          required
          value={values.posting_url}
          onChange={(e) => {
            set("posting_url", e.target.value);
            setDuplicateOn(null);
          }}
          onBlur={onUrlBlur}
          error={errors.posting_url}
        />
        {duplicateOn ? (
          <div role="status" className="banner banner-warning">
            You already logged this posting on {formatDate(duplicateOn)}. You can still save it
            again.
          </div>
        ) : null}
        <div key={fileInputsKey}>
          <FileField
            label="Resume used"
            required
            accept={RESUME_ACCEPT}
            hint="PDF or DOCX, up to 10 MB."
            onChange={(e) => set("resume", e.target.files?.[0] ?? null)}
            error={errors.resume}
          />
          <FileField
            label="Screenshot of the posting"
            accept={SCREENSHOT_ACCEPT}
            hint="Optional. PNG, JPEG or WebP, up to 10 MB."
            onChange={(e) => {
              const file = e.target.files?.[0] ?? null;
              set("screenshot", file);
              setPreview(file);
            }}
            error={errors.screenshot}
          />
        </div>
        {previewUrl ? (
          <img className="screenshot-preview" src={previewUrl} alt="Screenshot preview" />
        ) : null}
        <button type="submit" className="button button-primary" disabled={mutation.isPending}>
          {mutation.isPending ? "Saving…" : "Save application"}
        </button>
      </form>
    </section>
  );
}
