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

## Recap

- Mode B is **open by default**; production needs a `SecurityConfig`.
- **S0** `authenticate` rejects unauthorized connections before mounting a session.
- **S1** `allowed_origins` enables CORS **and** locks the WS origin.
- **S3** `verify_jwt` / `jwt_authenticator` authenticate with a signed JWT.
- Limits/anti-DoS (S2), security headers (S6) and deploy (S5) are on the
  [roadmap](roadmap.md) — Track S.
