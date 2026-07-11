# Deploy em produção

!!! abstract "O que você vai aprender"
    Como colocar cada modo em produção. Os **modos estáticos** (A/WASM e
    C/transpile) são só arquivos — sobem em qualquer CDN. O **Modo B (servidor)**
    é um host FastAPI que precisa de reverse-proxy, TLS e (para escalar)
    sticky-sessions.

## Modos estáticos (A / C) — CDN

`tempestweb build --mode wasm` ou `--mode transpile` gera um diretório estático.
Sirva-o em qualquer host de arquivos (Netlify, Vercel, S3+CloudFront, GitHub
Pages, nginx). Sem servidor, sem estado — só CDN + cache. O service worker
cuida do offline.

```bash
tempestweb build --mode transpile --path .
# publique dist/transpile/ no seu CDN
```

## Modo B (servidor) — FastAPI

O host serve `/ws`, `/sse`, `/sse/{id}` e `/health`. Antes de expor
publicamente, **endureça-o** (ver [Segurança](security.md)):

```python
create_app(make_state, view, security=SecurityConfig(
    authenticate=jwt_authenticator(os.environ["JWT_KEY"]),
    allowed_origins=["https://app.exemplo.com"],
    max_connections=1000,
    security_headers=True,
    hsts=True,
))
```

### Docker + reverse-proxy

Arquivos de referência em
[`examples/deploy/`](https://github.com/mauriciobenjamin700/tempestweb/tree/main/examples/deploy):

- **`Dockerfile`** — `python:3.12-slim` + `tempestweb[server]`, roda `tempestweb
  run --mode server --host 0.0.0.0`, com `HEALTHCHECK` em `/health`.
- **`nginx.conf`** — upgrade de WebSocket, `Origin`/`X-Forwarded-*` preservados,
  timeouts longos + `proxy_buffering off` para WS/SSE, e `ip_hash` (sticky).
- **`docker-compose.yml`** — app + nginx (TLS).

```bash
docker compose -f examples/deploy/docker-compose.yml up --build
```

### Escala horizontal (S4)

O estado das sessões WS/SSE vive **na memória do processo**. Para rodar múltiplas
réplicas:

- **Sticky sessions** — fixe cada cliente a uma réplica (`ip_hash` no nginx, ou
  affinity do seu balanceador). É o caminho suportado hoje.
- Um **backend de sessão fora do processo** (Redis) para dispensar sticky é
  follow-up do Trilho S (S4).

!!! warning "Não use `--workers > 1` sem sticky"
    Cada worker uvicorn tem seu próprio registro de sessões em memória. Rode
    **1 worker por container** e escale com réplicas atrás de um proxy sticky.

### Health checks

`GET /health` (sem auth) responde `{"status":"ok","sessions":N,"ready":bool}`.
`ready` vira `false` quando `max_connections` é atingido — use no *readiness* do
balanceador para drenar uma instância cheia.

## Recap

- **A/C**: `build` → publique o diretório estático num CDN. Fim.
- **B**: endureça com `SecurityConfig`, rode atrás de nginx (TLS + upgrade WS),
  escale com réplicas **sticky** (1 worker cada), monitore `/health`.
