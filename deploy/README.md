# Deployment

The demo is designed for a single local machine or one VPS. During local
development, run:

```bash
python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

The deployed demo runs at `https://radar.188.166.112.226.nip.io/`. Its
systemd service binds only to `127.0.0.1:8000`; Caddy terminates public HTTPS
and proxies the dashboard to it. The active Caddy host is:

```caddyfile
radar.188.166.112.226.nip.io {
    encode zstd gzip
    header X-Robots-Tag "noindex, nofollow"
    reverse_proxy 127.0.0.1:8000
}
```

For a branded production deployment, replace the `nip.io` hostname with a
domain you control, point its DNS to this VPS, and update the Caddy host and
Chrome extension setting together.

Do not expose the plain development server as a long-lived production service.
The public Bluesky search endpoint is bounded but unauthenticated, so apply
normal VPS firewall, rate-limit, and reverse-proxy controls before a public
demo.
