import os
import unittest
from unittest.mock import patch

from src.collectors import reddit
from src.collectors.bluesky import CollectorError, CollectorRateLimitError


class FakeResponse:
    status_code = 200
    content = b"{}"

    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            request = httpx.Request("GET", "https://oauth.reddit.com/search")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("status", request=request, response=response)

    def json(self):
        return self.payload


class RedditCollectorTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "REDDIT_CLIENT_ID": "test-id",
            "REDDIT_CLIENT_SECRET": "test-secret",
            "REDDIT_USER_AGENT": "NoiseDecoder/1.0 test-contact@example.org",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.previous_token = reddit._cached_token
        reddit._cached_token = ("mock-token", 10**12)
        self.addCleanup(setattr, reddit, "_cached_token", self.previous_token)

    def test_public_submission_search_normalizes_records_and_skips_deleted(self):
        payload = {"data": {"children": [
            {"data": {"id": "abc", "author": "alice", "title": "Climate update", "subreddit": "news",
                       "created_utc": 1763114400, "permalink": "/r/news/comments/abc/climate/",
                       "url": "https://example.org/article?utm_source=reddit", "selftext": "A public summary."}},
            {"data": {"id": "gone", "author": "[deleted]", "title": "Deleted", "subreddit": "news",
                       "created_utc": 1763114400, "permalink": "/r/news/comments/gone/deleted/", "url": "https://example.org"}},
        ]}}
        with patch.object(reddit.httpx, "get", return_value=FakeResponse(payload)) as request:
            result = reddit.collect_reddit("climate", limit=4)
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0]["id"], "reddit:abc")
        self.assertEqual(result.events[0]["actor_id"], "reddit:alice")
        self.assertEqual(result.events[0]["publisher"], "r/news")
        self.assertEqual(result.events[0]["urls"], ["https://example.org/article"])
        self.assertEqual(result.skipped_posts, 1)
        self.assertIn("limit=4", request.call_args.args[0])
        self.assertIn("Bearer mock-token", request.call_args.kwargs["headers"]["Authorization"])

    def test_token_exchange_uses_client_credentials_and_user_agent(self):
        reddit._cached_token = None
        with patch.object(reddit.httpx, "post", return_value=FakeResponse({"access_token": "fresh", "expires_in": 3600})) as request:
            self.assertEqual(reddit._access_token(), "fresh")
        self.assertEqual(request.call_args.kwargs["auth"], ("test-id", "test-secret"))
        self.assertEqual(request.call_args.kwargs["headers"]["User-Agent"], os.environ["REDDIT_USER_AGENT"])

    def test_rate_limit_is_reported_and_missing_credentials_fail_closed(self):
        with patch.object(reddit.httpx, "get", return_value=FakeResponse({}, status_code=429)):
            with self.assertRaises(CollectorRateLimitError):
                reddit.collect_reddit("climate")
        with patch.dict(os.environ, {"REDDIT_CLIENT_ID": "", "REDDIT_CLIENT_SECRET": ""}):
            with self.assertRaises(CollectorError):
                reddit.collect_reddit("climate")


if __name__ == "__main__":
    unittest.main()
