"""Bounded read-only Reddit Data API search for public submissions."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from threading import Lock
from urllib.parse import urlencode
from typing import Any

import httpx

from src.collectors.bluesky import CollectionResult, CollectorError, CollectorRateLimitError, canonicalize_url
from src.collectors.news import MAX_RESPONSE_BYTES, _validate, plain_text

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
SEARCH_URL = "https://oauth.reddit.com/search"
MAX_LIMIT = 100
_token_lock = Lock()
_cached_token: tuple[str, float] | None = None


def configured() -> bool:
    return all(os.environ.get(name, "").strip() for name in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT"))


def _read_json(response: httpx.Response, service: str) -> dict[str, Any]:
    if response.status_code == 429:
        raise CollectorRateLimitError(f"{service} rate limit reached; try again later.")
    if response.status_code in (401, 403):
        raise CollectorError(f"{service} credentials or permissions need administrator attention.")
    try:
        response.raise_for_status()
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise CollectorError(f"{service} response exceeds the 2 MiB limit.")
        result = response.json()
    except httpx.HTTPStatusError as error:
        raise CollectorError(f"{service} returned HTTP {error.response.status_code}.") from None
    except (httpx.HTTPError, ValueError, UnicodeDecodeError):
        raise CollectorError(f"{service} returned unreadable JSON or is unavailable.") from None
    if not isinstance(result, dict):
        raise CollectorError(f"{service} returned an invalid response.")
    return result


def _access_token() -> str:
    global _cached_token
    client_id = os.environ.get("REDDIT_CLIENT_ID", "").strip()
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
    user_agent = os.environ.get("REDDIT_USER_AGENT", "").strip()
    if not (client_id and client_secret and user_agent):
        raise CollectorError("Reddit API is not configured; add its OAuth app credentials and user agent.")
    with _token_lock:
        now = time.monotonic()
        if _cached_token and _cached_token[1] > now + 30:
            return _cached_token[0]
        try:
            response = httpx.post(TOKEN_URL, auth=(client_id, client_secret), data={"grant_type": "client_credentials"},
                                  headers={"User-Agent": user_agent}, timeout=8, follow_redirects=False)
        except httpx.HTTPError:
            raise CollectorError("Reddit OAuth is unavailable or timed out.") from None
        payload = _read_json(response, "Reddit OAuth")
        token, expires = payload.get("access_token"), payload.get("expires_in")
        if not isinstance(token, str) or not token or not isinstance(expires, (int, float)):
            raise CollectorError("Reddit OAuth returned an invalid access token.")
        _cached_token = token, now + max(0, float(expires))
        return token


def collect_reddit(query: str, *, limit: int = 50) -> CollectionResult:
    query = _validate(query, limit)
    if limit > MAX_LIMIT:
        raise ValueError(f"Reddit search supports 1–{MAX_LIMIT} results.")
    user_agent = os.environ.get("REDDIT_USER_AGENT", "").strip()
    token = _access_token()
    url = f"{SEARCH_URL}?{urlencode({'q': query, 'sort': 'new', 'limit': limit, 'type': 'link'})}"
    try:
        response = httpx.get(url, headers={"Authorization": f"Bearer {token}", "User-Agent": user_agent,
                                           "Accept": "application/json"}, timeout=10, follow_redirects=False)
    except httpx.HTTPError:
        raise CollectorError("Reddit search is unavailable or timed out.") from None
    payload = _read_json(response, "Reddit search")
    listing = payload.get("data")
    children = listing.get("children") if isinstance(listing, dict) else None
    if not isinstance(children, list):
        raise CollectorError("Reddit search did not return a submissions listing.")

    events, seen = [], set()
    skipped = duplicates = 0
    for child in children[:limit]:
        data = child.get("data") if isinstance(child, dict) else None
        if not isinstance(data, dict):
            skipped += 1
            continue
        identifier, author = data.get("id"), data.get("author")
        title = plain_text(data.get("title"))
        subreddit = plain_text(data.get("subreddit"))
        try:
            timestamp = datetime.fromtimestamp(float(data.get("created_utc")), timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        except (TypeError, ValueError, OverflowError, OSError):
            timestamp = None
        permalink = data.get("permalink")
        post_url = canonicalize_url(data.get("url"))
        if not (isinstance(identifier, str) and identifier and isinstance(author, str) and author not in ("", "[deleted]")
                and title and subreddit and timestamp and isinstance(permalink, str) and permalink.startswith("/")):
            skipped += 1
            continue
        if identifier in seen:
            duplicates += 1
            continue
        seen.add(identifier)
        selftext = plain_text(data.get("selftext"))[:1000]
        events.append({
            "id": f"reddit:{identifier}", "platform": "reddit", "actor_id": f"reddit:{author}",
            "timestamp": timestamp, "text": title + (f" — {selftext}" if selftext else ""),
            "urls": [post_url] if post_url else [], "source_url": f"https://www.reddit.com{permalink}",
            "publisher": f"r/{subreddit}", "record_type": "reddit_submission",
        })
    return CollectionResult("reddit_search", query, limit, len(children), duplicates, skipped, events, [
        "Reddit search returns a bounded, recent sample of public submissions; it is not a complete archive.",
        "Reddit OAuth credentials and a truthful identifying User-Agent are required. Follow Reddit Data API terms and rate limits.",
        "Deleted or malformed submissions are skipped. Reddit usernames identify submitting accounts, not necessarily article authors.",
    ])
