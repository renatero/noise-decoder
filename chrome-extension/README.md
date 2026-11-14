# Coordination Radar Chrome extension

This minimal Manifest V3 extension opens the Coordination Radar dashboard from
selected text, a link, or a page. It does not scrape pages, collect post data,
or send content to an analysis API.

## Load and configure

1. Open `chrome://extensions` and enable **Developer mode**.
2. Choose **Load unpacked** and select this `chrome-extension` directory.
3. Open **Extension options** and set the dashboard URL. The default is
   `https://radar.188.166.112.226.nip.io/`. Replace it with your branded HTTPS
   URL when available.

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
node --experimental-default-type=module chrome-extension/tests/background.test.mjs
```
