# Public news and discussion sources

Researched and checked from `junction.dev` on 2026-11-14. Existing live input
was Bluesky. The four additions below returned HTTP 200 without credentials.
The dashboard can collect each independently or use **Live: All sources**.

| Source | Public endpoint / reference | Why included | Coverage and interpretation |
| --- | --- | --- | --- |
| BBC News — World | [Publisher RSS](https://feeds.bbci.co.uk/news/world/rss.xml) | General international headlines | Current feed only; actor is BBC, not a journalist. |
| The Guardian — World | [Publisher RSS](https://www.theguardian.com/world/rss), [feed documentation](https://www.theguardian.com/help/feeds) | Another international editorial source | Current feed only; Guardian describes RSS use for personal, non-commercial purposes. |
| Al Jazeera | [Publisher RSS](https://www.aljazeera.com/xml/rss/all.xml) | Adds international reporting including Middle East coverage | Current mixed news/video feed; actor is the publisher. |
| Hacker News | [Algolia API](https://hn.algolia.com/api), [provider repository](https://github.com/algolia/hn-search) | Searchable public story submissions with usernames, dates and outgoing article URLs | Technology-focused discussion, not a general news wire. Index coverage and freshness can vary. |

All three feeds exposed RSS items with article links and publication dates.
Hacker News exposed story IDs, submitting usernames, publication timestamps and
outgoing links. These fields map to the existing normalized event schema without
inventing identity or publication times. No new dependencies or API keys were
needed. The Algolia implementation repository is archived, so availability is
handled as an upstream dependency, not assumed permanent.

Only feed-provided headlines and short summaries are used; article pages are
not scraped. Each record links to the original publication, preserves publisher
identity, and removes common tracking parameters for URL comparison. Consult
publisher terms for uses beyond this demonstration; public accessibility is
not a general redistribution license. Guardian's documented non-commercial
scope is a consideration for any future commercial deployment.

An RSS article is context from a publisher, not evidence that a social account
posted it. Publisher IDs are deliberately distinct from social account IDs.
The extension's related-post search adds Hacker News alongside Bluesky; news
feeds are selectable in the dashboard. The existing detector requires recurring
shared URLs, so topical similarity across publishers alone does not create a
coordination finding.

Queries on feeds match all words in the current title/summary, or an exact
canonical article URL. They do not search publishers' historical archives.
Empty feed queries return the current feed. A zero-match result is valid and
is different from an unavailable feed. Feed data is cached for five minutes.
Combined collection reports failures per source and returns up to 100 events
in total, fairly interleaved across sources.

DW's English endpoint was also probed: it returned XML but did not expose the
RSS 2.0 item structure used by these feeds, so it was not enabled in this change.
Sources requiring credentials or a paid search plan were not needed for this
deployment.

## Verification

Run collector, API, discovery and engine unittest suites using the commands in
the root README. Tests cover RSS parsing and cache expiry, dates, publisher IDs,
HTML-to-text conversion, URL normalization, duplicates, malformed responses,
response-size and result limits, rate limits, partial failures, and combined
discovery. Live verification should fetch each new source, collect combined
results, and submit those normalized events to `/api/analyze`.
