"""CSS selectors for X (Twitter) public timeline DOM.

X rotates its DOM frequently and runs A/B tests on layouts. Keep this file
as the single source of truth for selectors — tests in
`tests/test_x_selectors.py` and `tests/test_x_spider.py` cover them via the
offline fixture HTML in `tests/fixtures/x_user_page.html`.

When X breaks: update this file first, refresh the fixture, re-run tests.
Only touch `spider.py` if the response *shape* (not just selectors) changed.
"""

# Top-level tweet card. X has used this data-testid for years.
TWEET_ARTICLE = 'article[data-testid="tweet"]'

# Tweet body container (lang-marked so RTL/CJK both work).
TWEET_TEXT = 'div[data-testid="tweetText"]'

# Author block (display name + handle).
USER_NAME = 'div[data-testid="User-Name"]'

# Per-tweet permalink. Path segment after /status/ is the tweet id.
TWEET_LINK = 'a[href*="/status/"]'

# Timestamp element. `datetime` attribute holds ISO-8601 UTC.
TIME = "time"