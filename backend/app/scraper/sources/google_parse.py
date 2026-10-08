"""Pure HTML parsing for the Google source, kept apart from the browser so it can be tested
against saved pages (SCR-3.2, SCR-3.5)."""

import re
from dataclasses import dataclass, field
from datetime import datetime

from bs4 import BeautifulSoup, Tag

from app.scraper.normalize import parse_posted
from app.scraper.schemas import RawPosting
from app.scraper.sources import google_selectors as sel

_SALARY = re.compile(r"[$£€]\s?\d|\d\s?[kK]\b.*(year|yr|hour|hr|month)|an hour|a year", re.I)
_POSTED = re.compile(r"\bago\b|just posted|today|yesterday", re.I)


@dataclass
class Card:
    title: str
    company: str
    location: str | None = None
    via: str | None = None
    posted_text: str | None = None
    salary_text: str | None = None


@dataclass
class Detail:
    description: str = ""
    apply_urls: list[str] = field(default_factory=list)
    posted_text: str | None = None
    salary_text: str | None = None


def _first(root: Tag, selectors: list[str]) -> Tag | None:
    for selector in selectors:
        found = root.select_one(selector)
        if found is not None:
            return found
    return None


def _all(root: Tag, selectors: list[str]) -> list[Tag]:
    for selector in selectors:
        found = root.select(selector)
        if found:
            return found
    return []


def _text(tag: Tag | None) -> str:
    return " ".join(tag.get_text(" ", strip=True).split()) if tag is not None else ""


def _classify_chips(texts: list[str]) -> tuple[str | None, str | None]:
    posted = next((t for t in texts if _POSTED.search(t)), None)
    salary = next((t for t in texts if _SALARY.search(t) and t != posted), None)
    return posted, salary


def is_blocked(html: str, url: str = "") -> bool:
    if any(part in url for part in sel.BLOCK_URL_PARTS):
        return True
    soup = BeautifulSoup(html, "html.parser")
    if _first(soup, sel.BLOCK_SELECTORS) is not None:
        return True
    text = soup.get_text(" ", strip=True).lower()
    return any(phrase in text for phrase in sel.BLOCK_TEXT)


def parse_list(html: str) -> list[Card]:
    """The postings in the results list. Raises LayoutChangedError if the list isn't there."""
    soup = BeautifulSoup(html, "html.parser")
    items = _all(soup, sel.LIST_ITEM)
    if not items:
        raise LayoutChangedError("No job list items found on the page.")
    return [card for item in items if (card := parse_card(item)) is not None]


def parse_card(item: Tag | str) -> Card | None:
    if isinstance(item, str):
        item = BeautifulSoup(item, "html.parser")
    title = _text(_first(item, sel.CARD_TITLE))
    company = _text(_first(item, sel.CARD_COMPANY))
    if not title or not company:
        return None
    sublines = [_text(t) for t in _all(item, sel.CARD_SUBLINES)]
    location = next((s for s in sublines if not s.lower().startswith("via ")), None)
    via_line = next((s for s in sublines if s.lower().startswith("via ")), None)
    posted, salary = _classify_chips([_text(t) for t in _all(item, sel.CARD_CHIPS)])
    return Card(
        title=title,
        company=company,
        location=location or None,
        via=via_line[4:].strip() if via_line else None,
        posted_text=posted,
        salary_text=salary,
    )


def parse_detail(html: str) -> Detail:
    """The selected posting's details pane. Raises LayoutChangedError if it isn't there."""
    soup = BeautifulSoup(html, "html.parser")
    pane = _first(soup, sel.DETAIL_PANE)
    if pane is None:
        raise LayoutChangedError("No job details pane found on the page.")
    description_tag = _first(pane, sel.DETAIL_DESCRIPTION)
    description = description_tag.get_text("\n", strip=True) if description_tag is not None else ""
    urls = [str(a.get("href")) for a in _all(pane, sel.DETAIL_APPLY_LINKS) if a.get("href")]
    posted, salary = _classify_chips([_text(t) for t in _all(pane, sel.DETAIL_CHIPS)])
    return Detail(description=description, apply_urls=urls, posted_text=posted, salary_text=salary)


class LayoutChangedError(Exception):
    """The page didn't have the elements we expected; Google probably changed its markup."""


def merge(card: Card, detail: Detail, now: datetime, fallback_url: str) -> RawPosting:
    """A posting from a list card and its details pane."""
    posted_text = card.posted_text or detail.posted_text
    return RawPosting(
        title=card.title,
        company=card.company,
        location=card.location,
        via=card.via,
        posted_text=posted_text,
        posted_at=parse_posted(posted_text, now),
        salary_text=card.salary_text or detail.salary_text,
        url=detail.apply_urls[0] if detail.apply_urls else fallback_url,
        description=detail.description,
    )
