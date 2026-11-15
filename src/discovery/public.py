"""Related social/discussion posts; publisher feeds stay in the news dashboard."""

import asyncio
from itertools import zip_longest
from typing import Any

from src.collectors.bluesky import CollectorError
from src.collectors.news import collect_hackernews
from src.discovery.bluesky import (
    MAX_RELATED_POSTS, MAX_RESULTS_PER_QUERY, _queries,
    discover_related_posts as discover_bluesky,
)


async def _hackernews(events: list[dict[str, Any]]) -> dict[str, Any]:
    queries = _queries(events)
    results = await asyncio.gather(*(
        asyncio.to_thread(collect_hackernews, query, limit=MAX_RESULTS_PER_QUERY)
        for query in queries
    ), return_exceptions=True)
    found = {}
    failures = 0
    limitations = []
    for result in results:
        if isinstance(result, (CollectorError, OSError)):
            failures += 1
            continue
        if isinstance(result, BaseException):
            raise result
        limitations.extend(result.limitations)
        for event in result.events:
            found.setdefault(event["id"], {
                "post_id": event["id"], "platform": event["platform"],
                "actor_id": event["actor_id"], "timestamp": event["timestamp"],
                "text": event["text"], "url": event["source_url"],
                "links": event["urls"], "discovery_source": "hackernews_algolia",
            })
    if failures:
        limitations.append(f"{failures} Hacker News search request(s) failed; results may be incomplete.")
    return {"events": list(found.values())[:MAX_RELATED_POSTS],
            "queries_run": len(queries), "limitations": list(dict.fromkeys(limitations))}


async def discover_related_posts(events: list[dict[str, Any]]) -> dict[str, Any]:
    if not _queries(events):
        return {"events": [], "queries_run": 0,
                "limitations": ["No usable text or URLs were available as search seeds."]}
    results = await asyncio.gather(discover_bluesky(events), _hackernews(events), return_exceptions=True)
    found = {}
    limitations = ["Discovery searches Bluesky and Hacker News with up to five queries each and 100 total posts. Publisher RSS feeds are available separately in the dashboard."]
    successes = []
    sources = []
    for source, result in zip(("bluesky", "hackernews"), results):
        if isinstance(result, Exception):
            limitations.append(f"{source} discovery failed; other available results are retained.")
            sources.append({"id": source, "status": "error"})
        else:
            successes.append(result)
            limitations.extend(result["limitations"])
            sources.append({"id": source, "status": "partial" if any("failed" in item for item in result["limitations"]) else "ok"})
    for row in zip_longest(*(result["events"] for result in successes)):
        for event in row:
            if event:
                found.setdefault(event["post_id"], event)
    return {"events": list(found.values())[:MAX_RELATED_POSTS],
            "queries_run": sum(result["queries_run"] for result in successes),
            "sources": sources, "limitations": list(dict.fromkeys(limitations))}
