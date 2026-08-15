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

### Infra que bloqueia WebSocket? Troque o shell por SSE

O artefato de `--mode server` embarca **os dois** clientes de Modo B —
`static/transport-ws.js` (o que o `index.html` gerado monta) e
`static/transport-sse.js`. Se o seu proxy/CDN não deixa o WebSocket passar,
substitua o `index.html` do artefato; o mesmo host já responde em `/sse` e
`/sse/{id}`, e nada do lado Python muda:

```html
<script type="module">
  import { mount } from "./static/tempestweb.js";
  import { createSSETransport } from "./static/transport-sse.js";

  const transport = createSSETransport({ session: crypto.randomUUID() });
  mount(document.getElementById("app"), transport);
</script>
```

!!! tip "O `session` é seu"
    A sessão do SSE é keyed pelo id que **o cliente** escolhe — os dois canais
    (`GET /sse?session=<id>` e `POST /sse/<id>`) derivam dele. `crypto.randomUUID()`
    dá uma por aba; guardá-lo no `sessionStorage` faz o reload reaproveitar a
    mesma sessão. Com mais de uma réplica, mantenha as sticky-sessions (o
    `nginx.conf` gerado já usa `ip_hash`) ou configure o roteador Redis.

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

### Handler lento: `spawn` primeiro, `concurrent_dispatch` depois

Cada sessão despacha **um evento por vez**. É o que garante que duas teclas
digitadas rápido cheguem na ordem — e é o que faz um handler demorado congelar
aquela conexão inteira: nenhum outro botão daquele usuário responde enquanto ele
roda.

Na esmagadora maioria dos casos a resposta **não** é mudar o dispatch, é tirar o
trabalho do handler com
[`tempestweb.runtime.spawn`](../tutorial/best-practices.md#trabalho-longo-o-dispatch-e-serial).
Ele não muda semântica nenhuma: a ordem dos eventos continua a mesma, e a task
morre junto com a conexão.

Quando você realmente quer handlers de widgets diferentes rodando ao mesmo
tempo:

```python
app = create_app(make_state, view, concurrent_dispatch=True)
```

Cada evento vira sua própria task. Eventos do **mesmo `key`** continuam em ordem
de chegada (há um lock por widget), então digitação não embaralha; handlers de
widgets diferentes se sobrepõem. Um handler que levanta exceção nesse modo é
logado e descartado em vez de derrubar a conexão.

!!! warning "O que a opção exige de você"
    Com `concurrent_dispatch=True` dois handlers podem mutar o estado ao mesmo
    tempo. O app precisa estar escrito para isso — um `set_state` que lê o
    estado, calcula e grava deixa de ser atômico em relação a outro handler. Por
    isso vem desligada por padrão.

    Vale também ler o efeito no limite de carga: ligada, cada envelope aceito
    vira uma task, e `max_events_per_minute` passa a ser o teto de tasks
    concorrentes por IP — veja
    [Segurança → S2](security.md#s2-limites-anti-dos).

## Recap

- **A/C**: `build` → publique o diretório estático num CDN. Fim.
- **B**: endureça com `SecurityConfig`, rode atrás de nginx (TLS + upgrade WS),
  escale com réplicas **sticky** (1 worker cada), monitore `/health`.
- **Handler lento**: `spawn` resolve sem mudar semântica;
  `concurrent_dispatch=True` só quando você quer sobreposição de verdade — e aí
  configure `max_events_per_minute`.
