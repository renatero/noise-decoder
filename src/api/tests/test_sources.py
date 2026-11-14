import unittest
from unittest.mock import patch

import httpx

from src.api.main import app
from src.collectors.bluesky import CollectorError, CollectorRateLimitError


class SourceApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_catalog_exposes_all_sources_and_dashboard_options(self):
        catalog = (await self.client.get("/api/sources")).json()["sources"]
        self.assertEqual({source["id"] for source in catalog}, {"all", "bluesky", "hackernews", "bbc", "guardian", "aljazeera"})
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
