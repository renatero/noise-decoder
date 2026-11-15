#!/usr/bin/env python3
"""Fetch the licensed QCRI ProBel research benchmark without Git/LFS tooling."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPOSITORY = "QCRI/ProBel"
REVISION = "main"
LICENSE = "CC-BY-NC-SA-4.0"
FILES = (
    "LICENSE",
    "README.md",
    "label_taxonomy.json",
    "english/train.jsonl",
    "english/dev.jsonl",
    "english/test.jsonl",
    "arabic/train.jsonl",
    "arabic/dev.jsonl",
    "arabic/test.jsonl",
)


def url_for(filename: str) -> str:
    return f"https://huggingface.co/datasets/{REPOSITORY}/resolve/{REVISION}/{filename}?download=true"


def download(filename: str, target: Path, overwrite: bool) -> dict[str, str | int]:
    destination = target / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not overwrite:
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        return {"path": filename, "bytes": destination.stat().st_size, "sha256": digest, "status": "existing"}

    temporary = destination.with_suffix(destination.suffix + ".part")
    request = Request(url_for(filename), headers={"User-Agent": "CoordinationRadarResearch/1.0"})
    digest = hashlib.sha256()
    total = 0
    try:
        with urlopen(request, timeout=60) as response, temporary.open("wb") as output:  # noqa: S310 - fixed HF URL
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                digest.update(chunk)
                total += len(chunk)
    except (HTTPError, URLError, TimeoutError) as error:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Could not download {filename}: {error}") from error
    temporary.replace(destination)
    return {"path": filename, "bytes": total, "sha256": digest.hexdigest(), "status": "downloaded"}


def validate_jsonl(target: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for filename in FILES:
        if not filename.endswith(".jsonl"):
            continue
        rows = 0
        with (target / filename).open(encoding="utf-8") as stream:
            for row_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as error:
                    raise RuntimeError(f"Invalid JSON in {filename}, line {row_number}") from error
                if not isinstance(value, dict):
                    raise RuntimeError(f"Expected an object in {filename}, line {row_number}")
                rows += 1
        counts[filename] = rows
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/external/probel"), help="Local dataset directory")
    parser.add_argument("--force", action="store_true", help="Re-download existing files")
    args = parser.parse_args()

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    try:
        files = [download(filename, output, args.force) for filename in FILES]
        rows = validate_jsonl(output)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1
    provenance = {
        "dataset": REPOSITORY,
        "revision": REVISION,
        "source": f"https://huggingface.co/datasets/{REPOSITORY}",
        "license": LICENSE,
        "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "files": files,
        "jsonl_rows": rows,
        "notice": "Research benchmark only. Labels annotate text techniques and must not be used as factual findings about people, publishers, or intent.",
    }
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "jsonl_rows": rows, "files": len(files)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
