"""Bounded, unauthenticated collection from the public Bluesky AppView."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from json import JSONDecodeError, load
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


# ``api.bsky.app`` is Bluesky's unauthenticated AppView host. The newer
# ``public.api.bsky.app`` hostname can be blocked by some CDN regions, so use
# the host that is reachable from the demo VPS.
APPVIEW_BASE_URL = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"
MAX_LIMIT = 100
DEFAULT_TIMEOUT_SECONDS = 8
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "dclid", "gclsrc", "msclkid", "mc_cid", "mc_eid", "at_medium", "at_campaign", "traffic_source"}


class CollectorError(RuntimeError):
    """A public-data request could not be completed safely."""


class CollectorRateLimitError(CollectorError):
    """The upstream service rejected a bounded request due to rate limiting."""


@dataclass(frozen=True)
class CollectionResult:
    source: str
    query: str
    requested_limit: int
    fetched_posts: int
    deduplicated_posts: int
    skipped_posts: int
    events: list[dict[str, Any]]
    limitations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def canonicalize_url(value: str) -> str | None:
    """Remove fragments and common tracking parameters from an HTTP(S) URL."""
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return None
        netloc = hostname
        if parsed.port and not ((parsed.scheme == "https" and parsed.port == 443) or (parsed.scheme == "http" and parsed.port == 80)):
            netloc = f"{hostname}:{parsed.port}"
        kept = sorted(
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.lower().startswith("utm_") and key.lower() not in TRACKING_QUERY_KEYS
        )
        path = parsed.path.rstrip("/") or "/"
        return urlunsplit((parsed.scheme.lower(), netloc, path, urlencode(kept, doseq=True), ""))
    except (TypeError, ValueError):
        return None


def normalize_timestamp(value: Any) -> str | None:
    """Return an RFC 3339 UTC timestamp, or ``None`` if it cannot be parsed."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _facet_urls(record: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for facet in record.get("facets") or []:
        for feature in facet.get("features") or []:
            uri = feature.get("uri")
            if isinstance(uri, str):
                urls.append(uri)
    for candidate in (
        (record.get("embed") or {}).get("external", {}).get("uri"),
        (record.get("embed") or {}).get("external", {}).get("url"),
    ):
        if isinstance(candidate, str):
            urls.append(candidate)
    return urls


def _source_url(post: dict[str, Any]) -> str | None:
    author = post.get("author") or {}
    handle = author.get("handle")
    uri = post.get("uri")
    if not isinstance(handle, str) or not isinstance(uri, str):
        return None
    rkey = uri.rsplit("/", maxsplit=1)[-1]
    if not rkey or rkey == uri:
        return None
    return f"https://bsky.app/profile/{handle}/post/{rkey}"


def normalize_post(post: dict[str, Any]) -> dict[str, Any] | None:
    """Convert one AppView search result into the shared normalized schema."""
    record = post.get("record") or {}
    author = post.get("author") or {}
    uri = post.get("uri")
    did = author.get("did")
    text = record.get("text")
    timestamp = normalize_timestamp(record.get("createdAt")) or normalize_timestamp(post.get("indexedAt"))
    if not all(isinstance(value, str) and value.strip() for value in (uri, did, text, timestamp)):
        return None
    urls = sorted({url for value in _facet_urls(record) if (url := canonicalize_url(value))})
    return {
        "id": uri,
        "platform": "bluesky",
        "actor_id": f"bluesky:{did}",
        "timestamp": timestamp,
        "text": text,
        "urls": urls,
        "source_url": _source_url(post),
    }


def collect_posts(query: str, *, limit: int = 50, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> CollectionResult:
    """Search a bounded number of public Bluesky posts without authentication."""
    query = query.strip()
    if not query:
        raise ValueError("query must not be empty")
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    request_url = f"{APPVIEW_BASE_URL}?{urlencode({'q': query, 'limit': limit})}"
    request = Request(request_url, headers={"Accept": "application/json", "User-Agent": "CoordinationRadarDemo/0.1"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - fixed HTTPS endpoint
            payload = load(response)
    except HTTPError as error:
        if error.code == 429:
            raise CollectorRateLimitError("Bluesky rate limit reached; try again later.") from error
        raise CollectorError(f"Bluesky returned HTTP {error.code}.") from error
    except URLError as error:
        raise CollectorError("Bluesky is unavailable or the request timed out.") from error
    except (JSONDecodeError, UnicodeDecodeError) as error:
        raise CollectorError("Bluesky returned an unreadable response.") from error

    raw_posts = payload.get("posts") if isinstance(payload, dict) else None
    if not isinstance(raw_posts, list):
        raise CollectorError("Bluesky response did not contain a posts list.")

    events: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    skipped = 0
    duplicates = 0
    for raw_post in raw_posts[:limit]:
        event = normalize_post(raw_post) if isinstance(raw_post, dict) else None
        if not event:
            skipped += 1
            continue
        if event["id"] in seen_ids:
            duplicates += 1
            continue
        seen_ids.add(event["id"])
        events.append(event)

    return CollectionResult(
        source="bluesky_public_appview",
        query=query,
        requested_limit=limit,
        fetched_posts=len(raw_posts),
        deduplicated_posts=duplicates,
        skipped_posts=skipped,
        events=events,
        limitations=[
            "Public Bluesky search is bounded and may not represent all posts, accounts, or languages.",
            "This collection records public search results only; it does not establish coordination, identity, or intent.",
        ],
    )
