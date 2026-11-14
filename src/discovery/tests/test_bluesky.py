import asyncio
import unittest

import httpx

from src.discovery.bluesky import SEARCH_URL, discover_related_posts


class BlueskyDiscoveryTests(unittest.TestCase):
    def test_searches_seed_text_and_maps_public_posts(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(200, json={"posts": [{
                "uri": "at://did:plc:author/app.bsky.feed.post/abc",
                "author": {"did": "did:plc:author", "handle": "reporter.example"},
                "record": {"text": "A related public update", "createdAt": "2026-01-01T00:00:00Z"},
            }]})

        result = asyncio.run(discover_related_posts(
            [{"text": "A long enough seed story about the important public event"}],
            transport=httpx.MockTransport(handler),
        ))

        self.assertEqual(len(requests), 1)
        self.assertEqual(str(requests[0].url).split("?")[0], SEARCH_URL)
        self.assertEqual(result["events"][0]["platform"], "bluesky")
        self.assertEqual(result["events"][0]["actor_id"], "bluesky:did:plc:author")
        self.assertEqual(result["events"][0]["url"], "https://bsky.app/profile/reporter.example/post/abc")
        self.assertIn("public Bluesky posts", result["limitations"][0])

    def test_empty_seeds_do_not_make_network_requests(self):
        result = asyncio.run(discover_related_posts([]))

        self.assertEqual(result["events"], [])
        self.assertEqual(result["queries_run"], 0)

    def test_search_failure_returns_limited_result(self):
        def handler(request):
            return httpx.Response(503)

        result = asyncio.run(discover_related_posts(
            [{"text": "A sufficiently long public seed text to search"}],
            transport=httpx.MockTransport(handler),
        ))

        self.assertEqual(result["events"], [])
        self.assertTrue(any("failed" in limitation for limitation in result["limitations"]))


if __name__ == "__main__":
    unittest.main()
