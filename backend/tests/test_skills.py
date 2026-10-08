import pytest

from app.core.skills import canonical_skill, same_skill, text_mentions_skill


@pytest.mark.parametrize(
    ("text", "skill", "expected"),
    [
        ("Experience with Postgres required", "PostgreSQL", True),
        ("We use PostgreSQL", "postgres", True),
        ("Deploy on K8s", "Kubernetes", True),
        ("Google Cloud experience", "Go", False),
        ("Write services in Go", "golang", True),
        ("Strong C++ skills", "C++", True),
        ("Strong C skills", "C++", False),
        ("C# and .NET", "C#", True),
        ("React.js and Node.js", "React", True),
        ("React.js and Node.js", "node", True),
        ("Python3 scripting", "Python", True),
        ("pythonic code", "Python", False),
        ("Machine learning models", "ML", True),
        ("", "Python", False),
    ],
)
def test_text_mentions_skill(text: str, skill: str, expected: bool) -> None:
    assert text_mentions_skill(text, skill) is expected


def test_same_skill_and_canonical() -> None:
    assert same_skill("JS", "javascript")
    assert same_skill("Amazon Web Services", "aws")
    assert not same_skill("Java", "JavaScript")
    assert canonical_skill("  Fast-API ") == "fast api"
