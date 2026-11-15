import json
import unittest
from unittest.mock import patch

import httpx

from src.collectors.bluesky import CollectorError, CollectorRateLimitError
from src.collectors import news
from src.collectors.public import collect_source


def item(title="Climate policy announced", link="https://example.org/story?at_medium=RSS", date="Sat, 14 Nov 2026 10:00:00 +0200"):
    return f"<item><title>{title}</title><link>{link}</link><pubDate>{date}</pubDate><description><![CDATA[<p>A public policy update.</p>]]></description></item>"


def feed(*items):
    return ("<rss><channel>" + "".join(items) + "</channel></rss>").encode()


def hit(identifier="123", **overrides):
    return {"objectID": identifier, "author": "alice", "title": "Climate &amp; science",
            "created_at": "2026-11-14T10:00:00+02:00", "url": "https://example.org/story?utm_source=hn", **overrides}


class NewsCollectorTests(unittest.TestCase):
    def setUp(self):
        news._feed_cache.clear()

    def test_feed_preserves_publisher_timestamp_attribution_and_canonical_url(self):
        with patch.object(news, "fetch_bytes", return_value=feed(item(), item(), item(date="bad"))):
            result = news.collect_feed("bbc", "climate")
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.deduplicated_posts, 1)
        self.assertEqual(result.skipped_posts, 1)
        event = result.events[0]
        self.assertEqual(event["actor_id"], "publisher:bbc")
        self.assertEqual(event["record_type"], "publisher_article")
        self.assertEqual(event["timestamp"], "2026-11-14T08:00:00.000Z")
        self.assertEqual(event["urls"], ["https://example.org/story"])
        self.assertNotIn("<p>", event["text"])

    def test_feed_filters_all_words_or_exact_url_and_allows_recent_headlines(self):
        with patch.object(news, "fetch_bytes", return_value=feed(item(), item("Unrelated story", "https://example.org/other"))) as fetch:
            self.assertEqual(len(news.collect_feed("bbc", "climate policy").events), 1)
            self.assertEqual(news.collect_feed("bbc", "climate unrelated").events, [])
            self.assertEqual(len(news.collect_feed("bbc", "https://example.org/story?utm_source=test").events), 1)
            self.assertEqual(len(news.collect_feed("bbc").events), 2)
            self.assertEqual(len(news.collect_feed("bbc", limit=1).events), 1)
            fetch.assert_called_once()  # Feed cached independently of the search phrase.

    def test_feed_cache_expires(self):
        with patch.object(news, "fetch_bytes", return_value=feed(item())) as fetch, patch.object(news.time, "monotonic", return_value=100) as now:
            news.collect_feed("bbc")
            now.return_value = 401
            news.collect_feed("bbc")
            self.assertEqual(fetch.call_count, 2)

    def test_invalid_feeds_are_not_cached(self):
        for body in (b"not xml", b"<html/>", b'<!DOCTYPE rss [<!ENTITY x "expanded">]><rss><channel/></rss>'):
            with self.subTest(body=body), patch.object(news, "fetch_bytes", return_value=body):
                with self.assertRaises(CollectorError):
                    news.collect_feed("bbc")
                self.assertNotIn("bbc", news._feed_cache)

    def test_missing_or_timezone_free_dates_do_not_become_collection_time(self):
        with patch.object(news, "fetch_bytes", return_value=feed(item(date=""), item(date="Sat, 14 Nov 2026 10:00:00"))):
            result = news.collect_feed("bbc")
        self.assertEqual(result.events, [])
        self.assertEqual(result.skipped_posts, 2)

    def test_hackernews_normalization_and_malformed_records(self):
        body = json.dumps({"hits": [hit(), hit(), hit("124", created_at="bad"), None, hit("125", url=42)]}).encode()
        with patch.object(news, "fetch_bytes", return_value=body) as fetch:
            result = news.collect_hackernews("climate", limit=10)
        self.assertIn("tags=story", fetch.call_args.args[0])
        self.assertEqual(result.deduplicated_posts, 1)
        self.assertEqual(result.skipped_posts, 2)
        self.assertEqual(result.events[0]["actor_id"], "hackernews:alice")
        self.assertEqual(result.events[0]["text"], "Climate & science")
        self.assertEqual(result.events[0]["source_url"], "https://news.ycombinator.com/item?id=123")
        self.assertEqual(result.events[0]["urls"], ["https://example.org/story"])
        self.assertEqual(result.events[1]["urls"], [])

    def test_hackernews_rejects_invalid_payloads(self):
        for body in (b"not json", b"[]", b'{"hits":null}'):
            with self.subTest(body=body), patch.object(news, "fetch_bytes", return_value=body):
                with self.assertRaises(CollectorError):
                    news.collect_hackernews("test")

    def test_validation_prevents_network_calls(self):
        with patch.object(news, "fetch_bytes") as fetch:
            for call in (lambda: news.collect_feed("unknown"), lambda: news.collect_feed("bbc", limit=101),
                         lambda: news.collect_hackernews(" "), lambda: news.collect_hackernews("x" * 513)):
                with self.assertRaises(ValueError):
                    call()
            fetch.assert_not_called()

    def test_http_rate_limit_errors_and_response_size_are_bounded(self):
        for status, body, expected in ((429, b"", CollectorRateLimitError), (503, b"", CollectorError),
                                        (200, b"x" * (news.MAX_RESPONSE_BYTES + 1), CollectorError)):
            response = httpx.Response(status, content=body, request=httpx.Request("GET", news.HN_SEARCH_URL))
            with self.subTest(status=status), patch.object(news.httpx, "stream") as stream:
                stream.return_value.__enter__.return_value = response
                with self.assertRaises(expected):
                    news.fetch_bytes(news.HN_SEARCH_URL)


class CombinedCollectorTests(unittest.TestCase):
    def test_partial_failure_keeps_healthy_sources_and_interleaves_with_total_limit(self):
        news._feed_cache.clear()
        with patch("src.collectors.public.collect_posts", side_effect=CollectorError("offline")), \
             patch.object(news, "fetch_bytes", side_effect=lambda url: json.dumps({"hits": [hit(), hit("124")]}).encode() if "algolia" in url else feed(item(), item("Second", "https://example.org/two"))):
            result = collect_source("all", "climate", limit=4)
        self.assertEqual(len(result["events"]), 4)
        self.assertEqual([event["actor_id"] for event in result["events"]],
                         ["hackernews:alice", "publisher:bbc", "publisher:guardian", "publisher:aljazeera"])
        self.assertEqual(result["sources"][0]["status"], "error")
        self.assertTrue(any("bluesky failed" in message for message in result["limitations"]))

    def test_total_failure_is_an_error(self):
        with patch("src.collectors.public.collect_posts", side_effect=CollectorError("offline")), \
             patch("src.collectors.public.collect_hackernews", side_effect=CollectorError("offline")), \
             patch("src.collectors.public.collect_feed", side_effect=CollectorError("offline")):
            with self.assertRaises(CollectorError):
                collect_source("all", "climate")


if __name__ == "__main__":
    unittest.main()
