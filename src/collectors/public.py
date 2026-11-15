"""Source registry and failure-tolerant, bounded combined collection."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from itertools import zip_longest
from typing import Any

from src.collectors.bluesky import CollectorError, collect_posts
from src.collectors.news import FEEDS, collect_feed, collect_hackernews, _validate
from src.collectors.context import configured as context_configured
from src.collectors.reddit import collect_reddit, configured as reddit_configured

SOURCE_IDS = ("bluesky", "hackernews", "reddit", *FEEDS)


class CollectionFailed(CollectorError):
    def __init__(self, message: str, sources: list[dict[str, Any]]):
        super().__init__(message)
        self.sources = sources


def source_details(source: str) -> dict[str, str]:
    if source in FEEDS:
        name, url = FEEDS[source]
        return {"id": source, "name": name, "url": url, "scope": "Current RSS headlines, filtered by all query words; not the publisher archive."}
    return {
        "all": {"id": source, "name": "All live sources", "url": "", "scope": "Collection stopped before individual source outcomes were available."},
        "bluesky": {"id": source, "name": "Bluesky", "url": "https://bsky.app/", "scope": "Bounded public post search."},
        "hackernews": {"id": source, "name": "Hacker News", "url": "https://hn.algolia.com/", "scope": "Story submissions searched through the Algolia index."},
        "reddit": {"id": source, "name": "Reddit", "url": "https://www.reddit.com/", "scope": "Bounded search of public submissions through Reddit's OAuth Data API."},
        "context": {"id": source, "name": "Context.dev news index", "url": "https://www.context.dev/", "scope": "English publisher articles in the selected date window, ranked by relevance."},
    }[source]


def collection_details(source: str, query: str, limit: int, result: dict[str, Any], *,
                       error: CollectorError | OSError | None = None, days: int | None = None) -> dict[str, Any]:
    """Keep the attempted source inventory even when it returns zero or fails."""
    rows = getattr(error, "sources", None) or result.get("sources")
    if rows is None:
        rows = [{"id": source, "status": "error" if error else "ok",
                 "available_events": None if error else len(result.get("events", [])),
                 "returned_events": 0 if error else len(result.get("events", [])),
                 "fetched_posts": None if error else result.get("fetched_posts"),
                 "error": str(error) if error else None}]
    sources = [{**source_details(row["id"]), **row} for row in rows]
    if source == "context" and days is not None:
        sources[0]["scope"] = f"English publisher articles from the last {days} days, ranked by relevance."
    return {**result, "query": query.strip(), "requested_limit": limit, "sources": sources,
            "source": result.get("source", source),
            "search_completed_at": datetime.now(timezone.utc).isoformat()}


def source_catalog() -> list[dict[str, Any]]:
    return [
        {"id": "all", "name": "All live sources", "kind": "combined"},
        {"id": "bluesky", "name": "Bluesky", "kind": "social_search"},
        {"id": "hackernews", "name": "Hacker News", "kind": "discussion_search"},
        {"id": "reddit", "name": "Reddit", "kind": "discussion_search", "available": reddit_configured(), "included_in_all": True},
        {"id": "context", "name": "Context.dev news", "kind": "news_search", "available": context_configured(),
         "method": "POST", "max_limit": 10, "default_days": 7, "included_in_all": False},
        *({"id": key, "name": name, "kind": "news_feed", "feed_url": url}
          for key, (name, url) in FEEDS.items()),
    ]


def collect_source(source: str, query: str = "", *, limit: int = 50) -> dict[str, Any]:
    query = _validate(query, limit, allow_empty=source in FEEDS)
    if source == "bluesky":
        return collect_posts(query, limit=limit).to_dict()
    if source == "hackernews":
        return collect_hackernews(query, limit=limit).to_dict()
    if source == "reddit":
        return collect_reddit(query, limit=limit).to_dict()
    if source in FEEDS:
        return collect_feed(source, query, limit=limit).to_dict()
    if source != "all":
        raise ValueError("Unknown public source")

    def fetch(source_id):
        try:
            return source_id, collect_source(source_id, query, limit=limit), None
        except (CollectorError, OSError) as error:
            return source_id, None, str(error)

    with ThreadPoolExecutor(max_workers=len(SOURCE_IDS)) as pool:
        results = list(pool.map(fetch, SOURCE_IDS))
    successes = [(key, result) for key, result, error in results if result is not None]
    if not successes:
        raise CollectionFailed("All public sources are unavailable; try again later.", [
            {"id": key, "status": "error", "available_events": None, "returned_events": 0, "error": error}
            for key, result, error in results])
    # Interleave results so one prolific source cannot consume the entire limit.
    events, seen = [], set()
    duplicate_count = sum(result["deduplicated_posts"] for _, result in successes)
    for row in zip_longest(*(result["events"] for _, result in successes)):
        for event in row:
            if event is None:
                continue
            if event["id"] in seen:
                duplicate_count += 1
                continue
            seen.add(event["id"])
            events.append(event)
    selected = events[:limit]
    selected_ids = {event["id"] for event in selected}
    return {
        "source": "all_public_sources", "query": query, "requested_limit": limit,
        "fetched_posts": sum(result["fetched_posts"] for _, result in successes),
        "deduplicated_posts": duplicate_count,
        "skipped_posts": sum(result["skipped_posts"] for _, result in successes),
        "events": selected,
        "sources": [{"id": key, "status": "ok" if result is not None else "error",
                     "available_events": len(result["events"]) if result else None,
                     "fetched_posts": result["fetched_posts"] if result else None,
                     "returned_events": sum(event["id"] in selected_ids for event in result["events"]) if result else 0,
                     "error": error} for key, result, error in results],
        "limitations": list(dict.fromkeys([
            "Combined collection is capped at the requested total, interleaved across available sources. RSS results cover current headlines only.",
            *(message for _, result in successes for message in result["limitations"]),
            *(f"{key} failed: {error}" for key, result, error in results if error),
        ])),
    }
