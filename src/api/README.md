# Development API

Run the local endpoint for the Chrome extension with:

```bash
python3 src/api/dev_server.py
```

It listens on all IPv4 interfaces at port `8000` and exposes:

- `GET /health`
- `POST /analyze`

`POST /analyze` accepts an object with an `events` array. Each event must have
exactly these fields: `post_id`, `actor_id`, `text`, `url`, `timestamp`, and
`platform`. `actor_id` and `timestamp` may be `null` for sources such as SS.LV
that do not expose them in a listing view.

This server validates the extension handoff and returns a clearly marked
development report. It does not perform coordination detection yet.

The development API sends `Access-Control-Allow-Origin: *`, so browser clients
on other origins may call it. It has no authentication; only expose it on a
trusted network. Public internet access additionally requires firewall and
network-routing configuration outside this repository.
