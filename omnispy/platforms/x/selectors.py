"""CSS selectors for X (Twitter) public timeline DOM.

X rotates its DOM frequently and runs A/B tests on layouts. Keep this file
as the single source of truth for selectors — tests in
``tests/test_x_spider.py`` cover them via the offline fixture HTML in
``tests/fixtures/x_user_page.html``.

When X breaks: update this file first, refresh the fixture, re-run tests.
Only touch ``spider.py`` if the response *shape* (not just selectors) changed.

X serves different DOM to different browsers (A/B or bot detection).
Selectors are grouped by variant — the spider tries each in order.
"""

# -- Variant A: React-hydrated page (browser with strong JS fingerprint) ---
# Uses ``data-testid`` attributes.  Kept as v1 baseline.

TWEET_ARTICLE_V1 = 'article[data-testid="tweet"]'
TWEET_TEXT_V1 = 'div[data-testid="tweetText"]'
USER_NAME_V1 = 'div[data-testid="User-Name"]'

# -- Variant B: server-rendered page (Scrapling / Patchright / lightweight) -
# Uses ``data-tweet-id`` and Tailwind-ish utility classes.  No <time> element.

TWEET_ARTICLE_V2 = 'article[data-tweet-id]'
TWEET_TEXT_V2 = 'div.whitespace-pre-wrap.break-words.text-body.font-normal'
USER_NAME_V2 = 'a.font-bold[href*="x.com/"]'

# Shared across variants
TWEET_LINK = 'a[href*="/status/"]'