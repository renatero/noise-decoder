# Coordination Radar API

Run the dashboard and mock API on all network interfaces:

```bash
python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

The current demo is reachable at:

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

`POST /api/import` accepts an `events` array already in the normalized schema,
allowing other platforms to be supplied without adding a collector.

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

For internet-facing use, keep port `8000` allowed by the VPS/cloud firewall and
place the application behind an HTTPS reverse proxy before a public demo.
