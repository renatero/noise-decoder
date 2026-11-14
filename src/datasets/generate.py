"""Generate deterministic coordinated and benign demonstration datasets."""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "datasets"
BASE_TIME = datetime(2026, 11, 14, 8, 0, tzinfo=timezone.utc)


def iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def event(
    identifier: str,
    actor: str,
    timestamp: datetime,
    text: str,
    urls: list[str],
    scenario: str,
) -> dict[str, Any]:
    return {
        "id": identifier,
        "platform": "bluesky",
        "actor_id": actor,
        "timestamp": iso(timestamp),
        "text": text,
        "urls": urls,
        "source_url": f"https://demo.invalid/{scenario}/{identifier}",
        "demo": {"synthetic": True, "scenario": scenario},
    }


def suspicious_dataset(seed: int = 20261114) -> list[dict[str, Any]]:
    """Return recurring, synchronized URL-sharing bursts plus background noise."""
    rng = random.Random(seed)
    coordinated = [f"demo:coordinated-{index:02d}" for index in range(1, 13)]
    background = [f"demo:background-{index:03d}" for index in range(1, 91)]
    events: list[dict[str, Any]] = []
    counter = 1
    themes = [
        ("transport", "https://demo.example/briefing/transport-{burst}"),
        ("energy", "https://demo.example/briefing/energy-{burst}"),
    ]
    templates = [
        "New {theme} briefing is worth sharing: {url}",
        "Please read this {theme} update and pass it on: {url}",
        "Useful {theme} context in this briefing: {url}",
    ]
    for burst in range(6):
        theme, url_template = themes[burst % len(themes)]
        url = url_template.format(burst=burst + 1)
        burst_start = BASE_TIME + timedelta(hours=burst * 4)
        for actor in coordinated:
            timestamp = burst_start + timedelta(seconds=rng.randrange(0, 8 * 60))
            text = rng.choice(templates).format(theme=theme, url=url)
            events.append(event(f"demo-suspicious-{counter:04d}", actor, timestamp, text, [url], "coordinated"))
            counter += 1
    for index in range(264):
        actor = rng.choice(background)
        topic = rng.choice(["weather", "culture", "local sport", "science", "music", "community"])
        url = f"https://demo.example/independent/{topic.replace(' ', '-')}/{index:03d}"
        timestamp = BASE_TIME + timedelta(minutes=rng.randrange(0, 24 * 60))
        events.append(
            event(
                f"demo-suspicious-{counter:04d}",
                actor,
                timestamp,
                f"An independent note about {topic} from a synthetic demonstration account.",
                [url],
                "coordinated",
            )
        )
        counter += 1
    return sorted(events, key=lambda item: item["timestamp"])


def benign_dataset(seed: int = 20261115) -> list[dict[str, Any]]:
    """Return independent breaking-news reactions with one coincidental burst."""
    rng = random.Random(seed)
    actors = [f"demo:benign-{index:03d}" for index in range(1, 151)]
    events: list[dict[str, Any]] = []
    counter = 1
    breaking_url = "https://demo.example/news/harbour-service-update"
    reactions = [
        "Following the harbour service update; hoping for a quick resolution.",
        "Sharing the harbour update for people travelling today.",
        "Checking the harbour report before making plans this afternoon.",
        "This harbour news affects a lot of local journeys today.",
    ]
    burst_start = BASE_TIME + timedelta(hours=5)
    for actor in actors[:54]:
        events.append(
            event(
                f"demo-benign-{counter:04d}",
                actor,
                burst_start + timedelta(seconds=rng.randrange(0, 35 * 60)),
                rng.choice(reactions),
                [breaking_url],
                "benign",
            )
        )
        counter += 1
    for index in range(282):
        actor = rng.choice(actors)
        topic = rng.choice(["weather", "school event", "football", "museum", "garden", "health advice"])
        url = f"https://demo.example/ordinary/{topic.replace(' ', '-')}/{index:03d}"
        events.append(
            event(
                f"demo-benign-{counter:04d}",
                actor,
                BASE_TIME + timedelta(minutes=rng.randrange(0, 24 * 60)),
                f"A synthetic independent reaction about {topic}.",
                [url],
                "benign",
            )
        )
        counter += 1
    return sorted(events, key=lambda item: item["timestamp"])


def write_datasets(destination: Path = OUTPUT_DIR) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for scenario, build in (("synthetic_coordinated", suspicious_dataset), ("synthetic_benign", benign_dataset)):
        events = build()
        payload = {
            "dataset_type": "synthetic_demonstration",
            "scenario": scenario,
            "notice": "All actors, events, URLs, and source links in this file are synthetic demonstration data.",
            "event_count": len(events),
            "events": events,
        }
        (destination / f"{scenario}.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write_datasets()
