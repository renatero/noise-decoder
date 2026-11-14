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
