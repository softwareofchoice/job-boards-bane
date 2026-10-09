# 01 — Job Application Tracker: Requirements

> **Source (`REQUIREMENTS.md`):**
> "Use a form that takes the job posting title, company name, url, screenshot of
> job posting(optional), and resume used to apply as input and stores in a local
> Postgres DB in a Applications table
> — Additional fields of created at stored when Job Application submitted"

## User stories

### TRK-1 — Log an application

*As a job seeker, I want to record each job I apply for with the resume I
used, so that I have a reliable history of my applications.*

- **TRK-1.1** THE SYSTEM SHALL provide a form with these fields:
  | Field              | Required | Rules                                                              |
  | ------------------ | -------- | ------------------------------------------------------------------ |
  | Job posting title  | Yes      | 1–200 characters, leading/trailing spaces removed                  |
  | Company name       | Yes      | 1–200 characters, leading/trailing spaces removed                  |
  | Job posting URL    | Yes      | Valid `http`/`https` URL, ≤ 2048 characters                        |
  | Screenshot         | No       | PNG, JPEG or WebP image, within the upload size limit              |
  | Resume used        | Yes      | PDF or DOCX file, within the upload size limit **[assumption, Q-2]** |
- **TRK-1.2** WHEN the user submits a valid form THE SYSTEM SHALL save one row
  in the `applications` table and store the uploaded files.
- **TRK-1.3** WHEN an application is saved THE SYSTEM SHALL set its
  `created_at` to the server's current time in UTC; the user can't set it.
- **TRK-1.4** IF a required field is missing or invalid THEN THE SYSTEM SHALL
  save nothing and show an error next to each invalid field, keeping what the
  user already entered.
- **TRK-1.5** IF saving the files or the row fails part-way THEN THE SYSTEM
  SHALL leave no partial row and no orphaned files.
- **TRK-1.6** WHEN an application is saved THE SYSTEM SHALL confirm it and
  clear the form, ready for the next entry.
- **TRK-1.7** WHERE the URL matches an application saved before THE SYSTEM
  SHALL warn "You already logged this posting on <date>" but still allow the
  save. **[assumption]**

### TRK-2 — View my applications

*As a job seeker, I want to see the applications I've logged, so that I can
check where I've applied.* **[assumption, Q-3]** — `REQUIREMENTS.md` only
describes storing; a list is needed to make the stored data usable.

- **TRK-2.1** THE SYSTEM SHALL list applications newest first, showing title,
  company, a link to the posting, the date applied (`created_at`), and whether
  a screenshot is attached.
- **TRK-2.2** THE SYSTEM SHALL let the user filter the list by text in the
  title or company name.
- **TRK-2.3** THE SYSTEM SHALL show 25 applications per page with pagination.
- **TRK-2.4** WHEN the user opens an application THE SYSTEM SHALL show all its
  fields, display the screenshot, and offer the resume for download.

### TRK-3 — Delete an application **[assumption, Q-3]**

- **TRK-3.1** WHEN the user deletes an application and confirms THE SYSTEM
  SHALL remove its row and its files.

### TRK-4 — Track each application's status

*As a job seeker, I want to record how each application is going, so that I
know where I stand with every company.*

> **Source:** added on request after v1: "Update job tracker to track status of
> job. Status should flow from applied to interviewing to rejected or offer.
> Applied can also flow to rejected. The change of status should be tracked."

- **TRK-4.1** WHEN an application is saved THE SYSTEM SHALL give it the status
  **Applied**, dated with its `created_at`.
- **TRK-4.2** THE SYSTEM SHALL allow only these status changes:
  | From         | To                       |
  | ------------ | ------------------------ |
  | Applied      | Interviewing, Rejected   |
  | Interviewing | Offer, Rejected          |

  Offer and Rejected are final.
- **TRK-4.3** IF the user asks for any other change THEN THE SYSTEM SHALL
  refuse it, say which changes are allowed from the current status, and leave
  the status as it was.
- **TRK-4.4** WHEN the status changes THE SYSTEM SHALL record the old status,
  the new status and the server's current time (UTC), keeping every earlier
  change.
- **TRK-4.5** THE SYSTEM SHALL show an application's current status and its
  full history of changes on its page, with a button for each allowed next
  status.
- **TRK-4.6** IF the user made a mistake THEN THE SYSTEM SHALL let them undo
  the most recent change, which removes it from the history. The initial
  Applied can't be undone. **[assumption]**
- **TRK-4.7** THE SYSTEM SHALL show each application's status in the list and
  let the user filter the list by status.

### TRK-5 — See how applications flow between statuses

> **Source:** "...can be visualized in a parallel plot".

- **TRK-5.1** THE SYSTEM SHALL show a parallel sets plot (the parallel
  coordinates plot for categories) with one axis per stage: *Applied*, *After
  applying* (Interviewing, Rejected, or No response yet) and *Outcome* (Offer,
  Rejected, Still interviewing, or No response yet). Each application is one
  path across the axes; paths with the same statuses are drawn as one ribbon
  whose width is their count.
- **TRK-5.2** THE SYSTEM SHALL colour ribbons by where the application ended
  up (Offer, Rejected, still open), with a legend and the categories labelled
  on the axes, so colour is never the only cue.
- **TRK-5.3** WHEN the user hovers over or focuses a ribbon THE SYSTEM SHALL
  show its path and count, and THE SYSTEM SHALL also offer the same numbers
  as a table.
- **TRK-5.4** WHEN the user changes the status filter or search THE SYSTEM
  SHALL keep the plot showing all applications. **[assumption]**

## Out of scope (v1)

- Editing an application after it's saved.
- Notes on an application, and statuses beyond the four in TRK-4 (e.g.
  "withdrawn", "ghosted").
- Back-dating a status change (it's always recorded at the time it's made).
- Taking the screenshot automatically from the URL.
- Choosing a resume generated by Resume Rounder instead of uploading one (Q-10).
- Importing jobs from the Web Job Scraper (Q-10).
