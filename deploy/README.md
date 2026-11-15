# Deployment

The demo is designed for a single local machine or one VPS. During local
development, run:

```bash
python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

The deployed dashboard is at `https://decodethenoise.today/dashboard`, with DNS pointing
to `2.24.173.100`. Nginx terminates TLS and redirects HTTP to HTTPS. The
Coordination Radar service binds to `127.0.0.1:8001`; the legacy extension API
remains on `127.0.0.1:8000`. Let's Encrypt certificates are renewed by the
Certbot systemd timer. Install the declared dependencies in the project's
virtual environment before starting the service:

```bash
cd /opt/projects/noise-decoder
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

On Ubuntu, the Python `venv` OS package must be installed first. The supplied
systemd unit runs `.venv/bin/python` so collection uses the declared `httpx`
dependency rather than relying on packages in the system Python environment.
For test runs, install `requirements-dev.txt` in the same environment.

For a fresh VPS, first enable an HTTP Nginx reverse-proxy server block for
`decodethenoise.today`, then install Certbot's Nginx plugin and issue the
certificate:

```sh
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d decodethenoise.today --redirect
```

The current extension dashboard and API defaults use the HTTPS domain. Update
the extension's default URL when deploying to a different host.

Do not expose the plain development server as a long-lived production service.
The public Bluesky search endpoint is bounded but unauthenticated, so apply
normal VPS firewall, rate-limit, and reverse-proxy controls before a public
demo.

## Context.dev news search

Choose **News: Context.dev search** in the investigation dialog. It searches
English publisher articles over the last 1, 7, or 30 days (7 by default),
fetching at most 10 candidates. Duplicate URLs/story groups and records without
valid dates are removed. The news cards retain publisher attribution and links;
these articles are excluded from account coordination analysis, including when
exported and reimported with their `news_context` platform.

Configure `CONTEXT_API_KEY` in `/etc/noise-decoder/context.env`, owned by root
with mode `0600`. Never place it in JavaScript, Git, or a URL. The supplied
systemd unit reads this optional file and creates `/var/lib/noise-decoder` for
the cache and request budget. Install the unit and restart the service after
configuration changes. If the key is absent, the dashboard disables this source;
other sources continue to work.

`CONTEXT_DAILY_REQUEST_LIMIT` defaults to 20 new upstream requests per UTC day;
set it to 0 to disable searches. There is also a global limit of four new
requests per minute. Each request fetches at most ten candidates (normally one
provider credit). Cache hits within ten minutes consume no additional credits.
Failed or uncertain requests count against the local budget. Reservations are
persisted across restarts in `CONTEXT_STATE_PATH`, defaulting to
`.context-state.sqlite3` locally and `/var/lib/noise-decoder/context.sqlite3`
under systemd. The limit covers this app, not other applications sharing the key.

The endpoint is `POST /api/collect/context` with JSON
`{"query":"artificial intelligence regulation","limit":10,"days":7}` and
`X-NoiseDecoder-Request: 1`. It accepts same-origin browser requests and has no
CORS opt-in. This is a public demo endpoint, not an authenticated private API:
any client can use its shared allowance. The persistent global budget bounds
spending. Context.dev is deliberately excluded from **All live sources**.
No article extraction, automatic pagination, retries, or scheduled jobs run.

Official endpoint documentation: https://docs.context.dev/api-reference/news/search.
Availability and request format verified on 2026-11-14.
