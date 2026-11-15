"""Bounded live probe: usage, ten news results, one standard scrape, usage.

Run from the repository root with .venv/bin/python. Prompts without echo for
the API key; never saves credentials, request headers, or article bodies.
No retries, subscriptions, monitors, or production writes.
"""

import getpass
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.api.main import Event
from src.collectors.bluesky import canonicalize_url, normalize_timestamp


def main():
    recent_only = "--recent-only" in sys.argv
    key = getpass.getpass("Context API key (hidden): ").strip()
    if not key:
        raise SystemExit("An API key is required.")
    report = {"tested_at": datetime.now(timezone.utc).isoformat(), "calls": []}
    output = Path(__file__).with_name("context-recent-test.json" if recent_only else "context-live-test.json")

    def emit(value):
        print(json.dumps(value, ensure_ascii=False).replace(key, "[REDACTED]"), flush=True)

    def call(client, method, path, body=None):
        started = time.monotonic()
        record = {"method": method, "path": path}
        report["calls"].append(record)
        try:
            response = client.request(method, path, json=body) if body else client.request(method, path)
            record.update(status=response.status_code, seconds=round(time.monotonic() - started, 3))
            data = response.json()
            record.update(response_fields=sorted(data), key_metadata=data.get("key_metadata"),
                          request_id=data.get("request_id"), credits_used_header=response.headers.get("x-credits-used"))
            if not response.is_success:
                record.update(error_code=data.get("error_code"), message=data.get("message"))
                emit(record)
                return None
            emit(record)
            return data
        except (httpx.HTTPError, ValueError) as exc:
            record.update(seconds=round(time.monotonic() - started, 3), error_type=type(exc).__name__)
            emit(record)
            return None

    try:
        with httpx.Client(base_url="https://api.context.dev/v1", headers={"Authorization": f"Bearer {key}"},
                          timeout=60, follow_redirects=False) as client:
            before = call(client, "GET", "/org/usage")
            if before is None:
                return
            report["balance_before"] = before.get("credits_remaining")
            if not isinstance(report["balance_before"], (int, float)) or report["balance_before"] < 3:
                report["stop_reason"] = "Insufficient or unknown balance for bounded test"
                return
            report["query"] = "artificial intelligence regulation"
            body = {"searchBy": {"type": "natural_language", "query": report["query"]}, "limit": 10}
            if recent_only:
                now = datetime.now(timezone.utc)
                body["filterBy"] = {"articleLanguage": ["en"], "date": {
                    "from": int((now - timedelta(days=7)).timestamp() * 1000),
                    "to": int(now.timestamp() * 1000)}}
            report["search_request"] = body
            news = call(client, "POST", "/news/search", body)
            if news is not None:
                articles = news.get("data") or []
                report["news"] = {
                    "count": len(articles), "has_more": news.get("has_more"),
                    "cursor_present": bool(news.get("next_cursor")),
                    "pagination_tested": False,
                    "article_fields": sorted({field for article in articles for field in article}),
                    "distinct_publishers": len({(article.get("source") or {}).get("domain") for article in articles}),
                    "distinct_story_ids": len({article.get("story_id") for article in articles}),
                    "samples": [{field: article.get(field) for field in
                                 ("id", "story_id", "title", "url", "published_at", "source", "type", "language")}
                                for article in articles],
                }
                valid = 0
                for article in articles:
                    timestamp = normalize_timestamp(article.get("published_at"))
                    url = canonicalize_url(article.get("url"))
                    publisher = (article.get("source") or {}).get("domain")
                    if not (timestamp and url and publisher and article.get("id") and article.get("title")):
                        continue
                    Event(id=f"context:{article['id']}", platform="news_context", actor_id=f"publisher:{publisher}",
                          timestamp=timestamp, text=article["title"], urls=[url], source_url=url)
                    valid += 1
                report["news"]["valid_event_mappings"] = valid
                if recent_only:
                    report["news"]["dates_in_requested_window"] = sum(
                        bool(normalize_timestamp(a.get("published_at"))) and
                        body["filterBy"]["date"]["from"] <= datetime.fromisoformat(a["published_at"].replace("Z", "+00:00")).timestamp() * 1000 <= body["filterBy"]["date"]["to"]
                        for a in articles)
                    report["news"]["english_results"] = sum(a.get("language") == "en" for a in articles)
                emit(report["news"])
                candidate = next((a for a in articles if canonicalize_url(a.get("url"))), None)
                if candidate and not recent_only:
                    scraped = call(client, "POST", "/web/scrape", {
                        "url": candidate["url"], "formats": {"markdown": True}})
                    if scraped is not None:
                        markdown = scraped.get("markdown") or {}
                        report["scrape"] = {
                            "url": candidate["url"], "markdown_fields": sorted(markdown),
                            "success": markdown.get("success"), "code": markdown.get("code"),
                            "markdown_characters": len(markdown.get("data") or ""),
                        }
                        emit(report["scrape"])
            after = call(client, "GET", "/org/usage")
            if after:
                report["balance_after"] = after.get("credits_remaining")
                report["observed_balance_delta"] = report["balance_before"] - report["balance_after"]
    finally:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False).replace(key, "[REDACTED]") + "\n")
        emit({"report": str(output), "balance_delta": report.get("observed_balance_delta")})


if __name__ == "__main__":
    main()
