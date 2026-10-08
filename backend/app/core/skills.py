"""Skill-name matching shared by the scraper (spec 02) and Resume Rounder (spec 03)."""

import re

# Groups of names that mean the same skill. Matching is case-insensitive and ignores
# punctuation, so only genuinely different spellings need listing here.
ALIAS_GROUPS: list[set[str]] = [
    {"postgres", "postgresql", "psql"},
    {"javascript", "js", "ecmascript"},
    {"typescript", "ts"},
    {"kubernetes", "k8s"},
    {"golang", "go"},
    {"python", "python3", "py"},
    {"amazon web services", "aws"},
    {"google cloud", "google cloud platform", "gcp"},
    {"microsoft azure", "azure"},
    {"react", "reactjs", "react js"},
    {"node", "nodejs", "node js"},
    {"vue", "vuejs", "vue js"},
    {"next", "nextjs", "next js"},
    {"c#", "csharp", "c sharp"},
    {"c++", "cpp"},
    {"machine learning", "ml"},
    {"artificial intelligence", "ai"},
    {"continuous integration", "ci", "ci cd", "cicd"},
    {"rest", "rest api", "restful", "restful api"},
    {"sql server", "mssql", "microsoft sql server"},
    {"amazon s3", "s3"},
    {"elasticsearch", "elastic search", "elastic"},
]

_SPACE = re.compile(r"\s+")
# Keep + and # (C++, C#); turn other punctuation into spaces.
_PUNCT = re.compile(r"[^\w+#]+")


def normalize_skill(name: str) -> str:
    return _SPACE.sub(" ", _PUNCT.sub(" ", name.lower())).strip()


_CANONICAL: dict[str, str] = {}
for _group in ALIAS_GROUPS:
    _canon = sorted(_group)[0]
    for _name in _group:
        _CANONICAL[normalize_skill(_name)] = _canon


def canonical_skill(name: str) -> str:
    norm = normalize_skill(name)
    return _CANONICAL.get(norm, norm)


def skill_variants(name: str) -> set[str]:
    """All normalised spellings of a skill, from the alias table."""
    canon = canonical_skill(name)
    variants = {normalize_skill(name), canon}
    for group in ALIAS_GROUPS:
        normalized = {normalize_skill(n) for n in group}
        if canon in normalized:
            variants |= normalized
    return variants


def text_mentions_skill(text: str, skill: str) -> bool:
    """Whether `text` mentions `skill` or one of its aliases as a whole word or phrase."""
    haystack = f" {normalize_skill(text)} "
    for variant in skill_variants(skill):
        if not variant:
            continue
        # Short aliases ("go", "ai", "ts") only count as whole words.
        if re.search(rf"(?<![\w+#]){re.escape(variant)}(?![\w+#])", haystack):
            return True
    return False


def same_skill(a: str, b: str) -> bool:
    return canonical_skill(a) == canonical_skill(b)
