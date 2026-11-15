import unittest
from unittest.mock import patch

import httpx

from src.api.main import app
from src.collectors.context import ContextUnavailable
from src.collectors.bluesky import CollectorError, CollectorRateLimitError


class ContextApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost")
        self.headers = {"X-NoiseDecoder-Request": "1", "Origin": "http://localhost"}
        self.addAsyncCleanup(self.client.aclose)

    async def test_explicit_post_guard_and_validation(self):
        with patch("src.api.main.collect_context_news", return_value={"events": []}) as collect:
            for headers in ({}, {**self.headers, "Origin": "https://evil.example"}):
                response = await self.client.post("/api/collect/context", json={"query": "ai"}, headers=headers)
                self.assertEqual(response.status_code, 403)
            collect.assert_not_called()
            response = await self.client.post("/api/collect/context", json={"query": "ai"}, headers=self.headers)
            self.assertEqual(response.status_code, 200)
            collect.assert_called_once_with("ai", limit=10, days=7)
            for body in ({"query": "ai", "limit": 11}, {"query": "ai", "days": 31}, {"query": ""}):
                self.assertEqual((await self.client.post("/api/collect/context", json=body, headers=self.headers)).status_code, 422)
            self.assertEqual((await self.client.get("/api/collect/context?query=ai")).status_code, 404)

    async def test_actionable_errors(self):
        for error, status in ((ContextUnavailable("not configured"), 503), (CollectorRateLimitError("budget used"), 429),
                              (CollectorError("offline"), 502), (ValueError("empty query"), 400)):
            with patch("src.api.main.collect_context_news", side_effect=error):
                response = await self.client.post("/api/collect/context", json={"query": "ai"}, headers=self.headers)
                self.assertEqual(response.status_code, status)

    async def test_empty_cached_news_keeps_provider_and_date_window(self):
        with patch("src.api.main.collect_context_news", return_value={"source": "context_news", "events": [], "cached": True, "credits_consumed": 0}):
            response = await self.client.post("/api/collect/context", json={"query": "rare phrase", "days": 30}, headers=self.headers)
        data = response.json()
        self.assertEqual(data["sources"][0]["name"], "Context.dev news index")
        self.assertIn("30 days", data["sources"][0]["scope"])
        self.assertEqual(data["sources"][0]["available_events"], 0)
        self.assertTrue(data["cached"])

    async def test_news_metadata_survives_import_and_is_excluded_from_analysis(self):
        news = [{"id": f"context:{actor}{i}", "platform": "news_context", "actor_id": actor,
                 "timestamp": "2026-11-14T10:00:00Z", "text": "Before it's too late, this danger threatens us.", "urls": [f"https://example.org/{i}"],
                 "publisher": actor, "record_type": "publisher_article", "story_id": str(i), "language": "en"}
                for actor in ("publisher:a", "publisher:b") for i in range(2)]
        imported = (await self.client.post("/api/import", json={"events": news})).json()
        self.assertEqual(imported["events"][0]["publisher"], "publisher:a")
        self.assertEqual(imported["events"][0]["story_id"], "0")
        report = (await self.client.post("/api/analyze", json={"events": news})).json()
        self.assertEqual(report["status"], "news_context")
        self.assertEqual(report["statistics"]["news_articles"], 4)
        self.assertEqual(report["statistics"]["repeated_relationships"], 0)
        self.assertEqual(report["nodes"], [])
        self.assertEqual(report["technique_analysis"]["techniques"], [])
        self.assertEqual(report["news_context_technique_analysis"]["techniques"][0]["id"], "appeal_to_fear_prejudice")
        self.assertEqual(report["news_context_technique_analysis"]["score_adjustment"]["score_delta"], 0)
        social = {**news[0], "id": "social:a", "platform": "bluesky", "actor_id": "alice"}
        report = (await self.client.post("/api/analyze", json={"events": [*news, social]})).json()
        self.assertEqual(report["status"], "insufficient_data")
        self.assertEqual(report["statistics"]["events_observed"], 1)
        self.assertEqual(len(report["news_context"]), 4)
