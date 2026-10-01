# Project Reqs

## Overview

Job Board's Bane is a web application that has sub applications. Each sub application serves a function in the job search and application process. Below are descriptions of each sub application.

### Job Application Tracker

- Use a form that takes the job posting title, company name, url, screenshot of job posting(optional), and resume used to apply as input and stores in a local Postgres DB in a Applications table
  - Additional fields of created at stored when Job Application submitted

### Web Job Scraper

- Scrape Google for jobs within a specified time frame, title, location, and experience
  - Use a form to take in relevant inputs
  - Inputs include, number of jobs pulled, number of jobs to be selected, days since posting, job title, relevant skills, years of experience, job level
  - search options can be saved as a .yaml file and exported
- Use Local LLM to score the top X jobs against the form inputs, scoring higher for matching the job inputs
- Output into a CSV as well as display in the web app as a list

### Resume Rounder

- As a form, take both a skill name, role, and skill summary for a given skill and store in a database under SKILLS table
- Another form will take a resume to use as a format, and a job posting url or the job posting description as plain text, a job title, and a company name
- Using a Local LLM, swap in the saved skills to match against the skills mentioned in the job posting and generate a new resume. This resume will update the experience section only and work to keep the document at a variable length that can also be taken as an input.
