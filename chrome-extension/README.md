# Coordination Radar Chrome extension

This minimal Manifest V3 extension provides a one-click entry point to the
Coordination Radar dashboard. It does not scrape pages, collect post data, or
send content to an analysis API.

## Load locally

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Choose **Load unpacked** and select this `chrome-extension` directory.
4. In the extension's **Details**, open **Extension options** and set the
   dashboard URL (default: `http://188.166.112.226:8000/`).

## Investigate from a page

Right-click selected text, a link, or a web page, then choose **Investigate
with Coordination Radar**. The extension opens the configured dashboard in a
new tab with:

- `investigate`: the selected text, link URL, or page URL
- `input_type`: `selection`, `link`, or `page`

The dashboard is responsible for pre-filling its investigation field and
collecting any data needed for analysis. A prefilled reference is not a
collected post and has not been analysed. Clicking the extension toolbar icon
opens the dashboard without a prefilled input.

## Validate the handoff

```bash
node --experimental-default-type=module chrome-extension/tests/background.test.mjs
```

For browser acceptance, load the unpacked extension and test all three
right-click targets: selected text, a link, and the page. Each must open the
configured dashboard with the matching prefilled reference. The public demo
dashboard is `http://188.166.112.226:8000/`; replace it with the final HTTPS
domain before deployment.
