"""Every CSS selector the Google source relies on, in one place (SCR-3.5).

UNVERIFIED: Google's jobs page couldn't be reached from the environment where this was
written, so these follow the long-standing layout of Google's jobs view (`ibp=htl;jobs`) and
the test fixtures in tests/scraper/fixtures/ are built to match. Google changes this markup
without notice: run `make scraper-canary` against the live site and update this file (and the
fixtures) if it reports `layout_changed`.

Each entry is a list of alternatives, tried in order.
"""

# One posting in the results list (left column).
LIST_ITEM = ["li div.PwjeAc", "div.PwjeAc", "div[role='treeitem'][data-ved]"]
CARD_TITLE = ["div.BjJfJf", "div[role='heading']"]
CARD_COMPANY = ["div.vNEEBe"]
# Location first, then "via <site>".
CARD_SUBLINES = ["div.Qk80Jf"]
# Small chips: "3 days ago", "Full-time", "$120K-$150K a year".
CARD_CHIPS = ["span.LL4CDc", "div.ocResc span"]

# The details pane for the selected posting (right column).
DETAIL_PANE = ["#tl_ditc div.whazf", "#tl_ditc", "div.whazf"]
DETAIL_DESCRIPTION = ["span.HBvzbc", "div.YgLbBe span"]
DETAIL_SHOW_MORE = ["div.cVLgvc", "div[role='button'][aria-expanded='false']"]
DETAIL_APPLY_LINKS = ["a.pMhGee", "span.DaDV9e a", "a[href*='utm_campaign=google_jobs_apply']"]
DETAIL_CHIPS = ["span.LL4CDc", "div.I2Cbhb span"]

# Pages that mean Google has blocked us.
BLOCK_SELECTORS = ["form#captcha-form", "div#recaptcha", "iframe[src*='recaptcha']"]
BLOCK_TEXT = ["unusual traffic from your computer network", "our systems have detected unusual"]
BLOCK_URL_PARTS = ["/sorry/"]
# The EU cookie-consent interstitial; we try to dismiss it before treating it as a block.
CONSENT_BUTTONS = ["button:has-text('Reject all')", "button:has-text('Accept all')"]


def any_of(selectors: list[str]) -> str:
    """A single selector matching any of the alternatives."""
    return ", ".join(selectors)
