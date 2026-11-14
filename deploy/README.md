# Deployment

The Coordination Radar dashboard runs at `http://2.24.173.100/`. It runs as a
separate loopback service on port 8001 behind Nginx. The existing Noise Decoder
API remains on loopback port 8000 and keeps its `/health`, `/analyze`, and
`/discover` routes. The dashboard exposes `/healthz` and its `/api/*` routes on
the same public origin.

The project is checked out at `/home/joepeach/noise-decoder`, with dependencies
installed in `.venv`. From the repository root, install or refresh the service
and proxy configuration, then restart both API services:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
sudo install -m 0644 deploy/coordination-radar.service /etc/systemd/system/
sudo install -m 0644 deploy/nginx-noise-decoder-limit.conf /etc/nginx/conf.d/noise-decoder-limit.conf
sudo install -m 0644 deploy/nginx-coordination-radar.conf /etc/nginx/sites-available/noise-decoder-api
sudo ln -sfn /etc/nginx/sites-available/noise-decoder-api /etc/nginx/sites-enabled/noise-decoder-api
sudo systemctl daemon-reload
sudo systemctl restart noise-decoder-api
sudo systemctl enable --now coordination-radar
sudo nginx -t && sudo systemctl reload nginx
```

Nginx routes `/analyze`, `/discover`, and `/health` to the existing API on port
8000. All other paths, including `/`, `/healthz`, and `/api/*`, go to the
Coordination Radar dashboard service on port 8001. Both Uvicorn processes bind
to loopback only. Nginx applies a per-IP request limit to protect the public
collector.

The current IP deployment uses HTTP because no domain was configured. Configure
a domain and TLS before using it for sensitive traffic, then update the Nginx
host and Chrome extension dashboard URL together. Bluesky's public search may
reject requests from some VPS addresses; the dashboard also includes synthetic
scenarios and a stored public-data snapshot for offline demonstrations.
