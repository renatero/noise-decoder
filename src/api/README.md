# Coordination Radar API

Run the dashboard and API locally:

```bash
python3 -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

The deployed demo is reachable at:

- Dashboard: `https://radar.188.166.112.226.nip.io/`
- Health: `https://radar.188.166.112.226.nip.io/healthz`
- Analysis: `POST https://radar.188.166.112.226.nip.io/api/analyze`

## Public-data collection

The bounded, unauthenticated Bluesky collector uses the public AppView search
endpoint (`https://api.bsky.app/xrpc/app.bsky.feed.searchPosts`):

```text
GET /api/collect/bluesky?query=<phrase>&limit=50
```

`limit` is restricted to 1–100. Responses normalize IDs, actor IDs, UTC
timestamps, source URLs, and URLs while deduplicating records. Upstream rate
limits return `429`; unavailable or malformed upstream responses return `502`.

Additional public sources are available without credentials:

```text
GET /api/sources
GET /api/collect/hackernews?query=<phrase>&limit=50
GET /api/collect/bbc?query=<optional words or URL>&limit=50
GET /api/collect/guardian?query=<optional words or URL>&limit=50
GET /api/collect/aljazeera?query=<optional words or URL>&limit=50
GET /api/collect/all?query=<phrase>&limit=50
```

Feed searches filter the current headlines and summaries by all supplied words,
or an exact canonical article URL. An empty query returns recent feed items;
it is rejected for social search and combined collection. RSS is not an archive
search. Feeds are cached for five minutes, inspected up to 200 items, and capped
at 2 MiB per response. Hacker News searches story submissions in date order.
Publication timestamps must be present; missing dates are never replaced by
collection time. RSS records identify the publisher (`publisher:bbc`, etc.);
Hacker News records identify the submitting username.

Combined collection requests sources concurrently and interleaves results up to
the **total** limit. Each source may fetch up to the limit before merging. The
`sources` field reports availability, available/returned event counts and errors;
`limitations` also exposes failures. If every source fails the endpoint returns
`502`; one failing source does not discard results from healthy sources.

The separate local extension API (`python -m src.api.server`) now searches both
Bluesky and Hacker News through `POST /discover`, with up to five seed queries
per provider and 100 combined posts. Publisher feeds remain in the dashboard;
they are not inserted as social accounts into extension discovery.

See [source research and coverage](../../docs/news-sources.md) for endpoints,
attribution, access considerations and reasons for selection.

`POST /api/import` accepts an `events` array already in the normalized schema,
allowing other platforms to be supplied without adding a collector.

## Bounded news and discussion sources

`GET /api/sources` returns the live source catalog. The dashboard currently
offers a bounded combined search plus these public sources:

- Bluesky public search;
- Hacker News story search through its public Algolia index;
- BBC World RSS;
- The Guardian World RSS; and
- Al Jazeera RSS.

Use `GET /api/collect/<source>?query=<phrase>&limit=50` for an individual
source, or `/api/collect/all` for an interleaved, bounded result across the
available sources. RSS collection uses publisher-provided headlines and
summaries only; it does not fetch article pages. Publisher actor IDs identify
the publishing source rather than a journalist or social account, and shared
coverage alone does not establish coordination.

## Synthetic scenarios and analysis

- `GET /api/datasets` lists the reproducible coordinated and benign scenarios.
- `GET /api/datasets/synthetic_coordinated` and
  `GET /api/datasets/synthetic_benign` load their labelled JSON events.
- `POST /api/analyze` passes normalized events through the current
  evidence-weighted graph adapter and Engineer A's community-discovery engine.

The report status is `suspicious` only when the engine finds a recurring
evidence-backed actor network. It is `inconclusive` for observed but one-off
patterns, and `insufficient_data` for too little input. None of these states
establishes bot identity or propaganda intent.

Create an offline demo fallback from a trusted development machine, rather than
through the public web service:

```bash
python3 -m src.collectors.snapshot "your investigation phrase" --limit 50
```

The generated `datasets/bluesky_public_snapshot.json` is explicitly labelled
as a bounded public-search snapshot. `GET /api/snapshots/bluesky` loads it
without needing internet access.

The dashboard and API share one origin, so the extension only opens the
dashboard; it does not make cross-origin API requests.

The deployed service binds locally and is exposed by the Caddy HTTPS reverse
proxy. Do not expose port `8000` directly for public use.

### Search coverage in dashboard reports

Live collection responses include `sources`, `query`, `requested_limit`, and
`search_completed_at`, even when no usable records match. Each source includes
its display name, link, search scope, completion status, and usable/returned
record counts. A failed source has `available_events: null` (unknown), rather
than zero matches. Collection errors retain HTTP error status and carry this
trace under `collection` alongside `detail`. The dashboard shows the trace below
the verdict and includes it in exported reports. Offline datasets/imports are
explicitly labelled as having performed no live search. Context.dev reports its
news index and selected date window; it does not imply direct searches of every
publisher or social platform.
