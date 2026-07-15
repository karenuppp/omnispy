"""X (Twitter) public timeline scraper.

Wraps Scrapling's ``StealthySession`` (auto-bypass Cloudflare Turnstile) and
returns a normalized list of tweet dicts.

Layering rule: this module does not import LightAgent. The crawl layer
must be testable without an LLM in the loop.
"""

import asyncio
import json
import math
from datetime import datetime
from urllib.parse import quote

from scrapling.fetchers import StealthySession

from omnispy.config import settings


def _parse_cookies(cookie_str: str) -> list[dict]:
    """Convert a browser-exported cookie string into the list-of-dicts format
    that Scrapling's ``cookies`` parameter expects.

    Only ``auth_token`` and ``ct0`` are extracted — they're the only cookies
    required for X authentication.  Other cookies (guest_id, twid, etc.) may
    contain URL-encoded values or special attributes that Patchright rejects.
    """
    raw: dict[str, str] = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        key, value = key.strip(), value.strip()
        if key and value:
            raw[key] = value

    essential = ("auth_token", "ct0")
    out: list[dict] = []
    for key in essential:
        if key in raw:
            out.append({
                "name": key,
                "value": raw[key],
                "domain": ".x.com",
                "path": "/",
                "secure": True,
                "sameSite": "Lax",
            })
    return out


from .selectors import (
    TWEET_ARTICLE_V1,
    TWEET_ARTICLE_V2,
    TWEET_LINK,
    TWEET_TEXT_V1,
    TWEET_TEXT_V2,
    USER_NAME_V1,
    USER_NAME_V2,
)


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

    # LightAgent may invoke tool functions from a worker thread that lacks a
    # running event loop.  Patchright's *sync* API refuses to operate when a
    # loop *is* running (it detects an active ``asyncio.get_running_loop`` and
    # errors out), yet it internally needs ``get_event_loop`` to be set.
    # Workaround: temporarily clear the running-loop state so Patchright's
    # sync API can proceed, then restore it afterwards.
    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None  # no running loop — ideal for Patchright

    scroll_times = max(1, math.ceil(limit / 3))

    if running_loop is not None:
        # Patchright sync_api will refuse to start inside a running loop.
        # Defer the whole fetch to a thread that has no running loop.
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_fetch_sync, url, limit, scroll_times)
            return future.result()

    return _fetch_sync(url, limit, scroll_times)


def search_tweets(
    keywords: list[str] | None = None,
    from_users: list[str] | None = None,
    query: str | None = None,
    sort: str = "top",
    limit: int = 20,
    since: str | None = None,
    until: str | None = None,
    scroll_times: int | None = None,
) -> list[dict]:
    """Search X (Twitter) for tweets matching keywords and/or from specific users.

    Args:
        keywords:   List of search terms (combined with OR).
        from_users: List of X handles without leading @ (combined with OR).
        query:      Raw X search query snippet for advanced filters.
        sort:       ``"top"`` for hot tweets (default), ``"latest"`` for real-time.
        limit:      Maximum tweets to return (up to ~20, page-load dependent).
        since:      Only tweets from this date onwards (YYYY-MM-DD).
        until:      Only tweets before this date (YYYY-MM-DD).
        scroll_times: How many times to scroll for more results.
            Auto-calculated from limit when ``None`` (default).

    Returns:
        A list of dicts with keys: ``id``, ``text``, ``time``, ``author``.
        Empty list when all search params are empty.
    """
    if not keywords and not from_users and not query:
        return []

    if scroll_times is None:
        # Generous upper bound — _make_scroll_action will exit early once
        # enough articles are in the DOM via wait_for_function + count check.
        scroll_times = max(1, math.ceil(limit / 3))

    q = _build_search_query(
        keywords=keywords,
        from_users=from_users,
        raw=query,
        since=since,
        until=until,
    )
    sort_param = "top" if sort == "top" else "live"
    url = f"https://x.com/search?q={quote(q)}&f={sort_param}&src=typed_query"

    result = _do_fetch(url, limit, scroll_times)

    # Fallback: server-side returned empty -> retry without date operators
    # and client-filter instead.
    if not result and (since or until):
        q_fallback = _build_search_query(
            keywords=keywords,
            from_users=from_users,
            raw=query,
            since=None,
            until=None,
        )
        url_fallback = f"https://x.com/search?q={quote(q_fallback)}&f={sort_param}&src=typed_query"
        result = _do_fetch(url_fallback, limit, scroll_times)
        result = _filter_tweets_by_time(result, since, until)

    return result[:limit]


