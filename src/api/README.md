# Coordination Radar API

Run the dashboard and mock API on all network interfaces:

```bash
python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

The current demo is reachable at:

- Dashboard: `http://188.166.112.226:8000/`
- Health: `http://188.166.112.226:8000/healthz`
- Analysis: `POST http://188.166.112.226:8000/api/analyze`

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

Create an offline demo fallback from a trusted development machine, rather than
through the public web service:

```bash
python3 -m src.collectors.snapshot "your investigation phrase" --limit 50
```

The generated `datasets/bluesky_public_snapshot.json` is explicitly labelled
as a bounded public-search snapshot. `GET /api/snapshots/bluesky` loads it
without needing internet access.

The dashboard and API share one origin, so the extension only opens the
dashboard; it does not make cross-origin API requests. The server currently
returns a schema-valid mock analysis response until the detector is integrated.

For internet-facing use, keep port `8000` allowed by the VPS/cloud firewall and
place the application behind an HTTPS reverse proxy before a public demo.
