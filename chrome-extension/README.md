# Coordination Radar Chrome extension

<<<<<<< HEAD
This minimal Manifest V3 extension opens the Coordination Radar dashboard from
selected text, a link, or a page. It does not scrape pages, collect post data,
or send content to an analysis API.
=======
This is a Manifest V3 extension for user-initiated collection of **visible public posts** from the active tab, followed by a bounded search of public Bluesky posts for related content. It does not run in the background or collect page data until the user selects **Extract visible posts**. The search is disclosed in the popup and can be reviewed before sending the resulting payload for analysis.
>>>>>>> 900fde4f23704b10b7b2955a32c7d23890720f63

## Load and configure

1. Open `chrome://extensions` and enable **Developer mode**.
2. Choose **Load unpacked** and select this `chrome-extension` directory.
3. Open **Extension options** and set the dashboard URL. The default is
   `https://radar.188.166.112.226.nip.io/`. Replace it with your branded HTTPS
   URL when available.

<<<<<<< HEAD
To open Settings as its own browser tab, right-click the extension toolbar icon
and choose **Coordination Radar settings**.
=======
The default endpoint is `http://localhost:8000/analyze`. Start the local FastAPI service from the repository root with `python -m src.api.server`; Uvicorn listens on loopback port 8000 and FastAPI CORS middleware supports the extension's preflight. Interactive API docs are at `http://localhost:8000/docs`. Change the endpoint through **Configure API endpoint**. The extension asks for permission only when you save a non-local API origin. If the API is unavailable or a request fails, the extension shows a clearly marked mock response.
>>>>>>> 900fde4f23704b10b7b2955a32c7d23890720f63

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