def _do_fetch(url: str, limit: int, scroll_times: int = 0) -> list[dict]:
    """Internal: run the fetch with StealthySession, handling asyncio loop
    detection. Returns parsed tweet list (may be empty)."""
    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    if running_loop is not None:
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_fetch_sync, url, limit, scroll_times)
            return future.result()

    return _fetch_sync(url, limit, scroll_times)


def _make_scroll_action(max_scrolls: int, target_count: int, settle_time: int = 1000):
    """Create a ``page_action`` that scrolls until enough tweets are in DOM.

    Uses Playwright's ``wait_for_function`` (MutationObserver-based polling)
    to detect when new ``<article>`` elements appear, instead of guessing
    with fixed delays.

    1. Waits for React to render initial tweets (``article > 0``, 15 s timeout).
    2. Repeatedly scrolls to the bottom, waiting each time for the article
       count to increase (8 s timeout per scroll).
    3. Exits early when ``target_count`` articles are in the DOM.

    Args:
        max_scrolls:  Hard cap on scroll attempts (safety against infinite loop).
        target_count: Stop once this many articles are in the DOM.
        settle_time:  Extra ms to wait after count increase before next check.

    Returns:
        A callable for ``StealthySession.fetch(page_action=...)``.
    """

    def _scroll(page):
        # 1. Wait for React to render at least one tweet
        try:
            page.wait_for_function(
                "document.querySelectorAll('article').length > 0",
                timeout=15000,
            )
        except Exception:
            pass  # no initial tweets — X may be rate-limiting or empty

        # 2. Scroll + wait for growth, exit early at target.
        # Track consecutive failures — 3 in a row with no new articles means
        # X has no more content, no point continuing to timeout.
        consecutive_failures = 0
        for _ in range(max_scrolls):
            count = page.evaluate("document.querySelectorAll('article').length")
            if count >= target_count:
                break

            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

            try:
                page.wait_for_function(
                    f"document.querySelectorAll('article').length > {count}",
                    timeout=8000,
                )
                page.wait_for_timeout(settle_time)
                consecutive_failures = 0
            except Exception:
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    break  # 3 strikes — no more content from X
                continue  # try next scroll

    return _scroll


# ---------------------------------------------------------------------------
# X GraphQL API intercept helpers  (API-first, DOM fallback)
# ---------------------------------------------------------------------------

def _extract_api_entries(body: dict) -> list[dict]:
    """Extract raw entry dicts from an X GraphQL ``UserTweets`` response.

    Returns entries for actual tweets (skips cursor, who-to-follow, etc.).
    Shared with the DOM fallback — this is only used when the API response
        is available.
    """
    try:
        instructions = body["data"]["user"]["result"]["timeline"]["timeline"]["instructions"]
    except (KeyError, TypeError):
        return []

    entries: list[dict] = []
    for instr in instructions:
        t = instr.get("type")
        if t == "TimelinePinEntry":
            e = instr.get("entry")
            if e:
                entries.append(e)
        elif t == "TimelineAddEntries":
            for e in instr.get("entries", []):
                eid = e.get("entryId", "")
                if eid and not eid.startswith("cursor-") and not eid.startswith("who-to-follow-"):
                    entries.append(e)
    return entries


def _parse_api_tweet(entry: dict) -> dict | None:
    """Parse a single raw API entry into our tweet dict.

    Returns ``None`` when the entry does not contain a valid tweet (skipped
        silently — same as the DOM filter for image-only / broken tweets).
    """
    eid = entry.get("entryId", "")
    if not eid:
        return None

    # --- drill into the result object ------------------------------------
    try:
        ic = entry["content"]["itemContent"]
        result = ic.get("tweet_results", {}).get("result", {})
    except (KeyError, TypeError):
        return None

    # Unwrap TweetWithVisibilityResults
    if result.get("__typename") == "TweetWithVisibilityResults":
        result = result.get("tweet", result)

    rest_id = result.get("rest_id")
    if not rest_id:
        return None

    legacy = result.get("legacy", {})
    text = legacy.get("full_text", "")
    if not text:
        return None

    # --- author -----------------------------------------------------------
    user = result.get("core", {}).get("user_results", {}).get("result", {})
    author = user.get("core", {}).get("name", "")
    handle = user.get("legacy", {}).get("screen_name", "")

    # --- time -------------------------------------------------------------
    created_at = legacy.get("created_at", "")
    time_iso = created_at
    if created_at:
        try:
            dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
            time_iso = dt.isoformat()
        except ValueError:
            pass

    return {
        "id": rest_id,
        "text": text,
        "time": time_iso,
        "author": author or handle,
        "handle": handle or author,
        "like_count": legacy.get("favorite_count"),
        "reply_count": legacy.get("reply_count"),
        "retweet_count": legacy.get("retweet_count"),
        "view_count": result.get("views", {}).get("count"),
    }


