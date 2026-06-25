"""X (Twitter) public timeline scraper.

Wraps Scrapling's `StealthySession` (auto-bypass Cloudflare Turnstile) and
returns a normalized list of tweet dicts.

Layering rule: this module does not import LightAgent. The crawl layer
must be testable without an LLM in the loop.
"""

from scrapling.fetchers import StealthySession

from omnispy.config import settings

from .selectors import TIME, TWEET_ARTICLE, TWEET_LINK, TWEET_TEXT, USER_NAME


def fetch_user_tweets(handle: str, limit: int = 10) -> list[dict]:
    """Fetch the most recent tweets from a public X user timeline.

    Args:
        handle: X username without leading @.
        limit:  Maximum number of tweets to return.

    Returns:
        A list of dicts with keys: ``id``, ``text``, ``time``, ``author``.
        Empty list on invalid handle or no results.
    """
    handle = handle.lstrip("@").strip()
    if not handle:
        return []

    url = f"https://x.com/{handle}"
    with StealthySession(headless=True, cookies_str=settings.x_cookie) as session:
        page = session.fetch(url)

    return _parse_tweets(page, limit)


def _parse_tweets(page, limit: int) -> list[dict]:
    """Extract tweet dicts from a Scrapling page-like object.

    Exposed at module scope so tests can call it directly with a parsed
    HTML fixture.
    """
    out: list[dict] = []
    seen_ids: set[str] = set()

    for card in page.css(TWEET_ARTICLE)[:limit]:
        tweet_id = _extract_tweet_id(card.css(TWEET_LINK))
        if not tweet_id or tweet_id in seen_ids:
            continue
        seen_ids.add(tweet_id)

        out.append({
            "id": tweet_id,
            "text": _first_text(card, TWEET_TEXT),
            "time": _first_attr(card, TIME, "datetime"),
            "author": _first_text(card, USER_NAME),
        })

    return out


def _extract_tweet_id(link_elements) -> str | None:
    for el in link_elements:
        href = el.attrib.get("href", "")
        if "/status/" in href:
            return href.split("/status/")[-1].split("?")[0].split("/")[0]
    return None


def _first_text(card, selector: str) -> str | None:
    """Return whitespace-normalized text under the first match, or None.

    Recurses into nested elements so blocks like User-Name (which contains
    display-name and handle spans) yield a single concatenated string.
    """
    matches = card.css(selector)
    if not matches:
        return None
    parts = [t.strip() for t in matches[0].css("::text").getall() if t.strip()]
    return " ".join(parts) if parts else None


def _first_attr(card, selector: str, attr: str) -> str | None:
    """Return attribute of the first matching element, or None."""
    matches = card.css(selector)
    if not matches:
        return None
    return matches[0].attrib.get(attr)