/**
 * Shared form fields. Each shows its error (client- or server-side) under the input and
 * links it with `aria-describedby` (FND-5.1).
 */
import {
  useId,
  useState,
  type InputHTMLAttributes,
  type KeyboardEvent,
  type ReactNode,
  type SelectHTMLAttributes,
} from "react";

interface FieldShellProps {
  id: string;
  label: string;
  required?: boolean;
  error?: string;
  hint?: ReactNode;
  children: ReactNode;
}

function FieldShell({ id, label, required, error, hint, children }: FieldShellProps) {
  return (
    <div className={`field${error ? " field-invalid" : ""}`}>
      <label htmlFor={id}>
        {label}
        {required ? <span aria-hidden="true"> *</span> : null}
      </label>
      {children}
      {hint && !error ? (
        <p id={`${id}-hint`} className="field-hint">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={`${id}-error`} className="field-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

type InputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "id" | "type"> & {
  label: string;
  error?: string;
  hint?: ReactNode;
};

function useFieldIds(error?: string, hint?: ReactNode) {
  const id = useId();
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return { id, describedBy };
}

function Input({ label, error, hint, type, ...rest }: InputProps & { type: string }) {
  const { id, describedBy } = useFieldIds(error, hint);
  return (
    <FieldShell id={id} label={label} required={rest.required} error={error} hint={hint}>
      <input
        id={id}
        type={type}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        {...rest}
      />
    </FieldShell>
  );
}

export function TextField(props: InputProps) {
  return <Input type="text" {...props} />;
}

export function UrlField(props: InputProps) {
  return <Input type="url" inputMode="url" placeholder="https://" {...props} />;
}

export function NumberField(props: InputProps) {
  return <Input type="number" inputMode="numeric" {...props} />;
}

export function FileField(props: InputProps) {
  return <Input type="file" {...props} />;
}

type SelectProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, "id"> & {
  label: string;
  error?: string;
  hint?: ReactNode;
  options: readonly (readonly [string, string])[];
  placeholder?: string;
};

export function SelectField({ label, error, hint, options, placeholder, ...rest }: SelectProps) {
  const { id, describedBy } = useFieldIds(error, hint);
  return (
    <FieldShell id={id} label={label} required={rest.required} error={error} hint={hint}>
      <select
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        {...rest}
      >
        {placeholder !== undefined ? <option value="">{placeholder}</option> : null}
        {options.map(([value, text]) => (
          <option key={value} value={value}>
            {text}
          </option>
        ))}
      </select>
    </FieldShell>
  );
}

interface TagInputProps {
  label: string;
  value: string[];
  onChange: (tags: string[]) => void;
  error?: string;
  hint?: ReactNode;
  required?: boolean;
  maxTags?: number;
  placeholder?: string;
}

/** Free-text tags: Enter or comma adds one, Backspace on an empty input removes the last. */
export function TagInput({
  label,
  value,
  onChange,
  error,
  hint,
  required,
  maxTags,
  placeholder = "Type and press Enter",
}: TagInputProps) {
  const { id, describedBy } = useFieldIds(error, hint);
  const [draft, setDraft] = useState("");
  const full = maxTags !== undefined && value.length >= maxTags;

  function add(raw: string) {
    const tag = raw.trim();
    const exists = value.some((t) => t.toLowerCase() === tag.toLowerCase());
    if (tag && !exists && !full) {
      onChange([...value, tag]);
    }
    setDraft("");
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      add(draft);
    } else if (e.key === "Backspace" && draft === "" && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  }

  return (
    <FieldShell id={id} label={label} required={required} error={error} hint={hint}>
      <div className="tag-input">
        <ul aria-label={`${label} tags`}>
          {value.map((tag) => (
            <li key={tag} className="tag">
              {tag}
              <button
                type="button"
                aria-label={`Remove ${tag}`}
                onClick={() => onChange(value.filter((t) => t !== tag))}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
        <input
          id={id}
          type="text"
          value={draft}
          disabled={full}
          placeholder={full ? `Limit of ${maxTags} reached` : placeholder}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          onBlur={() => add(draft)}
        />
      </div>
    </FieldShell>
  );
}
