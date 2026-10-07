export interface SubApp {
  path: string;
  name: string;
  summary: string;
  needsLlm: boolean;
}

/** The three sub-applications, in navigation order (FND-1.1, FND-1.3). */
export const SUB_APPS: SubApp[] = [
  {
    path: "/tracker",
    name: "Job Application Tracker",
    summary: "Log every job you apply for, with the posting and the resume you sent.",
    needsLlm: false,
  },
  {
    path: "/scraper",
    name: "Web Job Scraper",
    summary:
      "Search for recent postings that fit your title, skills and level, then rank them with the local LLM.",
    needsLlm: true,
  },
  {
    path: "/resume-rounder",
    name: "Resume Rounder",
    summary:
      "Keep a library of your skills and generate a resume whose experience section is tailored to a posting.",
    needsLlm: true,
  },
];
