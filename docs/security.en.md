# Security (Mode B)

!!! abstract "What you'll learn"
    How to **harden the Mode B host** (FastAPI server + WebSocket/SSE): require
    authentication on every connection, restrict origins (CORS), and verify JWTs
    on the server. The static modes (A/WASM and C/transpile) are just
    CDN-served bundles — there is no server to protect.

By default `create_app(state_factory, view)` is **open**: any client connects.
For production, pass a `SecurityConfig`.

```python
from tempestweb.server import create_app, SecurityConfig, token_authenticator

app = create_app(
    make_state,
    view,
    security=SecurityConfig(
        authenticate=token_authenticator("my-secret"),     # S0 — auth gate
        allowed_origins=["https://app.example.com"],        # S1 — origin allowlist
    ),
)
```

## S0 — authentication gate

`authenticate` runs on **every** connection (WebSocket upgrade and SSE requests)
**before** a session is created. A falsy return — or a raised error — rejects the
connection (WS closes with `1008`; SSE returns `401`). It may be sync or `async`.

It receives a `Credentials`:

| Field | Source |
|---|---|
| `token` | `Authorization: Bearer <t>` or `?token=<t>` |
| `origin` | the `Origin` header |
| `headers` | request headers (lower-cased keys) |
| `query` | query parameters |

Two ready-made builders:

- **`token_authenticator(secret)`** — a shared secret (the `X-Token` convention),
  compared in constant time. An **empty secret disables the gate** (dev only).
- **`jwt_authenticator(key, ...)`** — accepts a valid, unexpired Bearer JWT
  (see S3).

Or write your own:

```python
async def authenticate(cred):
    user = await lookup_session(cred.token)
    return user is not None
```

## S1 — origin allowlist (CORS)

`allowed_origins` installs `CORSMiddleware` (HTTP/SSE surface) **and** checks the
`Origin` header on the WebSocket upgrade — which browser CORS does **not** guard.

- `allowed_origins=["https://app.example.com"]` — only that origin connects.
- `allowed_origins=["*"]` — any origin (wildcard; skips the WS check).
- Absent (`None`) — no origin restriction.

!!! warning "WebSockets ignore CORS"
    Browsers don't apply CORS to WebSockets. The `Origin` check on the upgrade is
    the only defense against a third-party site opening a WS to your server — so
    it is done explicitly here.

## S3 — server-side JWT verification

`verify_jwt(token, key)` validates the **signature and expiry** and returns the
claims — unlike `observability.auth.decode_jwt`, which only reads claims
(client-side).

```python
from tempestweb.server import verify_jwt, jwt_authenticator

claims = verify_jwt(token, KEY, algorithms=("HS256",), audience="my-app")

app = create_app(make_state, view, security=SecurityConfig(
    authenticate=jwt_authenticator(KEY, audience="my-app"),
))
```

!!! info "Requires the `[auth]` extra"
    `verify_jwt` uses PyJWT (`tempest-fastapi-sdk[auth]` / `pip install pyjwt`).
    Without it, `verify_jwt` raises `RuntimeError` and `jwt_authenticator` rejects
    the connection — it never silently accepts.

## S2 — limits / anti-DoS

```python
SecurityConfig(
    max_connections=500,             # cap on concurrent WS+SSE sessions
    max_message_bytes=65536,         # reject an SSE POST larger than this (413)
    max_connections_per_minute=60,   # per-IP connection flood (1013/429)
    max_events_per_minute=600,       # per-IP envelope flood (1013/429)
)
```

- **`max_connections`** — a connection over the cap is refused (WS close `1013`;
  SSE `503`). The counter decrements when the session ends.
- **`max_message_bytes`** — a `POST /sse/{id}` with a larger body returns `413`.
  The cap is enforced **while the body is read**, not from `Content-Length`
  alone — a chunked POST declares no length and used to sail straight past it.
- **`max_connections_per_minute`** — a rolling 60s per-IP window (from
  `X-Forwarded-For` or peer); a flood is refused (WS `1013` / SSE `429`).
- **`max_events_per_minute`** — the same window, counting **inbound envelopes**
  (clicks, input, `native_result`) across both legs: a `POST /sse/{id}` over
  budget answers `429`, and a WebSocket frame over budget closes the socket with
  `1013`. A separate knob because the magnitudes differ: one connection per
  client, but one envelope per interaction. Size it above your app's legitimate
  peak — without it, an already-accepted connection sends without limit.

!!! note "Dead + idle connections"
    A **dead/half-open** WS is already reaped by uvicorn's ping (~20–40s) — no
    app idle-timeout needed. An active idle-timeout would also disconnect
    legitimately-idle users, so it is **not** enforced — use `max_connections` +
    rate limiting + the reverse proxy's `limit_req` for defense in depth.

## S6 — security headers

```python
SecurityConfig(
    security_headers=True,                        # nosniff + Referrer-Policy + X-Frame-Options: DENY
    hsts=True,                                    # Strict-Transport-Security (HTTPS only)
    content_security_policy="default-src 'self'",  # optional, app-specific
)
```

A middleware adds the headers to **every** HTTP response.

!!! info "CSP and the shell"
    The static-mode `index.html` uses inline `<script type="module">`, so a strict
    CSP needs a nonce/hash **you** supply in `content_security_policy`. That's why
    CSP is an explicit opt-in, not a default.

!!! check "XSS: safe by construction"
    The JS client **never** injects HTML — the patcher uses `textContent` and
    `setAttribute` (never `innerHTML`). Dynamic content with `<`/`>`/`&` renders
    as text, not markup. Audit: zero HTML sinks anywhere in `client/`.

## Recap

- Mode B is **open by default**; production needs a `SecurityConfig`.
- **S0** `authenticate` rejects unauthorized connections before mounting a session.
- **S1** `allowed_origins` enables CORS **and** locks the WS origin.
- **S2** `max_connections` / `max_message_bytes` bound load (partial).
- **S3** `verify_jwt` / `jwt_authenticator` authenticate with a signed JWT.
- **S6** `security_headers` / `hsts` / `content_security_policy` harden responses;
  the client is XSS-safe by construction.
- Deploy (S5), scale (S4) and server observability (S8) remain on the
  [roadmap](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/roadmap.md) — Track S.
