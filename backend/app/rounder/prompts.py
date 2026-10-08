"""Prompt text for the Resume Rounder. Kept together so they're easy to read and tune."""

from collections.abc import Sequence

EXTRACT_SYSTEM = "You read job postings and list the skills they ask for. Reply only with JSON."

PAIR_SYSTEM = (
    "You decide which skill names mean the same thing. Only pair names that are the same skill, "
    "technology or competency under a different name. Reply only with JSON."
)

REWRITE_SYSTEM = (
    "You rewrite resume bullet points. You may only use facts that appear in the ORIGINAL "
    "BULLETS or the SKILL NOTES. Never invent employers, numbers, dates, tools or results. Use "
    "strong past-tense verbs (present tense if the ROLE line shows the job is current). Reply "
    "only with JSON."
)


def extract_skills(posting_text: str) -> str:
    return (
        "List the skills, technologies and competencies this job posting asks for. Separate "
        "required from preferred. Use the posting's own wording, one short name per skill. "
        "Don't include soft skills unless they are stated as requirements.\n\n"
        f"POSTING:\n{posting_text}"
    )


def pair_skills(posting_skills: Sequence[str], saved_skills: Sequence[str]) -> str:
    def bullets(names: Sequence[str]) -> str:
        return "\n".join(f"- {n}" for n in names)

    return (
        "Pair each POSTING SKILL with a SAVED SKILL only when they mean the same thing "
        '(for example "Postgres" and "PostgreSQL"). Leave out anything without a true '
        "match. Use the names exactly as written.\n\n"
        f"POSTING SKILLS:\n{bullets(posting_skills)}\n\n"
        f"SAVED SKILLS:\n{bullets(saved_skills)}"
    )


def rewrite_entry(
    *,
    header: str,
    job_title: str,
    company_name: str,
    wanted: Sequence[str],
    bullets: Sequence[str],
    notes: Sequence[tuple[str, str]],
    n_min: int,
    n_max: int,
    chars_per_bullet: int,
    char_budget: int,
) -> str:
    notes_text = "\n".join(f"- {name}: {summary}" for name, summary in notes) or "- (none)"
    return (
        f"ROLE: {header}\n"
        f"TARGET JOB: {job_title} at {company_name}\n"
        f"SKILLS THE POSTING WANTS (most important first): {', '.join(wanted) or '(none)'}\n\n"
        "ORIGINAL BULLETS:\n" + "\n".join(f"- {b}" for b in bullets) + "\n\n"
        f"SKILL NOTES (from the candidate):\n{notes_text}\n\n"
        f"Write {n_min}-{n_max} bullets, about {chars_per_bullet} characters each, at most "
        f"{char_budget} characters in total. Lead with the skills the posting wants. Keep "
        "strong original bullets that still fit. In skills_used, list the SKILL NOTES names "
        "you used."
    )


def remove_facts(prompt: str, facts: Sequence[str]) -> str:
    return (
        f"{prompt}\n\nYOUR LAST ANSWER added things that aren't in the original bullets or "
        f"the skill notes: {', '.join(facts)}. Write the bullets again without them."
    )
