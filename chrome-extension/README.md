# Coordination Radar Chrome extension

This minimal Manifest V3 extension opens the Coordination Radar dashboard from
selected text, a link, or a page. It does not scrape pages, collect post data,
or send content to an analysis API.

## Load and configure

1. Open `chrome://extensions` and enable **Developer mode**.
2. Choose **Load unpacked** and select this `chrome-extension` directory.
3. Open **Extension options** to confirm the dashboard URL. The deployed
   default is `https://decodethenoise.today/dashboard`.

To open Settings as its own browser tab, right-click the extension toolbar icon
and choose **Coordination Radar settings**.

## Investigate from a page

Right-click selected text, a link, or a web page and choose **Investigate with
Coordination Radar**. The extension opens the dashboard with:

- `investigate`: selected text, link URL, or page URL
- `input_type`: `selection`, `link`, or `page`

Opening the dashboard only transfers a reference. It does not mean the content
was collected or analysed.

## Validate

```bash
node chrome-extension/tests/background.test.mjs
```
