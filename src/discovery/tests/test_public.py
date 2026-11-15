import unittest
from unittest.mock import AsyncMock, patch

from src.collectors.bluesky import CollectionResult, CollectorError
from src.discovery.public import discover_related_posts


class PublicDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_maps_hackernews_links_and_preserves_bluesky_results(self):
        hn = CollectionResult("hackernews", "seed", 25, 1, 0, 0, [{
            "id": "hackernews:1", "platform": "hackernews", "actor_id": "hackernews:alice",
            "timestamp": "2026-11-14T10:00:00Z", "text": "Public story",
            "urls": ["https://example.org/story"], "source_url": "https://news.ycombinator.com/item?id=1",
        }], [])
        with patch("src.discovery.public.discover_bluesky", new=AsyncMock(return_value={"events": [{"post_id": "bsky:1"}], "queries_run": 1, "limitations": []})), \
             patch("src.discovery.public.collect_hackernews", return_value=hn):
            result = await discover_related_posts([{"text": "A sufficiently long seed text"}])
        self.assertEqual(len(result["events"]), 2)
        self.assertEqual(result["events"][1]["links"], ["https://example.org/story"])
        self.assertEqual(result["queries_run"], 2)

    async def test_failed_source_does_not_discard_the_other_source(self):
        with patch("src.discovery.public.discover_bluesky", new=AsyncMock(return_value={"events": [{"post_id": "bsky:1"}], "queries_run": 1, "limitations": []})), \
             patch("src.discovery.public.collect_hackernews", side_effect=CollectorError("offline")):
            result = await discover_related_posts([{"text": "A sufficiently long seed text"}])
        self.assertEqual(result["events"], [{"post_id": "bsky:1"}])
        self.assertTrue(any("Hacker News search request(s) failed" in message for message in result["limitations"]))

    async def test_empty_seeds_make_no_requests(self):
        with patch("src.discovery.public.discover_bluesky") as bluesky, patch("src.discovery.public.collect_hackernews") as hn:
            result = await discover_related_posts([])
            self.assertEqual(result["queries_run"], 0)
            bluesky.assert_not_called()
            hn.assert_not_called()

    async def test_combined_result_limit_is_shared_fairly(self):
        def results(prefix):
            return {"events": [{"post_id": f"{prefix}:{i}"} for i in range(100)], "queries_run": 5, "limitations": []}
        with patch("src.discovery.public.discover_bluesky", new=AsyncMock(return_value=results("bsky"))), \
             patch("src.discovery.public._hackernews", new=AsyncMock(return_value=results("hn"))):
            result = await discover_related_posts([{"text": "A sufficiently long seed text"}])
        self.assertEqual(len(result["events"]), 100)
        self.assertEqual(sum(event["post_id"].startswith("hn:") for event in result["events"]), 50)
