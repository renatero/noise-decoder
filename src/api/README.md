<<<<<<< HEAD
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
=======
# FastAPI analysis service

Install the dependency and run the loopback-only HTTP server from the repository root:

```sh
python -m pip install -r requirements.txt
python -m src.api.server
```

The FastAPI app is served by Uvicorn at `127.0.0.1:8000` by default, matching the extension's configured local endpoint. Interactive OpenAPI docs are available at `http://localhost:8000/docs`; the schema is at `/openapi.json`. It exposes:

- `GET http://localhost:8000/health` — simple readiness response.
- `POST http://localhost:8000/discover` — accepts `{ "events": [...] }` and searches public Bluesky posts using visible posts as seeds.
- `POST http://localhost:8000/analyze` — accepts the extension JSON object and returns the Python engine report.

Example request:

```sh
curl -sS http://localhost:8000/analyze \
  -H 'Content-Type: application/json' \
  --data-binary @payload.json
```

FastAPI's CORS middleware handles the extension's preflight requests and accepts loopback and `chrome-extension://` origins. The Uvicorn process binds only to a loopback address, and `/analyze` limits request bodies to 5 MiB. Use `Ctrl+C` to stop it.

## Tests

Install the development test dependencies and run the API tests from the repository root:

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s src/api/tests -v
```

The extension calls `/discover` when you select **Extract visible posts**. The API searches the unauthenticated public Bluesky AppView for up to five text/URL seed queries and returns at most 100 posts. The extension retains results that match a seed by its canonical URL or near-duplicate text rules, then computes the coordination features. Search failures leave the visible-page extraction available and are shown in the status message. This first provider searches Bluesky only; it does not crawl arbitrary websites or other platforms.

The API tests exercise the ASGI app in process, including analysis and discovery responses, extension CORS preflight, malformed requests, body-size limits, and loopback host checks.
>>>>>>> 900fde4f23704b10b7b2955a32c7d23890720f63
