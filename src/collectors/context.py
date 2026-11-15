"""Explicit, credit-bounded Context.dev news search (never part of all sources)."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

import httpx

from src.collectors.bluesky import CollectorError, CollectorRateLimitError, canonicalize_url, normalize_timestamp
from src.collectors.news import MAX_RESPONSE_BYTES, _validate, plain_text

SEARCH_URL = "https://api.context.dev/v1/news/search"
CACHE_SECONDS = 600
REQUESTS_PER_MINUTE = 4
_lock = Lock()


class ContextUnavailable(CollectorError):
    pass


def configured() -> bool:
    return bool(os.environ.get("CONTEXT_API_KEY", "").strip())


def _fetch(body: dict[str, Any], key: str) -> dict[str, Any]:
    try:
        with httpx.stream("POST", SEARCH_URL, json=body, timeout=12, follow_redirects=False,
                          headers={"Authorization": f"Bearer {key}", "Accept": "application/json"}) as response:
            if response.status_code == 429:
                raise CollectorRateLimitError("Context.dev is rate limited. Try again later.")
            if response.status_code in (401, 403):
                raise ContextUnavailable("Context.dev credentials or permissions need server administrator attention.")
            if response.status_code == 402:
                raise ContextUnavailable("Context.dev has insufficient credits. Other sources remain available.")
            response.raise_for_status()
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > MAX_RESPONSE_BYTES:
                    raise CollectorError("Context.dev response exceeds the 2 MiB limit.")
            data = json.loads(content)
    except httpx.HTTPStatusError as error:
        raise CollectorError(f"Context.dev returned HTTP {error.response.status_code}.") from None
    except httpx.HTTPError:
        raise CollectorError("Context.dev is unavailable or timed out. No automatic retry was made.") from None
    except (ValueError, UnicodeDecodeError):
        raise CollectorError("Context.dev returned unreadable JSON.") from None
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise CollectorError("Context.dev did not return an article list.")
    return data


def _normalize(data: dict[str, Any], query: str, limit: int, days: int, now: float) -> dict[str, Any]:
    events, urls, stories, identifiers = [], set(), set(), set()
    skipped = duplicates = 0
    for article in data["data"][:limit]:
        if not isinstance(article, dict):
            skipped += 1
            continue
        source = article.get("source") if isinstance(article.get("source"), dict) else {}
        identifier = article.get("id")
        story = article.get("story_id")
        story = story if isinstance(story, str) else None
        url = canonicalize_url(article.get("url"))
        title = plain_text(article.get("title"))
        timestamp = normalize_timestamp(article.get("published_at"))
        domain = source.get("domain")
        if not (isinstance(identifier, str) and identifier and url and title and timestamp
                and isinstance(domain, str) and domain.strip() and article.get("language") == "en"):
            skipped += 1
            continue
        published = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()
        if not now - days * 86400 <= published <= now:
            skipped += 1
            continue
        if identifier in identifiers or url in urls or (story and story in stories):
            duplicates += 1
            continue
        identifiers.add(identifier)
        urls.add(url)
        if story:
            stories.add(story)
        description = plain_text(article.get("description"))[:600]
        events.append({
            "id": f"context:{identifier}", "platform": "news_context", "actor_id": f"publisher:{domain.lower()}",
            "timestamp": timestamp, "text": title[:1000] + (f" — {description}" if description else ""),
            "urls": [url], "source_url": url, "publisher": plain_text(source.get("name")) or domain,
            "record_type": "publisher_article", "story_id": story, "language": "en",
        })
    metadata = data.get("key_metadata") if isinstance(data.get("key_metadata"), dict) else {}
    return {
        "source": "context_news", "query": query, "requested_limit": limit,
        "fetched_posts": len(data["data"]), "deduplicated_posts": duplicates, "skipped_posts": skipped,
        "events": events, "cached": False, "credits_consumed": metadata.get("credits_consumed"),
        "has_more": bool(data.get("has_more")),
        "collected_at": datetime.fromtimestamp(now, timezone.utc).isoformat(),
        "limitations": [
            f"Context.dev: English articles published within the last {days} days, ranked by relevance. Results may include loosely related coverage.",
            "Duplicate URLs and provider story groups are collapsed. Missing or invalid publication dates are skipped; fewer than the requested number may remain.",
            "Publisher articles provide news context and are excluded from account coordination analysis. Shared coverage does not establish coordination.",
            "Search results may be cached for ten minutes. Article bodies are not collected; use the original publisher links.",
        ],
    }


def collect_news(query: str, *, limit: int = 10, days: int = 7) -> dict[str, Any]:
    query = _validate(query, limit)
    if limit > 10 or not 1 <= days <= 30:
        raise ValueError("Context.dev supports 1–10 results and a 1–30 day window per search.")
    key = os.environ.get("CONTEXT_API_KEY", "").strip()
    if not key:
        raise ContextUnavailable("Context.dev is not configured on this server.")
    try:
        daily_limit = int(os.environ.get("CONTEXT_DAILY_REQUEST_LIMIT", "20"))
    except ValueError:
        raise ContextUnavailable("Context.dev daily request limit is misconfigured.") from None
    if daily_limit <= 0:
        raise ContextUnavailable("Context.dev search is disabled by the server administrator.")
    state_path = Path(os.environ.get("CONTEXT_STATE_PATH", ".context-state.sqlite3"))
    cache_key = hashlib.sha256(json.dumps([query, limit, days]).encode()).hexdigest()
    # Single flight in this service process; SQLite atomically reserves the budget
    # across workers and restarts. Failed/uncertain requests retain their reservation.
    with _lock:
        now = time.time()
        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(state_path, timeout=5)) as db, db:
                db.execute("CREATE TABLE IF NOT EXISTS requests (at REAL NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, at REAL NOT NULL, result TEXT NOT NULL)")
                db.execute("BEGIN IMMEDIATE")
                db.execute("DELETE FROM requests WHERE at < ?", (now - 86400 * 2,))
                db.execute("DELETE FROM cache WHERE at <= ?", (now - CACHE_SECONDS,))
                row = db.execute("SELECT result FROM cache WHERE key = ?", (cache_key,)).fetchone()
                if row:
                    result = json.loads(row[0])
                    result.update(cached=True, credits_consumed=0)
                    return result
                midnight = datetime.fromtimestamp(now, timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
                daily = db.execute("SELECT COUNT(*) FROM requests WHERE at >= ?", (midnight,)).fetchone()[0]
                recent = db.execute("SELECT COUNT(*) FROM requests WHERE at > ?", (now - 60,)).fetchone()[0]
                if daily >= daily_limit:
                    raise CollectorRateLimitError("Context.dev daily search allowance is used. It resets at midnight UTC; other sources remain available.")
                if recent >= REQUESTS_PER_MINUTE:
                    raise CollectorRateLimitError("Context.dev search is limited to four new requests per minute. Try again shortly.")
                db.execute("INSERT INTO requests (at) VALUES (?)", (now,))
                db.commit()
                data = _fetch({
                    "searchBy": {"type": "natural_language", "query": query}, "limit": limit,
                    "filterBy": {"articleLanguage": ["en"], "date": {
                        "from": int((now - days * 86400) * 1000), "to": int(now * 1000)}},
                }, key)
                result = _normalize(data, query, limit, days, now)
                db.execute("INSERT OR REPLACE INTO cache VALUES (?, ?, ?)", (cache_key, now, json.dumps(result)))
                return result
        except (sqlite3.Error, OSError, ValueError):
            raise ContextUnavailable("Context.dev cache or request budget storage is unavailable.") from None
