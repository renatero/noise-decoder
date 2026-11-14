# Noise Decoder Chrome extension

This is a Manifest V3 extension for user-initiated collection of **visible public posts** from the active tab. It does not run in the background or collect page data until the user selects **Extract visible posts**.

It recognises the Finland, Latvia, Europe, and U.S. publisher domains in
[`docs-local/news-monitoring-source-inventory.md`](../docs-local/news-monitoring-source-inventory.md).
For those publishers it uses visible article text plus JSON-LD/OpenGraph
metadata where available. On social platforms it collects only the post or
comment cards already visible in the page; it does not log in, expand hidden
replies, or use private APIs.

## Load locally

1. In Chrome, open `chrome://extensions`.
2. Enable **Developer mode**.
3. Select **Load unpacked** and choose this `chrome-extension` directory.
4. Open a supported public feed, use the extension, review its payload, and select **Send for analysis**.

The default endpoint is `http://127.0.0.1:8000/analyze`. Change it through **Configure API endpoint**. The extension asks for permission only when you save a non-local API origin. Until the API is available, failed requests show a clearly marked mock response.

## Right-click inspection

On any public web page, right-click to use one of these menu actions:

- **Inspect selected text with Noise Decoder**
- **Inspect link with Noise Decoder**
- **Inspect page with Noise Decoder**

The extension places one reviewable event in the popup. It does **not** send it
to the API until you open the popup and select **Send for analysis**. Context
inspections represent a captured claim or link, not a published article, so
their `actor_id` and `timestamp` are intentionally `null`.

## Comment collection

Comment systems differ per article and platform. The extension only collects
comment cards that are visibly rendered and publicly accessible. It does not
claim the visible set is complete, and its status message calls out that hidden,
ranked-out, login-gated, and unloaded replies are missing. See the comment map
and data safeguards in the source inventory before adding a site-specific
comment adapter.

## API handoff

The extension sends this body:

```json
{ "events": [{ "post_id": "…", "actor_id": "…", "text": "…", "url": "…", "timestamp": "…", "platform": "…" }] }
```

`post_id` is the platform post ID where available (otherwise a stable page-derived ID), and `url` is the permalink for the post where one can be found. The detector should return a JSON report with `status`, `nodes`, `edges`, `clusters`, `evidence`, `statistics`, and `limitations`. Extraction is intentionally conservative and page structure varies across platforms, so users must review the payload before submitting it.

## SS.LV support

On an SS.LV category or search-results page, **Extract visible posts** collects the currently visible advertisements using SS.LV's ad-row ID and each advertisement permalink. SS.LV's listing markup does not expose a seller identity or publication timestamp, so those records deliberately use `"actor_id": null` and `"timestamp": null`. The API must accept nullable values and must not treat unknown sellers as the same actor.
