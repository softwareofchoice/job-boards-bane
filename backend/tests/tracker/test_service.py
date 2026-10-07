import pytest

from app.tracker.service import escape_like, normalize_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("HTTPS://Jobs.Example.COM/Posting/123", "https://jobs.example.com/Posting/123"),
        ("https://example.com/jobs/1/", "https://example.com/jobs/1"),
        ("https://example.com/jobs/1#apply", "https://example.com/jobs/1"),
        (
            "https://example.com/jobs?id=7&utm_source=li&UTM_campaign=x",
            "https://example.com/jobs?id=7",
        ),
        ("  https://example.com/a  ", "https://example.com/a"),
        ("https://example.com/", "https://example.com"),
    ],
)
def test_normalize_url(url: str, expected: str) -> None:
    assert normalize_url(url) == expected


def test_variants_of_one_posting_normalize_the_same() -> None:
    a = normalize_url("https://Example.com/jobs/42/?utm_medium=email#top")
    b = normalize_url("https://example.com/jobs/42")
    assert a == b


def test_escape_like() -> None:
    assert escape_like("100%_a\\b") == "100\\%\\_a\\\\b"
