# Deployment

The demo is designed for a single local machine or one VPS. During local
development, run:

```bash
python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

For a public demo, run Uvicorn on `127.0.0.1` through the included systemd
service and place Nginx in front using `nginx-coordination-radar.conf`. Replace
`radar.example.org` with the real domain, then obtain an HTTPS certificate and
set that HTTPS dashboard URL in the Chrome extension options.

Do not expose the plain development server as a long-lived production service.
The public Bluesky search endpoint is bounded but unauthenticated, so apply
normal VPS firewall, rate-limit, and reverse-proxy controls before a public
demo.
