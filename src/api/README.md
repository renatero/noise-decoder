# Coordination Radar API

Run the dashboard and mock API on all network interfaces:

```bash
python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

The current demo is reachable at:

- Dashboard: `http://188.166.112.226:8000/`
- Health: `http://188.166.112.226:8000/healthz`
- Analysis: `POST http://188.166.112.226:8000/api/analyze`

The dashboard and API share one origin, so the extension only opens the
dashboard; it does not make cross-origin API requests. The server currently
returns a schema-valid mock analysis response until the detector is integrated.

For internet-facing use, keep port `8000` allowed by the VPS/cloud firewall and
place the application behind an HTTPS reverse proxy before a public demo.
