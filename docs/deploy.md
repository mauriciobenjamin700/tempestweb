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

### Gere os arquivos de deploy (`tempestweb deploy`)

Em vez de escrever a config do nginx à mão, gere-a pro seu projeto:

```bash
tempestweb deploy --server-name app.exemplo.com --tls --replicas 2
```

Escreve em `deploy/`: **`nginx.conf`** (parametrizado pela porta do
`tempestweb.toml`, com upgrade WS, `X-Forwarded-*`, timeouts de streaming,
`ip_hash` e — com `--tls` — bloco 443 + redirect HTTP→HTTPS), **`Dockerfile`**
(+ `HEALTHCHECK`), **`docker-compose.yml`** e **`DEPLOY.md`** (guia). Flags:
`--out`, `--server-name`, `--tls`, `--replicas`, `--no-sticky`, `--force`.

```bash
cd deploy && docker compose up --build
```

### Docker + reverse-proxy (referência)

Os mesmos arquivos, estáticos, também vivem em
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

**WebSocket é auto-contido** (uma conexão duplex numa réplica) → escala **sem
sticky**. O **SSE** é a exceção: o `GET` (stream) e o `POST` (eventos) precisam
cair na mesma réplica. Duas opções:

- **Sticky sessions** (padrão) — `ip_hash` no nginx fixa o cliente. `tempestweb
  deploy` já emite isso.
- **Backend Redis (dispensa sticky)** — roteie o inbound do SSE por Redis pub/sub:

  ```python
  from tempestweb.server import create_app, RedisSessionRouter

  app = create_app(make_state, view,
                   sse_backend=RedisSessionRouter.from_url("redis://redis:6379"))
  ```

  Aí gere o nginx **sem** `ip_hash`: `tempestweb deploy --no-sticky` (round-robin).
  Requer o extra `[cache]` (redis).

!!! warning "Não use `--workers > 1` sem sticky"
    Cada worker uvicorn tem seu próprio registro de sessões em memória. Rode
    **1 worker por container** e escale com réplicas atrás de um proxy sticky.

### Health checks

`GET /health` (sem auth) responde `{"status":"ok","sessions":N,"ready":bool}`.
`ready` vira `false` quando `max_connections` é atingido — use no *readiness* do
balanceador para drenar uma instância cheia.

### Métricas (S8)

`create_app(..., metrics=True)` monta `GET /metrics` no formato **Prometheus**:
`tempestweb_sessions_live` (gauge), `tempestweb_sessions_opened_total` e
`tempestweb_connections_rejected_total` (counters), e `tempestweb_sessions_max`
quando há cap. Aponte seu scraper pra lá.

## Recap

- **A/C**: `build` → publique o diretório estático num CDN. Fim.
- **B**: endureça com `SecurityConfig`, rode atrás de nginx (TLS + upgrade WS),
  escale com réplicas **sticky** (1 worker cada), monitore `/health`.