def _parse_api_tweets(raw_entries: list[dict]) -> list[dict]:
    """Batch-parse API entries and deduplicate by ``id``."""
    seen: set[str] = set()
    out: list[dict] = []
    for e in raw_entries:
        t = _parse_api_tweet(e)
        if t and t["id"] not in seen:
            seen.add(t["id"])
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# Fetch implementation
# ---------------------------------------------------------------------------


def _fetch_sync(url: str, limit: int, scroll_times: int = 0) -> list[dict]:
    """Fetch a page, trying X GraphQL API first, falling back to DOM parsing.

    1. Sets up a ``response`` listener for the ``UserTweets`` GraphQL endpoint
       *before* the page navigates (so the initial API call is captured).
    2. Scrolls normally (counting ``<article>`` elements for early exit).
    3. If API data is available → parse from JSON (precise count, richer data).
    4. If API data is insufficient → supplement with DOM parsing.
    5. If no API data at all → pure DOM fallback (current original behaviour).
    """
    api_entries: list[dict] = []

    def _page_setup(page):
        """Set short timeout + listen for X GraphQL UserTweets responses."""
        page.set_default_timeout(15_000)

        def _on_api_response(response):
            if "/UserTweets" in response.url:
                try:
                    raw = json.loads(response.body())
                    entries = _extract_api_entries(raw)
                    if entries:
                        api_entries.extend(entries)
                except Exception:
                    pass

        page.on("response", _on_api_response)

    # Build the scroll action (unchanged)
    page_action = None
    if scroll_times > 0:
        max_scrolls = scroll_times + 5
        page_action = _make_scroll_action(max_scrolls, limit)

    with StealthySession(headless=True, cookies=_parse_cookies(settings.x_cookie)) as session:
        page = session.fetch(
            url,
            network_idle=True,
            timeout=90000,
            disable_resources=True,
            page_setup=_page_setup,
            page_action=page_action,
            wait=3000 if scroll_times > 0 else 0,
        )

    # --- API mode -----------------------------------------------------------
    if api_entries:
        api_tweets = _parse_api_tweets(api_entries)
        if api_tweets:
            # If API got enough, return it directly.
            if len(api_tweets) >= limit:
                return api_tweets[:limit]

            # Otherwise supplement with DOM tweets (dedup by id).
            dom_tweets = _parse_tweets(page, limit)
            seen = {t["id"] for t in api_tweets if t.get("id")}
            for t in dom_tweets:
                tid = t.get("id")
                if tid and tid not in seen:
                    seen.add(tid)
                    api_tweets.append(t)
                    if len(api_tweets) >= limit:
                        break
            return api_tweets[:limit]

    # --- DOM fallback --------------------------------------------------------
    return _parse_tweets(page, limit)


def _filter_tweets_by_time(
    tweets: list[dict],
    since: str | None,
    until: str | None,
) -> list[dict]:
    """Filter a list of tweet dicts by ISO datetime (v1 ``time`` field).

    Tweets whose ``time`` field is not an ISO datetime (e.g. relative strings
    like "9h" from the v2 DOM variant) are included as-is — they can't be
    reliably compared.  This is a best-effort filter.
    """
    if not tweets:
        return tweets

    since_date = datetime.strptime(since, "%Y-%m-%d").date() if since else None
    until_date = datetime.strptime(until, "%Y-%m-%d").date() if until else None

    out: list[dict] = []
    for t in tweets:
        ts = t.get("time")
        if not ts:
            out.append(t)
            continue

        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            out.append(t)  # relative time, can't compare
            continue

        if since_date and dt.date() < since_date:
            continue
        if until_date and dt.date() >= until_date:
            continue
        out.append(t)

    return out


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------



def _pick_variant(card):
    """Detect which DOM variant this card uses.

    Returns ``'v2'`` when the card carries ``data-tweet-id`` (server-rendered
    page), ``'v1'`` otherwise (React-hydrated page with ``data-testid``).
    """
    if card.attrib.get("data-tweet-id"):
        return "v2"
    return "v1"


