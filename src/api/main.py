"""Same-origin API, dashboard shell, and bounded public-data collection."""

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from pydantic import BaseModel, Field

from src.collectors.bluesky import CollectorError, CollectorRateLimitError, collect_posts
from src.collectors.public import SOURCE_IDS, collect_source, source_catalog, collection_details
from src.collectors.context import ContextUnavailable, collect_news as collect_context_news
from src.api.integration import analyze_events
from src.providers.experimental import router as provider_router
from src.providers.companies import router as company_router, recover_jobs

WEB_DIR = Path(__file__).resolve().parents[1] / "web"
SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "datasets" / "bluesky_public_snapshot.json"
DATASET_DIR = Path(__file__).resolve().parents[2] / "datasets"
SYNTHETIC_DATASETS = {
    "synthetic_coordinated": DATASET_DIR / "synthetic_coordinated.json",
    "synthetic_benign": DATASET_DIR / "synthetic_benign.json",
}


@asynccontextmanager
async def lifespan(app):
    recover_jobs()
    yield


app = FastAPI(title="Coordination Radar", lifespan=lifespan)
app.include_router(provider_router)
app.include_router(company_router)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, error: RequestValidationError):
    # FastAPI normally echoes invalid input, which may contain submitted keys.
    if request.url.path.startswith('/api/settings'):
        return JSONResponse(status_code=422, content={'detail': 'Invalid provider settings. Check field types and lengths.'})
    return await request_validation_exception_handler(request, error)


class Event(BaseModel):
    id: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    timestamp: str = Field(min_length=1)
    text: str = Field(min_length=1)
    urls: list[str] = Field(default_factory=list)
    source_url: str | None = None
    publisher: str | None = None
    record_type: str | None = None
    story_id: str | None = None
    language: str | None = None


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
    news = [event for event in request.events if event.platform == "news_context"]
    social = [event for event in request.events if event.platform != "news_context"]
    report = await analyze_events([event.model_dump() for event in social])
    if news:
        report["news_context"] = [event.model_dump() for event in news]
        report["statistics"]["news_articles"] = len(news)
        report["statistics"]["news_publishers"] = len({event.actor_id for event in news})
        report["limitations"].append("Context.dev publisher articles are excluded from account coordination analysis.")
        if not social:
            report["status"] = "news_context"
            report["limitations"] = ["Publisher articles provide background context for a separate account investigation."]
            report["summary"] = f"{len(news)} news articles collected as background context. Publisher coverage is not evidence of coordinated accounts."
    return report


class ContextSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=512)
    limit: int = Field(default=10, ge=1, le=10)
    days: int = Field(default=7, ge=1, le=30)


def collection_failure(source, query, limit, error, status, *, days=None):
    return JSONResponse(status_code=status, content={"detail": str(error), "collection":
        collection_details(source, query, limit, {"events": []}, error=error, days=days)})


@app.post("/api/collect/context")
def collect_context(payload: ContextSearchRequest, request: Request):
    # Custom header + no CORS opt-in prevents cross-site browser spending. This
    # public demo also enforces a durable, global credit budget in the collector.
    origin = request.headers.get("origin")
    try:
        parsed_origin = urlsplit(origin) if origin else None
        foreign_origin = parsed_origin and (parsed_origin.netloc != request.url.netloc or parsed_origin.scheme != request.url.scheme)
    except ValueError:
        foreign_origin = True
    if request.headers.get("x-noisedecoder-request") != "1" or foreign_origin:
        raise HTTPException(status_code=403, detail="Start Context.dev searches from this dashboard.")
    try:
        result = collect_context_news(payload.query, limit=payload.limit, days=payload.days)
        return collection_details("context", payload.query, payload.limit, result, days=payload.days)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from None
    except ContextUnavailable as error:
        return collection_failure("context", payload.query, payload.limit, error, 503, days=payload.days)
    except CollectorRateLimitError as error:
        return collection_failure("context", payload.query, payload.limit, error, 429, days=payload.days)
    except CollectorError as error:
        return collection_failure("context", payload.query, payload.limit, error, 502, days=payload.days)


def collect_bluesky_or_error(query: str, limit: int):
    try:
        return collection_details("bluesky", query, limit, collect_posts(query, limit=limit).to_dict())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except CollectorRateLimitError as error:
        return collection_failure("bluesky", query, limit, error, 429)
    except CollectorError as error:
        return collection_failure("bluesky", query, limit, error, 502)


@app.get("/api/collect/bluesky")
def collect_bluesky(
    query: str = Query(min_length=1, max_length=512),
    limit: int = Query(default=50, ge=1, le=100),
):
    """Retrieve a bounded, unauthenticated set of public Bluesky posts."""
    return collect_bluesky_or_error(query, limit)


@app.get("/api/sources")
def list_sources() -> dict[str, Any]:
    return {"sources": source_catalog()}


@app.get("/api/collect/{source}")
def collect_public_source(
    source: str,
    query: str = Query(default="", max_length=512),
    limit: int = Query(default=50, ge=1, le=100),
):
    if source not in (*SOURCE_IDS, "all"):
        raise HTTPException(status_code=404, detail="Unknown public source.")
    try:
        return collection_details(source, query, limit, collect_source(source, query, limit=limit))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except CollectorRateLimitError as error:
        return collection_failure(source, query, limit, error, 429)
    except (CollectorError, OSError) as error:
        return collection_failure(source, query, limit, error, 502)


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
        "events": [event.model_dump() for event in events_by_id.values()],
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
