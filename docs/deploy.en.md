# Deploy to production

!!! abstract "What you'll learn"
    How to ship each mode. The **static modes** (A/WASM and C/transpile) are just
    files — host them on any CDN. **Mode B (server)** is a FastAPI host that needs
    a reverse proxy, TLS, and (to scale) sticky sessions.

## Static modes (A / C) — CDN

`tempestweb build --mode wasm` or `--mode transpile` produces a static
directory. Serve it from any file host (Netlify, Vercel, S3+CloudFront, GitHub
Pages, nginx). No server, no state — just CDN + cache. The service worker
handles offline.

```bash
tempestweb build --mode transpile --path .
# publish dist/transpile/ to your CDN
```

## Mode B (server) — FastAPI

The host serves `/ws`, `/sse`, `/sse/{id}` and `/health`. Before exposing it
publicly, **harden it** (see [Security](security.md)):

```python
create_app(make_state, view, security=SecurityConfig(
    authenticate=jwt_authenticator(os.environ["JWT_KEY"]),
    allowed_origins=["https://app.example.com"],
    max_connections=1000,
    security_headers=True,
    hsts=True,
))
```

### Generate the deploy files (`tempestweb deploy`)

Instead of hand-writing the nginx config, generate it for your project:

```bash
tempestweb deploy --server-name app.example.com --tls --replicas 2
```

Writes to `deploy/`: **`nginx.conf`** (parameterized from the `tempestweb.toml`
port, with WS upgrade, `X-Forwarded-*`, streaming timeouts, `ip_hash`, and — with
`--tls` — a 443 block + HTTP→HTTPS redirect), **`Dockerfile`** (+ `HEALTHCHECK`),
**`docker-compose.yml`** and **`DEPLOY.md`** (guide). Flags: `--out`,
`--server-name`, `--tls`, `--replicas`, `--no-sticky`, `--force`.

```bash
cd deploy && docker compose up --build
```

### Docker + reverse proxy (reference)

The same files, static, also live in
[`examples/deploy/`](https://github.com/mauriciobenjamin700/tempestweb/tree/main/examples/deploy):

- **`Dockerfile`** — `python:3.12-slim` + `tempestweb[server]`, runs `tempestweb
  run --mode server --host 0.0.0.0`, with a `HEALTHCHECK` on `/health`.
- **`nginx.conf`** — WebSocket upgrade, `Origin`/`X-Forwarded-*` preserved, long
  timeouts + `proxy_buffering off` for WS/SSE, and `ip_hash` (sticky).
- **`docker-compose.yml`** — app + nginx (TLS).

```bash
docker compose -f examples/deploy/docker-compose.yml up --build
```

### Horizontal scale (S4)

**WebSocket is self-contained** (one duplex connection on one replica) → it
scales **without** stickiness. **SSE** is the exception: its `GET` (stream) and
`POST` (events) must hit the same replica. Two options:

- **Sticky sessions** (default) — `ip_hash` in nginx pins the client;
  `tempestweb deploy` emits it.
- **Redis backend (drops stickiness)** — route SSE inbound over Redis pub/sub:

  ```python
  from tempestweb.server import create_app, RedisSessionRouter

  app = create_app(make_state, view,
                   sse_backend=RedisSessionRouter.from_url("redis://redis:6379"))
  ```

  Then generate nginx **without** `ip_hash`: `tempestweb deploy --no-sticky`
  (round-robin). Requires the `[cache]` extra (redis).

!!! warning "Don't use `--workers > 1` without stickiness"
    Each uvicorn worker has its own in-memory session registry. Run **1 worker
    per container** and scale with replicas behind a sticky proxy.

### Health checks

`GET /health` (no auth) returns `{"status":"ok","sessions":N,"ready":bool}`.
`ready` flips to `false` when `max_connections` is reached — use it in your load
balancer's readiness probe to drain a full instance.

### Metrics (S8)

`create_app(..., metrics=True)` mounts `GET /metrics` in **Prometheus** format:
`tempestweb_sessions_live` (gauge), `tempestweb_sessions_opened_total` and
`tempestweb_connections_rejected_total` (counters), plus `tempestweb_sessions_max`
when a cap is set. Point your scraper at it.

## Recap

- **A/C**: `build` → publish the static directory to a CDN. Done.
- **B**: harden with `SecurityConfig`, run behind nginx (TLS + WS upgrade), scale
  with **sticky** replicas (1 worker each), watch `/health`.
