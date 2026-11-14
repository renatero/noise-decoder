"""Same-origin API, dashboard shell, and bounded public-data collection."""

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.collectors.bluesky import CollectorError, CollectorRateLimitError, collect_posts
from src.api.integration import analyze_events

WEB_DIR = Path(__file__).resolve().parents[1] / "web"
SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "datasets" / "bluesky_public_snapshot.json"
DATASET_DIR = Path(__file__).resolve().parents[2] / "datasets"
SYNTHETIC_DATASETS = {
    "synthetic_coordinated": DATASET_DIR / "synthetic_coordinated.json",
    "synthetic_benign": DATASET_DIR / "synthetic_benign.json",
}
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
async def analyze(request: AnalyzeRequest) -> dict[str, Any]:
    """Run normalized events through the current Engineer A integration adapter."""
    return await analyze_events([event.dict() for event in request.events])


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


@app.get("/api/datasets")
def list_datasets() -> dict[str, Any]:
    """List locally stored synthetic scenarios without loading every event."""
    datasets = []
    for identifier, path in SYNTHETIC_DATASETS.items():
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        datasets.append(
            {
                "id": identifier,
                "event_count": payload.get("event_count", 0),
                "notice": payload.get("notice"),
                "scenario": payload.get("scenario"),
            }
        )
    return {"datasets": datasets}


@app.get("/api/datasets/{dataset_id}")
def load_dataset(dataset_id: str) -> dict[str, Any]:
    """Load a reproducible offline synthetic scenario."""
    path = SYNTHETIC_DATASETS.get(dataset_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Unknown synthetic dataset.")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Synthetic dataset file is missing.")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")
