# 03 — Resume Rounder: Requirements

> **Source (`REQUIREMENTS.md`):**
> "As a form, take both a skill name, role, and skill summary for a given skill and
> store in a database under SKILLS table
> Another form will take a resume to use as a format, and a job posting url or the
> job posting description as plain text, a job title, and a company name
> Using a Local LLM, swap in the saved skills to match against the skills mentioned
> in the job posting and generate a new resume. This resume will update the
> experience section only and work to keep the document at a variable length that
> can also be taken as an input."

## Terms

- **Skill entry:** one row in `SKILLS`: a skill name, the role it was used in,
  and a summary of what was done with it.
- **Role:** a position on the resume (e.g. "Software Engineer at Acme").
  Linking skills to roles is what decides *where* in the experience section a
  skill is written. **[assumption, Q-7]**
- **Template resume:** the user's existing `.docx` resume, used for layout and
  for everything outside the experience section. **[assumption, Q-8]**

## User stories

### RND-1 — Build a skills library

*As a job seeker, I want to record my skills with the role where I used them
and a summary of what I did, so that they can be put into tailored resumes.*

- **RND-1.1** THE SYSTEM SHALL provide a form with: skill name (required,
  1–100 characters), role (required, 1–200 characters, suggested from roles
  already entered), skill summary (required, 1–1000 characters).
- **RND-1.2** WHEN the form is submitted with valid values THE SYSTEM SHALL
  save the entry in the `skills` table with a `created_at` time.
- **RND-1.3** IF an entry with the same skill name and role (ignoring case)
  already exists THEN THE SYSTEM SHALL refuse it and offer to edit the
  existing entry.
- **RND-1.4** THE SYSTEM SHALL list saved skills grouped by role, and let the
  user edit and delete them. **[assumption]**

### RND-2 — Request a tailored resume

*As a job seeker, I want to give a resume, a job posting, the job title, the
company and a target length, so that I get a resume tailored to that job.*

- **RND-2.1** THE SYSTEM SHALL provide a form with:
  | Field                    | Required | Rules                                                                 |
  | ------------------------ | -------- | --------------------------------------------------------------------- |
  | Template resume          | Yes      | `.docx`, within the upload size limit                                 |
  | Job posting URL **or** job posting text | Exactly one | URL: `http`/`https`. Text: 200–20,000 characters               |
  | Job title                | Yes      | 1–200 characters                                                      |
  | Company name             | Yes      | 1–200 characters                                                      |
  | Target length            | Yes      | Pages: 1, 1.5, 2, or 3; defaults to the template's current page count **[assumption, Q-9]** |
- **RND-2.2** IF both or neither of the URL and text are given THEN THE SYSTEM
  SHALL reject the form with "Provide a job posting URL or paste the description".
- **RND-2.3** WHEN a URL is given THE SYSTEM SHALL download the page and pull
  out the posting's text.
- **RND-2.4** IF the posting can't be downloaded or has too little text (less
  than 200 characters) THEN THE SYSTEM SHALL ask the user to paste the
  description instead.
- **RND-2.5** IF the template has no experience section the system can find
  THEN THE SYSTEM SHALL say so before doing any LLM work, and let the user
  choose which heading is the experience section.
- **RND-2.6** IF no saved skills exist THEN THE SYSTEM SHALL disable
  generation and link to the skills form.

### RND-3 — Generate the resume with the local LLM

- **RND-3.1** THE SYSTEM SHALL use the local LLM to list the skills the job
  posting asks for.
- **RND-3.2** THE SYSTEM SHALL match the posting's skills against the saved
  skill entries, including synonyms (e.g. "Postgres" ↔ "PostgreSQL").
- **RND-3.3** THE SYSTEM SHALL match each saved role to an entry in the
  template's experience section, and show any role it couldn't match.
- **RND-3.4** THE SYSTEM SHALL rewrite the bullet points of each experience
  entry using that entry's original bullets and the summaries of matched skills
  for that role, giving more space to skills the posting asks for.
- **RND-3.5** THE SYSTEM SHALL NOT change anything outside the experience
  section: name, contact details, summary, education, other sections, and the
  role titles, company names and dates inside the experience section all stay
  exactly as in the template.
- **RND-3.6** THE SYSTEM SHALL keep the template's formatting (fonts, sizes,
  bullet style, spacing, margins) in the generated resume.
- **RND-3.7** THE SYSTEM SHALL NOT add employers, roles, dates, numbers, or
  skills that aren't in the template or the user's saved skill entries.
- **RND-3.8** THE SYSTEM SHALL make the generated resume no longer than the
  target length. WHERE the result is more than half a page shorter than the
  target THE SYSTEM SHALL say so but still produce it.
- **RND-3.9** IF the length can't be met after the allowed shortening
  attempts THEN THE SYSTEM SHALL return the closest attempt and say by how
  much it's over.

### RND-4 — Review and download

- **RND-4.1** WHILE generation is running THE SYSTEM SHALL show the current
  step (reading posting / finding skills / rewriting / checking length).
- **RND-4.2** WHEN generation finishes THE SYSTEM SHALL show: the posting's
  skills marked as covered or not covered by saved skills, which saved skills
  were used and where, a before/after view of each experience entry, and the
  final page count.
- **RND-4.3** THE SYSTEM SHALL offer the generated resume as `.docx` and as PDF.
- **RND-4.4** THE SYSTEM SHALL save each generated resume with its inputs and
  list past generations so they can be downloaded again.

## Out of scope (v1)

- PDF template resumes (Q-8).
- Rewriting sections other than experience (summary, skills list).
- Editing the result in the app before download.
- Cover letters.
- Logging the generated resume in the Tracker automatically (Q-10).
