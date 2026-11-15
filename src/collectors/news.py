"""Bounded public news feeds and Hacker News search; no credentials required."""

from __future__ import annotations

import json
import re
import time
from datetime import timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from threading import Lock
from typing import Any
from urllib.parse import urlencode
from xml.etree import ElementTree

import httpx

from src.collectors.bluesky import (
    CollectionResult, CollectorError, CollectorRateLimitError,
    canonicalize_url, normalize_timestamp,
)

FEEDS = {
    "bbc": ("BBC News — World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    "guardian": ("The Guardian — World", "https://www.theguardian.com/world/rss"),
    "aljazeera": ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
}
HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
FEED_CACHE_SECONDS = 300
_feed_cache: dict[str, tuple[float, bytes]] = {}
_cache_lock = Lock()


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data):
        self.parts.append(data)


def plain_text(value: Any) -> str:
    parser = _PlainText()
    parser.feed(value if isinstance(value, str) else "")
    return " ".join(" ".join(parser.parts).split())


def fetch_bytes(url: str) -> bytes:
    """Only called with fixed publisher endpoints or an encoded search query."""
    try:
        with httpx.stream("GET", url, timeout=8, follow_redirects=False,
                          headers={"User-Agent": "NoiseDecoder/0.1", "Accept": "application/json, application/rss+xml, text/xml"}) as response:
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise CollectorError("Public source response exceeds the 2 MiB limit.")
            return bytes(body)
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 429:
            raise CollectorRateLimitError("Public source rate limit reached; try again later.") from error
        raise CollectorError(f"Public source returned HTTP {error.response.status_code}.") from error
    except httpx.HTTPError as error:
        raise CollectorError("Public source is unavailable or timed out.") from error


def _validate(query: str, limit: int, *, allow_empty: bool = False) -> str:
    query = query.strip()
    if not query and not allow_empty:
        raise ValueError("query must not be empty")
    if len(query) > 512:
        raise ValueError("query must be at most 512 characters")
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    return query


def _feed_bytes(source: str) -> bytes:
    with _cache_lock:
        cached = _feed_cache.get(source)
        if cached and time.monotonic() - cached[0] < FEED_CACHE_SECONDS:
            return cached[1]
    body = fetch_bytes(FEEDS[source][1])
    # Do not cache error pages or malformed XML.
    _feed_items(body)
    with _cache_lock:
        _feed_cache[source] = (time.monotonic(), body)
    return body


def _feed_items(body: bytes) -> list[ElementTree.Element]:
    if b"<!DOCTYPE" in body.upper() or b"<!ENTITY" in body.upper():
        raise CollectorError("Public feed contains unsupported XML declarations.")
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as error:
        raise CollectorError("Public source returned an unreadable RSS feed.") from error
    if root.tag != "rss" or root.find("channel") is None:
        raise CollectorError("Public source did not return an RSS feed.")
    return root.findall("./channel/item")[:200]


def collect_feed(source: str, query: str = "", *, limit: int = 50) -> CollectionResult:
    if source not in FEEDS:
        raise ValueError("Unknown news feed")
    query = _validate(query, limit, allow_empty=True)
    items = _feed_items(_feed_bytes(source))
    events, seen = [], set()
    skipped = duplicates = 0
    # Match literal words (AND), or a canonical article URL. This is a filter
    # over the current feed, not a publisher archive search.
    query_url = canonicalize_url(query)
    terms = re.findall(r"\w+", query.casefold())
    if query and not query_url and not terms:
        raise ValueError("query must contain a word or an HTTP(S) URL")
    for item in items:
        title = plain_text(item.findtext("title"))
        url = canonicalize_url(item.findtext("link") or "")
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
            timestamp = normalize_timestamp(published.astimezone(timezone.utc).isoformat()) if published.tzinfo else None
        except (ValueError, TypeError, OverflowError):
            timestamp = None
        if not title or not url or not timestamp:
            skipped += 1
            continue
        if url in seen:
            duplicates += 1
            continue
        seen.add(url)
        summary = plain_text(item.findtext("description"))[:600]
        text = title + (f" — {summary}" if summary and summary != title else "")
        words = set(re.findall(r"\w+", text.casefold()))
        if query_url and query_url != url:
            continue
        if not query_url and not all(term in words for term in terms):
            continue
        events.append({
            "id": f"news:{source}:{url}", "platform": "news_rss",
            "actor_id": f"publisher:{source}", "timestamp": timestamp,
            "text": text, "urls": [url], "source_url": url,
            "publisher": FEEDS[source][0], "record_type": "publisher_article",
        })
    events.sort(key=lambda event: event["timestamp"], reverse=True)
    return CollectionResult(source=f"{source}_rss", query=query, requested_limit=limit,
        fetched_posts=len(items), deduplicated_posts=duplicates, skipped_posts=skipped,
        events=events[:limit], limitations=[
            f"{FEEDS[source][0]}: current RSS headlines and summaries only; cached for up to five minutes. A phrase filters these items by all words, not the full news archive.",
            "RSS actor IDs identify publishers, not individual journalists or social accounts. Shared coverage does not establish coordination.",
        ])


def collect_hackernews(query: str, *, limit: int = 50) -> CollectionResult:
    query = _validate(query, limit)
    url = f"{HN_SEARCH_URL}?{urlencode({'query': query, 'tags': 'story', 'hitsPerPage': limit})}"
    try:
        payload = json.loads(fetch_bytes(url))
    except (ValueError, UnicodeDecodeError) as error:
        raise CollectorError("Hacker News search returned unreadable JSON.") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("hits"), list):
        raise CollectorError("Hacker News search did not return a hits list.")
    events, seen = [], set()
    skipped = duplicates = 0
    for hit in payload["hits"][:limit]:
        if not isinstance(hit, dict):
            skipped += 1
            continue
        identifier, author = hit.get("objectID"), hit.get("author")
        title = plain_text(hit.get("title"))
        timestamp = normalize_timestamp(hit.get("created_at"))
        if not (isinstance(identifier, str) and identifier.isdigit() and
                isinstance(author, str) and author.strip() and title and timestamp):
            skipped += 1
            continue
        if identifier in seen:
            duplicates += 1
            continue
        seen.add(identifier)
        link = canonicalize_url(hit.get("url") or "")
        events.append({
            "id": f"hackernews:{identifier}", "platform": "hackernews",
            "actor_id": f"hackernews:{author}", "timestamp": timestamp,
            "text": title, "urls": [link] if link else [],
            "source_url": f"https://news.ycombinator.com/item?id={identifier}",
        })
    return CollectionResult(source="hackernews_algolia", query=query, requested_limit=limit,
        fetched_posts=len(payload["hits"]), deduplicated_posts=duplicates, skipped_posts=skipped,
        events=events, limitations=[
            "Hacker News story search uses Algolia's public index, ordered by publication date. Coverage is technology-focused, bounded, and may lag the site.",
            "Actors are submitting Hacker News usernames, not article authors. A shared article alone does not establish coordination.",
        ])
