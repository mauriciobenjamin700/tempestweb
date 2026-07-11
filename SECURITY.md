# Security Policy

## Reporting a vulnerability

Please report security issues **privately** — do not open a public issue for a
vulnerability. Email the maintainer or use GitHub's **"Report a vulnerability"**
(Security → Advisories) on the repository. Include a description, affected
versions, and a reproduction if possible. You'll get an acknowledgement within a
few days and a fix or mitigation timeline.

## Supported versions

tempestweb is pre-1.0; only the latest published `0.x` release receives security
fixes. Pin a version in production and upgrade promptly.

## Security model

- **Static modes (A/WASM, C/transpile):** the build output is static files with
  **no server**. The attack surface is the browser/CDN; there is no server-side
  code execution. The JS client never injects HTML (`textContent` + `setAttribute`
  only — no `innerHTML`), so app content is not an XSS vector.
- **Server mode (B):** the FastAPI host is **open by default** (dev). For any
  public deployment, pass a `SecurityConfig` to `create_app` — see
  [docs/security.md](docs/security.md):
  - `authenticate` — reject unauthenticated connections (`token_authenticator`,
    `jwt_authenticator`, or your own).
  - `allowed_origins` — CORS + a WebSocket `Origin` check.
  - `max_connections` / `max_message_bytes` — bound load.
  - `security_headers` / `hsts` / `content_security_policy` — hardening headers.
  - Server-side JWT verification via `verify_jwt` (signature + expiry).
- **Secrets** (VAPID keys, JWT signing keys, shared tokens) come from the
  environment and must **never** be committed.

Hardening still in progress is tracked in the roadmap under **Trilho S**
([docs/roadmap.md](docs/roadmap.md)): idle-session timeout, per-IP rate limiting,
an out-of-process session backend for horizontal scale, and server metrics.
