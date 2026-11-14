import unittest

import httpx

from src.api.server import app


class AnalysisApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://localhost",
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_health_route(self):
        response = await self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "noise-decoder-api"})

    async def test_analyze_returns_engine_report(self):
        response = await self.client.post(
            "/analyze",
            json={"events": [], "actor_graph": {"nodes": [], "edges": []}},
        )

        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report["status"], "insufficient_data")
        self.assertIn("communities", report)
        self.assertIn("limitations", report)

    async def test_discover_route_returns_public_search_results(self):
        from unittest.mock import AsyncMock, patch

        with patch(
            "src.api.server.discover_related_posts",
            new=AsyncMock(return_value={"events": [{"platform": "bluesky"}], "queries_run": 1, "limitations": []}),
        ) as discover:
            response = await self.client.post("/discover", json={"events": [{"text": "seed"}]})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["events"][0]["platform"], "bluesky")
        discover.assert_awaited_once_with([{"text": "seed"}])

    async def test_extension_cors_preflight_is_allowed(self):
        origin = "chrome-extension://local-test-extension"
        response = await self.client.options(
            "/analyze",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], origin)
        self.assertIn("POST", response.headers["access-control-allow-methods"])

    async def test_invalid_json_returns_bad_request(self):
        response = await self.client.post(
            "/analyze",
            content=b"{not valid json",
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("valid UTF-8 JSON", response.json()["detail"])

    async def test_non_object_json_returns_bad_request(self):
        response = await self.client.post("/analyze", json=["not", "an", "object"])

        self.assertEqual(response.status_code, 400)
        self.assertIn("JSON object", response.json()["detail"])

    async def test_non_json_content_type_is_rejected(self):
        response = await self.client.post(
            "/analyze",
            content="events",
            headers={"Content-Type": "text/plain"},
        )

        self.assertEqual(response.status_code, 415)

    async def test_request_body_limit_is_enforced(self):
        response = await self.client.post(
            "/analyze",
            content=b" " * (5 * 1024 * 1024 + 1),
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 413)

    async def test_non_loopback_host_is_rejected(self):
        response = await self.client.get("/health", headers={"Host": "not-local.example"})

        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
