# Google fixtures

Hand-made pages that follow the layout `app/scraper/sources/google_selectors.py` expects.
They were **not** captured from Google (it wasn't reachable where this code was written), so
they test the parsing and browser logic, not that Google still uses this markup.

When `make scraper-canary` shows the live layout has changed, save a real page with
`make scraper-canary SAVE=1`, update the selectors and refresh these files to match.

- `jobs_page.html`: a results list of three postings and a filled-in details pane.
- `jobs_interactive.html`: list items that fill the details pane when clicked, and load more
  items as you scroll (used by the browser test).
- `captcha.html`: Google's "unusual traffic" block page.
- `changed_layout.html`: a page with none of the expected elements.
