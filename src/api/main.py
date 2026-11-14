"""Same-origin API, dashboard shell, and bounded public-data collection."""

import json
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.collectors.bluesky import CollectorError, CollectorRateLimitError, collect_posts

WEB_DIR = Path(__file__).resolve().parents[1] / "web"
SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "datasets" / "bluesky_public_snapshot.json"
app = FastAPI(title="Coordination Radar")
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


class Event(BaseModel):
    id: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    timestamp: str = Field(min_length=1)
    text: str = Field(min_length=1)
    urls: list[str] = Field(default_factory=list)
    source_url: str | None = None


class AnalyzeRequest(BaseModel):
    events: list[Event] = Field(default_factory=list)


class ImportRequest(BaseModel):
    """Offline fallback: caller supplies already-normalized platform events."""

    events: list[Event] = Field(default_factory=list)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "coordination-radar"}


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest) -> dict[str, Any]:
    actors = sorted({event.actor_id for event in request.events})
    status: Literal["inconclusive", "insufficient_data"] = (
        "inconclusive" if len(request.events) >= 2 else "insufficient_data"
    )
    return {
        "status": status,
        "nodes": [{"id": actor, "label": actor} for actor in actors],
        "edges": [],
        "clusters": [],
        "evidence": [],
        "statistics": {"events_observed": len(request.events), "actors_observed": len(actors)},
        "limitations": [
            "Mock analysis response: the detector is not integrated yet.",
            "This result does not identify bots or establish intent.",
        ],
    }


def collect_bluesky_or_error(query: str, limit: int) -> dict[str, Any]:
    try:
        return collect_posts(query, limit=limit).to_dict()
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except CollectorRateLimitError as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except CollectorError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get("/api/collect/bluesky")
def collect_bluesky(
    query: str = Query(min_length=1, max_length=512),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    """Retrieve a bounded, unauthenticated set of public Bluesky posts."""
    return collect_bluesky_or_error(query, limit)


@app.get("/api/snapshots/bluesky")
def load_bluesky_snapshot() -> dict[str, Any]:
    """Load the saved offline public-data fallback without external access."""
    if not SNAPSHOT_PATH.exists():
        raise HTTPException(status_code=404, detail="No Bluesky snapshot has been saved yet.")
    try:
        snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=500, detail="The saved Bluesky snapshot is invalid JSON.") from error
    return snapshot


@app.post("/api/import")
def import_normalized_events(request: ImportRequest) -> dict[str, Any]:
    """Accept normalized JSON from another platform without collector changes."""
    events_by_id: dict[str, Event] = {}
    for event in request.events:
        events_by_id.setdefault(event.id, event)
    return {
        "source": "normalized_json_import",
        "events_received": len(request.events),
        "deduplicated_events": len(request.events) - len(events_by_id),
        "events": [event.dict() for event in events_by_id.values()],
        "limitations": ["Imported records are accepted as supplied; source collection coverage is not independently verified."],
    }


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")
