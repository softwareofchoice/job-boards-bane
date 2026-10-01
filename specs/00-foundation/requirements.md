# 00 — Foundation: Requirements

> **Source:** "Job Board's Bane is a web application that has sub applications.
> Each sub application serves a function in the job search and application process."
> Also: "local Postgres DB", "Local LLM" (used by both the scraper and Resume Rounder).

The foundation is the shared platform the three sub-apps run on: one web app
shell, one backend, one database, one local LLM client and one file store.

## User stories

### FND-1 — One web app with sub-apps

*As a job seeker, I want one web app that links to each tool, so that my whole
job-search workflow is in one place.*

- **FND-1.1** THE SYSTEM SHALL serve a single web app with navigation to the
  Job Application Tracker, Web Job Scraper and Resume Rounder.
- **FND-1.2** WHEN the user opens the app root THE SYSTEM SHALL show a home
  page that briefly describes each sub-app and links to it.
- **FND-1.3** THE SYSTEM SHALL give each sub-app its own URL path
  (`/tracker`, `/scraper`, `/resume-rounder`) so that it can be bookmarked.
- **FND-1.4** THE SYSTEM SHALL be usable at a viewport width of 1024 px and above.
  **[assumption]**

### FND-2 — Local data storage

*As a job seeker, I want my data stored in a Postgres database on my machine,
so that it stays private and is kept between sessions.*

- **FND-2.1** THE SYSTEM SHALL store all structured data in a local PostgreSQL
  database.
- **FND-2.2** THE SYSTEM SHALL create and update the database schema with
  versioned migrations, applied by one command.
- **FND-2.3** THE SYSTEM SHALL store uploaded and generated files (screenshots,
  resumes, CSVs) on the local filesystem under a configurable data directory,
  and store the file's path and metadata in the database.
- **FND-2.4** IF the database is unreachable at startup THEN THE SYSTEM SHALL
  exit with an error message that names the connection URL it tried (password
  hidden).

### FND-3 — Local LLM access

*As a developer, I want one shared client for the local LLM, so that the
scraper and Resume Rounder call it the same way.*

- **FND-3.1** THE SYSTEM SHALL send all LLM requests to a locally hosted model
  server; no prompts or documents are sent to a third-party LLM API.
- **FND-3.2** THE SYSTEM SHALL read the model server URL and model name from
  configuration.
- **FND-3.3** THE SYSTEM SHALL provide a way to request structured (JSON)
  output that is validated against a schema, retrying up to a configured
  number of times on invalid output.
- **FND-3.4** IF the model server is unreachable or the model is not installed
  THEN THE SYSTEM SHALL return an error that tells the user how to start the
  server or pull the model.
- **FND-3.5** THE SYSTEM SHALL expose a health endpoint that reports whether
  the database and the LLM server are reachable.

### FND-4 — Running and developing locally

*As a developer, I want the whole stack to start with one command, so that
setup is quick and repeatable.*

- **FND-4.1** THE SYSTEM SHALL start Postgres, the backend and the frontend
  with one documented command.
- **FND-4.2** THE SYSTEM SHALL read all settings (database URL, data
  directory, LLM URL and model, upload size limit) from environment variables,
  with a committed `.env.example`.
- **FND-4.3** THE SYSTEM SHALL provide one command each to run linting, type
  checks and tests, and CI SHALL run them on every pull request.

### FND-5 — Consistent errors and validation

- **FND-5.1** WHEN a request fails validation THE SYSTEM SHALL respond with
  HTTP 422 and a field-by-field error list, and the UI SHALL show each error
  next to its field.
- **FND-5.2** WHEN an unexpected error occurs THE SYSTEM SHALL log it with a
  request ID and show the user a generic message that includes that ID.
- **FND-5.3** THE SYSTEM SHALL reject uploads larger than the configured limit
  (default 10 MB) with a clear message. **[assumption]**

## Out of scope

- User accounts and authentication (see open question Q-1).
- Deploying to the cloud or hosting for more than one user.
- Mobile-specific layouts.
