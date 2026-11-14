import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import httpx

from src.collectors import context
from src.collectors.bluesky import CollectorError, CollectorRateLimitError

NOW = datetime(2026, 11, 14, 12, tzinfo=timezone.utc).timestamp()


def article(identifier="a", **overrides):
    return {"id": identifier, "story_id": identifier, "url": f"https://example.org/{identifier}?utm_source=test",
            "title": "AI regulation update", "description": "<p>Policy news.</p>", "language": "en",
            "published_at": "2026-11-14T10:00:00Z", "source": {"domain": "example.org", "name": "Example"}, **overrides}


def payload(*articles):
    return {"data": list(articles), "has_more": True, "key_metadata": {"credits_consumed": 1, "credits_remaining": 50000}}


class ContextCollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "state.sqlite3")
        self.env = patch.dict(os.environ, {"CONTEXT_API_KEY": "test-key", "CONTEXT_STATE_PATH": self.path,
                                          "CONTEXT_DAILY_REQUEST_LIMIT": "20"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.clock = patch.object(context.time, "time", return_value=NOW)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def test_dates_metadata_story_and_url_deduplication(self):
        data = payload(article(), article("b", story_id="a"), article("c", url="https://example.org/a"),
                       article("d", published_at=None), article("e", published_at="2020-01-01T00:00:00Z"),
                       article("f", published_at="2026-11-15T00:00:00Z"), article("g", language="es"), None)
        with patch.object(context, "_fetch", return_value=data) as fetch:
            result = context.collect_news(" AI regulation ")
        self.assertEqual(len(result["events"]), 1)
        self.assertEqual(result["deduplicated_posts"], 2)
        self.assertEqual(result["skipped_posts"], 5)
        self.assertEqual(result["events"][0]["source_url"], "https://example.org/a")
        self.assertEqual(result["events"][0]["publisher"], "Example")
        self.assertEqual(result["events"][0]["story_id"], "a")
        self.assertEqual(result["events"][0]["record_type"], "publisher_article")
        self.assertNotIn("<p>", result["events"][0]["text"])
        self.assertNotIn("credits_remaining", json.dumps(result))
        request = fetch.call_args.args[0]
        self.assertEqual(request["filterBy"]["articleLanguage"], ["en"])
        self.assertEqual(request["filterBy"]["date"]["to"], int(NOW * 1000))

    def test_cache_avoids_spending_and_expires(self):
        with patch.object(context, "_fetch", return_value=payload(article())) as fetch:
            first = context.collect_news("topic")
            cached = context.collect_news("topic")
            self.assertFalse(first["cached"])
            self.assertTrue(cached["cached"])
            self.assertEqual(cached["credits_consumed"], 0)
            self.assertEqual(fetch.call_count, 1)
            with patch.object(context.time, "time", return_value=NOW + 601):
                context.collect_news("topic")
            self.assertEqual(fetch.call_count, 2)

    def test_daily_budget_persists_and_cached_results_stay_available(self):
        with patch.dict(os.environ, {"CONTEXT_DAILY_REQUEST_LIMIT": "1"}), patch.object(context, "_fetch", return_value=payload(article())) as fetch:
            context.collect_news("topic")
            # Every collector invocation opens a new database connection.
            self.assertTrue(context.collect_news("topic")["cached"])
            with self.assertRaisesRegex(CollectorRateLimitError, "daily"):
                context.collect_news("other topic")
            self.assertEqual(fetch.call_count, 1)
            with patch.object(context.time, "time", return_value=NOW + 86400):
                context.collect_news("next day")
            self.assertEqual(fetch.call_count, 2)

    def test_burst_budget_and_failures_do_not_trigger_retries(self):
        with patch.object(context, "_fetch", side_effect=CollectorError("offline")) as fetch:
            for i in range(4):
                with self.assertRaises(CollectorError):
                    context.collect_news(f"topic {i}")
            with self.assertRaisesRegex(CollectorRateLimitError, "four"):
                context.collect_news("topic 5")
            self.assertEqual(fetch.call_count, 4)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 4)

    def test_missing_key_bad_inputs_and_storage_fail_closed(self):
        with patch.object(context, "_fetch") as fetch:
            for kwargs in ({"query": " "}, {"query": "x", "limit": 11}, {"query": "x", "days": 31}):
                with self.assertRaises(ValueError):
                    context.collect_news(**kwargs)
            with patch.dict(os.environ, {"CONTEXT_API_KEY": ""}):
                with self.assertRaises(context.ContextUnavailable):
                    context.collect_news("topic")
            with patch.dict(os.environ, {"CONTEXT_STATE_PATH": self.temp.name}):
                with self.assertRaises(context.ContextUnavailable):
                    context.collect_news("topic")
            fetch.assert_not_called()

    def test_http_errors_do_not_expose_key_or_provider_error_body(self):
        for status, kind in ((401, context.ContextUnavailable), (403, context.ContextUnavailable),
                             (402, context.ContextUnavailable), (429, CollectorRateLimitError), (500, CollectorError)):
            response = httpx.Response(status, request=httpx.Request("POST", context.SEARCH_URL),
                                      json={"message": "test-key private upstream details"})
            with self.subTest(status=status), patch.object(context.httpx, "stream") as stream:
                stream.return_value.__enter__.return_value = response
                with self.assertRaises(kind) as caught:
                    context._fetch({}, "test-key")
                self.assertNotIn("test-key", str(caught.exception))
                self.assertNotIn("private", str(caught.exception))
                self.assertFalse(stream.call_args.kwargs["follow_redirects"])

    def test_response_shape_and_size_are_bounded(self):
        for content in (b"invalid", b'{"data": {}}', b"x" * (context.MAX_RESPONSE_BYTES + 1)):
            response = httpx.Response(200, request=httpx.Request("POST", context.SEARCH_URL), content=content)
            with patch.object(context.httpx, "stream") as stream:
                stream.return_value.__enter__.return_value = response
                with self.assertRaises(CollectorError):
                    context._fetch({}, "test-key")
