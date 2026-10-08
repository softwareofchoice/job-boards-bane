import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { TextAreaField, TextField } from "../../components/fields";
import { ApiError, type FieldErrors } from "../../lib/api";
import {
  createSkill,
  deleteSkill,
  listRoles,
  listSkills,
  rounderKeys,
  updateSkill,
  type Skill,
  type SkillInput,
} from "./api";
import { groupByRole, validateSkill } from "./validation";

const EMPTY: SkillInput = { skill_name: "", role: "", summary: "" };

interface Duplicate {
  message: string;
  existing: Skill | undefined;
}

/** The skills library: add, edit and delete skills, grouped by role (RND-1). */
export function SkillsPage() {
  const queryClient = useQueryClient();
  const rolesListId = useId();
  const formRef = useRef<HTMLFormElement>(null);
  const [values, setValues] = useState<SkillInput>(EMPTY);
  const [editing, setEditing] = useState<Skill | null>(null);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [duplicate, setDuplicate] = useState<Duplicate | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  const skills = useQuery({ queryKey: rounderKeys.skills, queryFn: listSkills });
  const roles = useQuery({ queryKey: rounderKeys.roles, queryFn: listRoles });

  function reset() {
    setValues(EMPTY);
    setEditing(null);
    setErrors({});
    setDuplicate(null);
  }

  function startEdit(skill: Skill) {
    reset();
    setEditing(skill);
    setValues({ skill_name: skill.skill_name, role: skill.role, summary: skill.summary });
    setSaved(null);
    formRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }

  const save = useMutation({
    mutationFn: (input: SkillInput) =>
      editing ? updateSkill(editing.id, input) : createSkill(input),
    onSuccess: async (skill) => {
      setSaved(`${editing ? "Updated" : "Saved"} “${skill.skill_name}” for ${skill.role}.`);
      reset();
      await queryClient.invalidateQueries({ queryKey: rounderKeys.all });
    },
    onError: (error) => {
      if (error instanceof ApiError && error.code === "duplicate_skill") {
        const id = error.details.existing_id;
        setDuplicate({
          message: error.message,
          existing: skills.data?.find((s) => s.id === id),
        });
      } else if (error instanceof ApiError && Object.keys(error.fieldErrors).length > 0) {
        setErrors(error.fieldErrors);
      } else {
        setFormError(error instanceof ApiError ? error.displayMessage : "Couldn't save.");
      }
    },
  });

  const remove = useMutation({
    mutationFn: deleteSkill,
    onSuccess: async (_, id) => {
      if (editing?.id === id) reset();
      await queryClient.invalidateQueries({ queryKey: rounderKeys.all });
    },
  });

  function set(key: keyof SkillInput, value: string) {
    setValues((v) => ({ ...v, [key]: value }));
    setErrors(({ [key]: _cleared, ...rest }) => rest);
    setDuplicate(null);
    setSaved(null);
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    const clientErrors = validateSkill(values);
    setErrors(clientErrors);
    if (Object.keys(clientErrors).length > 0) return;
    save.mutate({
      skill_name: values.skill_name.trim(),
      role: values.role.trim(),
      summary: values.summary.trim(),
    });
  }

  const groups = groupByRole(skills.data ?? []);

  return (
    <section>
      <p>
        <Link to="/resume-rounder">← Tailor a resume</Link>
      </p>
      <h1>Your skills</h1>
      <p className="muted">
        Record each skill with the role where you used it and what you did. The role should match a
        job in your resume’s experience section (for example “Software Engineer at Acme”), so the
        skill is written into that job.
      </p>

      <div className="two-column">
        <form ref={formRef} onSubmit={onSubmit} noValidate aria-label="Skill form">
          <h2>{editing ? `Edit “${editing.skill_name}”` : "Add a skill"}</h2>
          {saved ? (
            <div role="status" className="banner banner-success">
              {saved}
            </div>
          ) : null}
          {formError ? (
            <div role="alert" className="banner banner-error">
              {formError}
            </div>
          ) : null}
          {duplicate ? (
            <div role="alert" className="banner banner-warning">
              {duplicate.message}{" "}
              {duplicate.existing ? (
                <button
                  type="button"
                  className="button button-small"
                  onClick={() => startEdit(duplicate.existing!)}
                >
                  Edit existing
                </button>
              ) : null}
            </div>
          ) : null}
          <TextField
            label="Skill name"
            required
            maxLength={100}
            value={values.skill_name}
            onChange={(e) => set("skill_name", e.target.value)}
            error={errors.skill_name}
          />
          <TextField
            label="Role"
            required
            maxLength={200}
            list={rolesListId}
            hint="The job on your resume where you used this skill."
            value={values.role}
            onChange={(e) => set("role", e.target.value)}
            error={errors.role}
          />
          <datalist id={rolesListId}>
            {(roles.data ?? []).map((role) => (
              <option key={role} value={role} />
            ))}
          </datalist>
          <TextAreaField
            label="Skill summary"
            required
            rows={4}
            maxLength={1000}
            hint="What you did with it. Only facts written here can be added to your resume."
            value={values.summary}
            onChange={(e) => set("summary", e.target.value)}
            error={errors.summary}
          />
          <div className="button-row">
            <button type="submit" className="button button-primary" disabled={save.isPending}>
              {save.isPending ? "Saving…" : editing ? "Save changes" : "Add skill"}
            </button>
            {editing ? (
              <button type="button" className="button" onClick={reset}>
                Cancel
              </button>
            ) : null}
          </div>
        </form>

        <div>
          <h2>Saved skills</h2>
          {skills.error ? (
            <p role="alert" className="field-error">
              Couldn't load your skills.
            </p>
          ) : null}
          {skills.data && skills.data.length === 0 ? (
            <p className="empty">No skills yet. Add your first one.</p>
          ) : null}
          {groups.map(([role, items]) => (
            <section key={role} className="skill-group" aria-label={role}>
              <h3>{role}</h3>
              <ul className="skill-list">
                {items.map((skill) => (
                  <li key={skill.id}>
                    <div>
                      <strong>{skill.skill_name}</strong>
                      <p>{skill.summary}</p>
                    </div>
                    <div className="button-row">
                      <button
                        type="button"
                        className="button button-small"
                        aria-label={`Edit ${skill.skill_name} (${skill.role})`}
                        onClick={() => startEdit(skill)}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="button button-small"
                        aria-label={`Delete ${skill.skill_name} (${skill.role})`}
                        disabled={remove.isPending}
                        onClick={() => remove.mutate(skill.id)}
                      >
                        Delete
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </section>
  );
}
