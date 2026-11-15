"""FastAPI application for the local Noise Decoder analysis engine."""

from __future__ import annotations

import argparse
import json
import logging
import re
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from src.engine.analyzer import analyze
from src.discovery.public import discover_related_posts


LOGGER = logging.getLogger("noise_decoder.api")
MAX_BODY_BYTES = 5 * 1024 * 1024
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}

app = FastAPI(
    title="Noise Decoder API",
    version="0.1.0",
    description="Local analysis API for evidence-weighted actor networks.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1"],
    allow_origin_regex=r"^(chrome-extension://[^/]+|http://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?)$",
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=600,
)


@app.middleware("http")
async def restrict_to_loopback_hosts(request: Request, call_next):
    host = request.url.hostname
    if host not in LOOPBACK_HOSTS:
        return _json_error(403, "Host is not allowed; use localhost or 127.0.0.1.")
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "noise-decoder-api"}


@app.post("/analyze")
async def analyze_request(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise HTTPException(status_code=415, detail="Content-Type must be application/json.")

    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Request body exceeds the 5 MiB limit.")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=400, detail="Request body must be valid UTF-8 JSON.") from error
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object.")

    try:
        return await analyze(payload)
    except Exception as error:
        LOGGER.exception("Analysis request failed")
        raise HTTPException(status_code=500, detail="Analysis failed.") from error


@app.post("/discover")
async def discover_request(request: Request) -> dict[str, Any]:
    """Search public Bluesky and Hacker News posts using visible posts as seeds."""
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise HTTPException(status_code=415, detail="Content-Type must be application/json.")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Request body exceeds the 5 MiB limit.")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=400, detail="Request body must be valid UTF-8 JSON.") from error
    events = payload.get("events", []) if isinstance(payload, dict) else None
    if not isinstance(events, list) or any(not isinstance(event, dict) for event in events):
        raise HTTPException(status_code=400, detail="Request body must contain an events array.")
    try:
        return await discover_related_posts(events)
    except Exception as error:
        LOGGER.exception("Related-post discovery failed")
        raise HTTPException(status_code=502, detail="Public source discovery failed.") from error


def _json_error(status_code: int, detail: str):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=status_code, content={"detail": detail})


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Noise Decoder FastAPI service.")
    parser.add_argument("--host", default="127.0.0.1", help="Loopback interface to bind (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000).")
    args = parser.parse_args()
    if args.host not in LOOPBACK_HOSTS:
        parser.error("The local analysis API may only bind to a loopback host.")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
