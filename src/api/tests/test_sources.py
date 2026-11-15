import unittest
from unittest.mock import patch

import httpx

from src.api.main import app
from src.collectors.bluesky import CollectorError, CollectorRateLimitError
from src.collectors.public import SOURCE_IDS


class SourceApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_catalog_exposes_all_sources_and_dashboard_options(self):
        catalog = (await self.client.get("/api/sources")).json()["sources"]
        self.assertEqual({source["id"] for source in catalog}, {"all", "bluesky", "hackernews", "bbc", "guardian", "aljazeera", "context"})
        context = next(source for source in catalog if source["id"] == "context")
        self.assertFalse(context["included_in_all"])
        from src.collectors.public import SOURCE_IDS
        self.assertNotIn("context", SOURCE_IDS)
        dashboard = (await self.client.get("/")).text
        for source in catalog:
            self.assertIn(f'value="{source["id"]}"', dashboard)

    async def test_collect_routes_and_empty_feed_query(self):
        with patch("src.api.main.collect_source", return_value={"events": []}) as collector:
            response = await self.client.get("/api/collect/bbc?limit=10")
            self.assertEqual(response.status_code, 200)
            collector.assert_called_once_with("bbc", "", limit=10)

    async def test_input_validation_and_unknown_sources(self):
        for path, status in (("/api/collect/unknown?query=test", 404), ("/api/collect/bbc?limit=101", 422),
                             ("/api/collect/hackernews", 400), ("/api/collect/all", 400)):
            self.assertEqual((await self.client.get(path)).status_code, status)

    async def test_upstream_errors_have_actionable_status_codes(self):
        for error, status in ((CollectorRateLimitError("rate limited"), 429), (CollectorError("offline"), 502)):
            with patch("src.api.main.collect_source", side_effect=error):
                response = await self.client.get("/api/collect/hackernews?query=test")
                self.assertEqual(response.status_code, status)
                row = response.json()["collection"]["sources"][0]
                self.assertEqual(row["name"], "Hacker News")
                self.assertEqual(row["status"], "error")
                self.assertIsNone(row["available_events"])

    async def test_zero_results_keep_the_searched_source_and_query(self):
        with patch("src.api.main.collect_source", return_value={"source": "bbc_rss", "events": [], "fetched_posts": 20}):
            response = await self.client.get("/api/collect/bbc?query=rare%20phrase&limit=10")
        data = response.json()
        self.assertEqual(data["query"], "rare phrase")
        self.assertEqual(data["requested_limit"], 10)
        self.assertTrue(data["search_completed_at"])
        row = data["sources"][0]
        self.assertEqual(row["name"], "BBC News — World")
        self.assertEqual(row["available_events"], 0)
        self.assertEqual(row["status"], "ok")
        self.assertIn("rss", row["url"])

    async def test_total_failure_preserves_every_attempted_source(self):
        with patch("src.collectors.public.collect_posts", side_effect=CollectorError("offline")), \
             patch("src.collectors.public.collect_hackernews", side_effect=CollectorError("offline")), \
             patch("src.collectors.public.collect_feed", side_effect=CollectorError("offline")):
            response = await self.client.get("/api/collect/all?query=topic")
        self.assertEqual(response.status_code, 502)
        data = response.json()["collection"]
        self.assertEqual({row["id"] for row in data["sources"]}, set(SOURCE_IDS))
        self.assertTrue(all(row["status"] == "error" and row["available_events"] is None for row in data["sources"]))
        self.assertNotIn("context", {row["id"] for row in data["sources"]})

    async def test_combined_zero_results_are_successful_searches_not_failures(self):
        from src.collectors.bluesky import CollectionResult
        empty = CollectionResult("empty", "topic", 10, 0, 0, 0, [], [])
        with patch("src.collectors.public.collect_posts", return_value=empty), \
             patch("src.collectors.public.collect_hackernews", return_value=empty), \
             patch("src.collectors.public.collect_feed", return_value=empty):
            response = await self.client.get("/api/collect/all?query=topic&limit=10")
        self.assertEqual(response.status_code, 200)
        rows = response.json()["sources"]
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(row["status"] == "ok" and row["available_events"] == 0 for row in rows))
