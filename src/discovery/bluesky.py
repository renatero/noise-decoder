"""Bounded, read-only related-post search against Bluesky's public AppView."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx


SEARCH_URL = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"
MAX_SEEDS = 40
MAX_QUERIES = 5
MAX_RESULTS_PER_QUERY = 25
MAX_RELATED_POSTS = 100
TIMEOUT_SECONDS = 10
URL_RE = re.compile(r"https?://[^\s<>\]\[{}()]+", re.IGNORECASE)


def _queries(events: list[dict[str, Any]]) -> list[str]:
    queries: list[str] = []
    seen: set[str] = set()
    for event in events[:MAX_SEEDS]:
        text = str(event.get("text") or "").strip()
        urls = list(event.get("links") or []) + URL_RE.findall(text)
        for raw_url in urls:
            try:
                parsed = urlparse(str(raw_url).rstrip(".,!?;"))
                query = f"{parsed.hostname}{parsed.path}" if parsed.hostname else ""
            except ValueError:
                query = ""
            query = query[:180].strip("/")
            if query and query.lower() not in seen:
                queries.append(query)
                seen.add(query.lower())
        # Use the seed phrase as a search query as well as any links it contains.
        phrase = re.sub(r"\s+", " ", URL_RE.sub(" ", text)).strip()
        phrase = phrase[:180]
        if len(phrase) >= 12 and phrase.lower() not in seen:
            queries.append(phrase)
            seen.add(phrase.lower())
        if len(queries) >= MAX_QUERIES:
            break
    return queries[:MAX_QUERIES]


def _event(post: dict[str, Any]) -> dict[str, Any] | None:
    uri = post.get("uri")
    author = post.get("author") or {}
    record = post.get("record") or {}
    text = record.get("text")
    if not isinstance(uri, str) or not isinstance(text, str) or not text.strip():
        return None
    did = author.get("did") or "unknown"
    handle = author.get("handle") or did
    rkey = uri.rsplit("/", 1)[-1]
    links: list[str] = []
    for facet in record.get("facets") or []:
        for feature in facet.get("features") or []:
            if feature.get("$type") == "app.bsky.richtext.facet#link" and isinstance(feature.get("uri"), str):
                links.append(feature["uri"])
    embed = post.get("embed") or {}
    external = embed.get("external") or {}
    if isinstance(external.get("uri"), str):
        links.append(external["uri"])
    return {
        "post_id": uri,
        "platform": "bluesky",
        "actor_id": f"bluesky:{did}",
        "actor_handle": handle,
        "timestamp": record.get("createdAt"),
        "text": text,
        "url": f"https://bsky.app/profile/{handle}/post/{rkey}",
        "links": sorted(set(links)),
        "discovery_source": "bluesky_public_search",
    }


async def discover_related_posts(events: list[dict[str, Any]], *, transport: httpx.AsyncBaseTransport | None = None) -> dict[str, Any]:
    """Search Bluesky for a small, deduplicated set of public posts related to seeds."""
    queries = _queries(events)
    if not queries:
        return {"events": [], "queries_run": 0, "limitations": ["No usable text or URLs were available as search seeds."]}

    found: dict[str, dict[str, Any]] = {}
    failures = 0
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=False, transport=transport) as client:
        for query in queries:
            try:
                response = await client.get(SEARCH_URL, params={"q": query, "limit": MAX_RESULTS_PER_QUERY})
                response.raise_for_status()
                posts = response.json().get("posts", [])
                for post in posts:
                    event = _event(post)
                    if event:
                        found.setdefault(event["post_id"], event)
                    if len(found) >= MAX_RELATED_POSTS:
                        break
            except (httpx.HTTPError, ValueError, TypeError):
                failures += 1
            if len(found) >= MAX_RELATED_POSTS:
                break

    limitations = ["Search is limited to public Bluesky posts, at most five seed queries and 100 returned posts."]
    if failures:
        limitations.append(f"{failures} public search request(s) failed; returned results may be incomplete.")
    return {"events": list(found.values()), "queries_run": len(queries), "limitations": limitations}
