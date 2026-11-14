import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from src.collectors.bluesky import CollectionResult, CollectorRateLimitError, canonicalize_url, collect_posts
from src.collectors.snapshot import save_snapshot


class FakeResponse:
    def __init__(self, payload):
        self.payload = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def read(self, *args, **kwargs):
        return self.payload.read(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def post(uri, *, did="did:plc:alice", text="A public post", created_at="2026-11-14T12:00:00+02:00"):
    return {
        "uri": uri,
        "indexedAt": "2026-11-14T10:01:00Z",
        "author": {"did": did, "handle": "alice.bsky.social"},
        "record": {
            "text": text,
            "createdAt": created_at,
            "facets": [{"features": [{"$type": "app.bsky.richtext.facet#link", "uri": "https://EXAMPLE.org/story/?b=2&utm_source=x&a=1#top"}]}],
        },
    }


class BlueskyCollectorTests(unittest.TestCase):
    def test_collection_normalizes_deduplicates_and_falls_back_to_index_time(self):
        payload = {
            "posts": [
                post("at://did:plc:alice/app.bsky.feed.post/first"),
                post("at://did:plc:alice/app.bsky.feed.post/first"),
                post("at://did:plc:bob/app.bsky.feed.post/second", did="did:plc:bob", created_at="invalid"),
            ]
        }
        with patch("src.collectors.bluesky.urlopen", return_value=FakeResponse(payload)):
            result = collect_posts("public news", limit=10)

        self.assertEqual(result.fetched_posts, 3)
        self.assertEqual(result.deduplicated_posts, 1)
        self.assertEqual(result.skipped_posts, 0)
        self.assertEqual(len(result.events), 2)
        event = result.events[0]
        self.assertEqual(event["id"], "at://did:plc:alice/app.bsky.feed.post/first")
        self.assertEqual(event["actor_id"], "bluesky:did:plc:alice")
        self.assertEqual(event["timestamp"], "2026-11-14T10:00:00.000Z")
        self.assertEqual(event["urls"], ["https://example.org/story?a=1&b=2"])
        self.assertEqual(event["source_url"], "https://bsky.app/profile/alice.bsky.social/post/first")
        self.assertEqual(result.events[1]["timestamp"], "2026-11-14T10:01:00.000Z")

    def test_rate_limit_is_reported_clearly(self):
        error = HTTPError("https://public.api.bsky.app", 429, "Too many requests", None, None)
        with patch("src.collectors.bluesky.urlopen", side_effect=error):
            with self.assertRaises(CollectorRateLimitError):
                collect_posts("public news", limit=10)

    def test_url_canonicalization_removes_tracking(self):
        self.assertEqual(
            canonicalize_url("https://EXAMPLE.org:443/path/?utm_source=x&b=2&a=1#section"),
            "https://example.org/path?a=1&b=2",
        )

    def test_snapshot_is_labelled_and_reloads_as_json(self):
        result = CollectionResult("bluesky_public_appview", "news", 1, 1, 0, 0, [], ["bounded"])
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "snapshot.json"
            with patch("src.collectors.snapshot.collect_posts", return_value=result):
                snapshot = save_snapshot("news", limit=1, destination=destination)
            self.assertEqual(snapshot["snapshot_type"], "public_bluesky_search")
            self.assertTrue(destination.exists())
            self.assertEqual(json.loads(destination.read_text(encoding="utf-8"))["query"], "news")
