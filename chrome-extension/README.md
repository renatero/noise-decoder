# Noise Decoder Chrome extension

This is a Manifest V3 extension for user-initiated collection of **visible public posts** from the active tab. It does not run in the background or collect page data until the user selects **Extract visible posts**.

## Load locally

1. In Chrome, open `chrome://extensions`.
2. Enable **Developer mode**.
3. Select **Load unpacked** and choose this `chrome-extension` directory.
4. Open a supported public feed, use the extension, review its payload, and select **Send for analysis**.

The default endpoint is `http://localhost:8000/analyze`. Change it through **Configure API endpoint**. The extension asks for permission only when you save a non-local API origin. Until the API is available, failed requests show a clearly marked mock response.

## API handoff

The extension sends this body (with extraction features attached to each event):

```json
{ "events": [{ "post_id": "…", "actor_id": "…", "text": "…", "url": "…", "timestamp": "…", "platform": "…" }] }
```

`post_id` is the platform post ID where available (otherwise a stable page-derived ID), and `url` is the permalink for the post where one can be found. Events retain the visible `text` and also include `normalized_text`, Unicode-aware `tokens`, normalized outgoing `links`, and `features`. URL normalization removes fragments and common analytics parameters (such as `utm_*`, `fbclid`, and `gclid`), sorts remaining query parameters, and canonicalizes the host and trailing slash. `features.shared_urls` lists links found in multiple extracted posts. `features.near_duplicates` lists matching post IDs and the reason for each match: `canonical_url` means an exact normalized outgoing URL match; `token_similarity` means token-set Jaccard similarity of at least 0.8, with at least three unique tokens on each side. An inverted index narrows comparisons to pairs that share a token or URL.

The detector should return a JSON report with `status`, `nodes`, `edges`, `clusters`, `evidence`, `statistics`, and `limitations`. Extraction is intentionally conservative and page structure varies across platforms, so users must review the payload before submitting it.
