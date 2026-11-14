"""Create a labelled, offline Bluesky demo snapshot from the bounded collector."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from src.collectors.bluesky import APPVIEW_BASE_URL, collect_posts


def save_snapshot(query: str, *, limit: int, destination: Path) -> dict[str, object]:
    result = collect_posts(query, limit=limit).to_dict()
    snapshot: dict[str, object] = {
        "snapshot_type": "public_bluesky_search",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_endpoint": APPVIEW_BASE_URL,
        "notice": "Public, bounded search snapshot for an offline demo; it is not a complete account or platform record.",
        **result,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Bluesky search phrase")
    parser.add_argument("--limit", type=int, default=50, help="Maximum posts to collect (1-100)")
    parser.add_argument("--output", type=Path, default=Path("datasets/bluesky_public_snapshot.json"))
    args = parser.parse_args()
    snapshot = save_snapshot(args.query, limit=args.limit, destination=args.output)
    print(f"Saved {len(snapshot['events'])} public posts to {args.output}")


if __name__ == "__main__":
    main()