def _build_search_query(
    keywords: list[str] | None = None,
    from_users: list[str] | None = None,
    raw: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> str:
    """Build an X search query string from structured parameters.

    Args:
        keywords:   List of search terms (combined with OR).
        from_users: List of X handles without leading @ (combined with OR).
        raw:        Raw X search query snippet, appended as-is.
        since:      Only tweets from this date onwards (YYYY-MM-DD).
        until:      Only tweets before this date (YYYY-MM-DD).

    Returns:
        A plain (non-URL-encoded) query string for ``x.com/search?q=``.
    """
    parts: list[str] = []

    if keywords:
        kw_parts = [f'"{kw}"' if " " in kw else kw for kw in keywords]
        if len(kw_parts) == 1:
            parts.append(kw_parts[0])
        else:
            parts.append("(" + " OR ".join(kw_parts) + ")")

    if from_users:
        user_parts = [f"from:@{u.lstrip('@')}" for u in from_users]
        if len(user_parts) == 1:
            parts.append(user_parts[0])
        else:
            parts.append("(" + " OR ".join(user_parts) + ")")

    if raw:
        parts.append(raw)

    if since:
        parts.append(f"since:{since}")

    if until:
        parts.append(f"until:{until}")

    return " ".join(parts)


def _parse_tweets(page, limit: int) -> list[dict]:
    """Extract tweet dicts from a Scrapling page-like object.

    Exposed at module scope so tests can call it directly with a parsed
    HTML fixture.
    """
    out: list[dict] = []
    seen_ids: set[str] = set()

    cards = _find_cards(page)[:limit]

    for card in cards:
        variant = _pick_variant(card)
        tweet_id = _extract_tweet_id(card, variant)
        if not tweet_id or tweet_id in seen_ids:
            continue
        seen_ids.add(tweet_id)

        text = _extract_text(card, variant)
        if not text:
            # Image-only / video-only tweet with no caption — skip
            continue

        out.append({
            "id": tweet_id,
            "text": text,
            "time": _extract_time(card, variant),
            "author": _extract_author(card, variant),
        })

    return out


def _find_cards(page):
    """Return tweet card elements, trying each known variant selector."""
    cards = page.css(TWEET_ARTICLE_V1)
    if cards:
        return cards
    return page.css(TWEET_ARTICLE_V2)


# ---- ID extraction ----


def _extract_tweet_id(card, variant: str) -> str | None:
    # v2: tweet id sits directly on the <article> attribute
    if variant == "v2":
        return card.attrib.get("data-tweet-id")

    # v1: extract from /status/<id> permalink
    return _extract_id_from_links(card.css(TWEET_LINK))


def _extract_id_from_links(link_elements) -> str | None:
    for el in link_elements:
        href = el.attrib.get("href", "")
        if "/status/" in href:
            return href.split("/status/")[-1].split("?")[0].split("/")[0]
    return None


# ---- Text extraction ----


def _extract_text(card, variant: str) -> str | None:
    selector = TWEET_TEXT_V2 if variant == "v2" else TWEET_TEXT_V1
    matches = card.css(selector)
    if not matches:
        return None
    # v2 returns multiple candidates (one per text block in the card);
    # the last one is the actual tweet body.
    if variant == "v2" and len(matches) > 1:
        el = matches[-1]
    else:
        el = matches[0]
    parts = [t.strip() for t in el.css("::text").getall() if t.strip()]
    return " ".join(parts) if parts else None


# ---- Author extraction ----


def _extract_author(card, variant: str) -> str | None:
    selector = USER_NAME_V2 if variant == "v2" else USER_NAME_V1
    matches = card.css(selector)
    if not matches:
        return None
    parts = [t.strip() for t in matches[0].css("::text").getall() if t.strip()]
    return parts[0] if parts else None


# ---- Time extraction ----


def _extract_time(card, variant: str) -> str | None:
    if variant == "v2":
        # No <time> element in server-rendered DOM.
        # The status permalink's text is the relative time (e.g. "9h").
        for el in card.css(TWEET_LINK):
            href = el.attrib.get("href", "")
            if "/status/" in href:
                text = el.css("::text").get()
                if text and text.strip():
                    return text.strip()
        return None

    # v1: <time datetime="...">
    matches = card.css("time")
    if matches:
        return matches[0].attrib.get("datetime")
    return None