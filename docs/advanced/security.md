# Segurança (Modo B)

!!! abstract "O que você vai aprender"
    Como **proteger o host do Modo B** (servidor FastAPI + WebSocket/SSE): exigir
    autenticação em cada conexão, restringir origens (CORS) e verificar JWT no
    servidor. Os modos estáticos (A/WASM e C/transpile) são só bundles servidos
    por CDN — não têm servidor a proteger.

Por padrão o `create_app(state_factory, view)` é **aberto**: qualquer cliente
conecta. Para produção, passe um `SecurityConfig`.

!!! warning "O host aberto avisa no log"
    Sem `SecurityConfig`, o servidor registra um `WARNING` dizendo exatamente o
    que está desligado — sem auth, sem allowlist de origem (então **qualquer
    site** abre um WebSocket para o seu host) e sem limites. É o default certo
    para `tempestweb dev` e o errado para chegar em produção sem ninguém notar.

```python
from tempestweb.server import create_app, SecurityConfig, token_authenticator

app = create_app(
    make_state,
    view,
    security=SecurityConfig(
        authenticate=token_authenticator("meu-segredo"),   # S0 — gate de auth
        allowed_origins=["https://app.exemplo.com"],        # S1 — allowlist de origem
    ),
)
```

## S0 — gate de autenticação

`authenticate` roda em **toda** conexão (upgrade do WebSocket e requisições SSE)
**antes** de a sessão ser criada. Um retorno falso — ou um erro levantado —
recusa a conexão (WS fecha com `1008`; SSE responde `401`). Pode ser síncrono ou
`async`.

Ele recebe um `Credentials`:

| Campo | Origem |
|---|---|
| `token` | `Authorization: Bearer <t>` ou `?token=<t>` |
| `origin` | header `Origin` |
| `headers` | headers (chaves minúsculas) |
| `query` | parâmetros de query |
| `client_ip` | endereço do peer — ou do `X-Forwarded-For`, se `trusted_proxies` permitir |

Dois builders prontos:

- **`token_authenticator(secret)`** — segredo compartilhado (padrão `X-Token`),
  comparado em tempo constante. Segredo **vazio desliga o gate** (só dev).
- **`jwt_authenticator(key, ...)`** — aceita um Bearer JWT válido e não expirado
  (ver S3).

Ou escreva o seu:

```python
async def authenticate(cred):
    user = await lookup_session(cred.token)
    return user is not None
```

## S1 — allowlist de origem (CORS)

`allowed_origins` instala o `CORSMiddleware` (superfície HTTP/SSE) **e** checa o
header `Origin` no upgrade do WebSocket — que o CORS do browser **não** protege.

- `allowed_origins=["https://app.exemplo.com"]` — só essa origem conecta.
- `allowed_origins=["*"]` — qualquer origem (wildcard; pula a checagem no WS).
- Ausente (`None`) — sem restrição de origem.

!!! warning "WebSocket ignora CORS"
    O navegador não aplica CORS a WebSockets. A checagem de `Origin` no upgrade é
    a única defesa contra um site terceiro abrir um WS pro seu servidor — por isso
    ela é feita explicitamente aqui.

## S3 — verificação de JWT no servidor

`verify_jwt(token, key)` valida **assinatura e expiração** e devolve os claims —
diferente de `observability.auth.decode_jwt`, que só lê os claims (client-side).

O claim `exp` é **obrigatório**: o PyJWT só confere uma expiração que existe, e um
token emitido sem `exp` seria aceito para sempre — o que não é "validar a
expiração". Para um token cuja vida outra coisa limita, passe
`require_expiry=False` (em `verify_jwt` e em `jwt_authenticator`).

```python
from tempestweb.server import verify_jwt, jwt_authenticator

claims = verify_jwt(token, KEY, algorithms=("HS256",), audience="meu-app")

app = create_app(make_state, view, security=SecurityConfig(
    authenticate=jwt_authenticator(KEY, audience="meu-app"),
))
```

!!! info "Requer o extra `[auth]`"
    `verify_jwt` usa PyJWT (`tempest-fastapi-sdk[auth]` / `pip install pyjwt`). Sem
    ele, `verify_jwt` levanta `RuntimeError` e `jwt_authenticator` recusa a
    conexão — nunca aceita silenciosamente.

## S2 — limites / anti-DoS

```python
SecurityConfig(
    max_connections=500,             # teto de sessões WS+SSE simultâneas
    max_message_bytes=65536,         # rejeita POST SSE maior que isso (413)
    max_connections_per_minute=60,   # flood de conexões por IP (1013/429)
    max_events_per_minute=600,       # flood de envelopes por IP (1013/429)
    trusted_proxies=["10.0.0.1"],    # de quem o X-Forwarded-For pode ser lido
)
```

- **`max_connections`** — conexão acima do teto é recusada (WS fecha `1013`; SSE
  `503`). O contador decrementa quando a sessão encerra.
- **`max_message_bytes`** — um `POST /sse/{id}` com corpo maior responde `413`. O
  teto é conferido **enquanto o corpo é lido**, não só no `Content-Length` — um
  POST com `Transfer-Encoding: chunked` não declara tamanho e antes passava reto.
- **`max_connections_per_minute`** — janela deslizante de 60s por IP; flood é
  recusado (WS `1013` / SSE `429`). O IP vem do **peer do socket**, a menos que
  `trusted_proxies` diga o contrário (abaixo).
- **`trusted_proxies`** — de quais peers o `X-Forwarded-For` pode ser acreditado.
  `None` (default) **ignora** o header; `["*"]` confia em qualquer peer; uma lista
  de endereços confia só neles.
- **`max_events_per_minute`** — a mesma janela, mas contando **envelopes de
  entrada** (cliques, input, `native_result`) nas duas pernas: `POST /sse/{id}`
  acima do teto responde `429`, e um frame de WebSocket acima do teto fecha o
  socket com `1013`. É um knob separado porque as ordens de grandeza diferem: uma
  conexão por cliente, mas um envelope por interação. Dimensione acima do pico
  legítimo do seu app — sem ele, uma conexão já aceita envia sem limite.

!!! danger "`X-Forwarded-For` é dado do cliente"
    Todo limite por IP só vale se o IP não for escolhido por quem está sendo
    limitado. O header é enviado pelo cliente: acreditar nele sem condição faz
    cada requisição parecer um cliente novo, e o limite nunca dispara — contra um
    teto de 3 conexões/minuto, 8 conexões com um `X-Forwarded-For` forjado por
    request passavam todas.

    Com `trusted_proxies`, o header é lido **da direita para a esquerda**: um
    proxy anexa o endereço que ele viu, então o hop mais à direita que não é um
    proxy declarado é o mais distante de que este deploy pode dar fé — o que o
    cliente prependou fica à esquerda e é ignorado.

    ```python
    # atrás de um nginx em 10.0.0.1
    SecurityConfig(trusted_proxies=["10.0.0.1"], max_connections_per_minute=60)
    ```

## Sessões SSE: o `session` na URL não autoriza nada

A perna SSE se divide em `GET /sse?session=<id>` (stream) e `POST /sse/<id>`
(eventos), e o `id` é escolhido pelo cliente. Ele identifica a sessão; **não**
prova quem pode usá-la. Quem apenas conhecesse o `id` leria o stream de patches
da vítima — que é o estado renderizado da tela dela — e postaria eventos na
sessão dela.

Por isso o `GET` que **materializa** a sessão grava a impressão digital de quem a
abriu — o token de auth quando o host autentica, o endereço do cliente quando
não — e todo `GET`/`POST` posterior naquele `id` precisa casar, ou responde
`403`.

- **Reabrir o stream é um takeover:** o stream mais novo passa a ser o dono; o que
  ele substituiu não pode mais derrubar a sessão. Isso é o caso normal de
  reconexão — a rede cai, o cliente reconecta, e só depois a resposta antiga
  termina de desmontar no servidor.
- **Gap no replay vira resync:** se o `Last-Event-ID` aponta para um tick que o
  buffer já descartou, o servidor manda a cena inteira (um Replace na raiz) antes
  de retomar, em vez de patches relativos a índice que não encaixam mais.

!!! tip "Escolha um `session` imprevisível"
    A posse protege o conteúdo, mas o `id` ainda viaja numa URL (logs, referer,
    histórico). Gere-o com `crypto.randomUUID()` — nunca um contador ou o id do
    usuário.

!!! note "Conexões mortas + ociosas"
    Conexão WS **morta/meio-aberta** já é ceifada pelo ping do uvicorn (~20–40s),
    não precisa de idle-timeout no app. Um idle-timeout ativo desconectaria também
    usuários legítimos parados, então **não** é imposto — use `max_connections` +
    rate limiting + o `limit_req` do reverse-proxy para defesa em profundidade.

!!! danger "`concurrent_dispatch=True` muda o que `max_events_per_minute` protege"
    Por padrão a sessão despacha **um evento por vez**, então um cliente que
    inunda envelopes só enfileira trabalho — a fila cresce, mas há sempre um
    handler rodando.

    Com [`create_app(..., concurrent_dispatch=True)`](deploy.md#handler-lento-spawn-primeiro-concurrent_dispatch-depois)
    cada envelope aceito vira **sua própria task**. A fila deixa de segurar o
    flood: o que limita quantas tasks uma conexão consegue abrir passa a ser
    exclusivamente `max_events_per_minute`.

    Se você liga a opção, configure esse teto **explicitamente**. Ele é `None`
    por padrão, e `None` com `concurrent_dispatch=True` significa fan-out de
    tasks sem limite por conexão.

## S6 — headers de segurança

```python
SecurityConfig(
    security_headers=True,                       # nosniff + Referrer-Policy + X-Frame-Options: DENY
    hsts=True,                                   # Strict-Transport-Security (só atrás de HTTPS)
    content_security_policy="default-src 'self'",  # opcional, app-specific
)
```

Um middleware adiciona os headers a **toda** resposta HTTP.

!!! info "CSP e o shell"
    O `index.html` dos modos estáticos usa `<script type="module">` inline, então
    uma CSP estrita precisa de nonce/hash que **você** fornece em
    `content_security_policy`. Por isso a CSP é opt-in explícita, não um default.

!!! check "XSS: seguro por construção"
    O cliente JS **nunca** injeta HTML — o patcher usa `textContent` e
    `setAttribute` (nunca `innerHTML`). Conteúdo dinâmico com `<`/`>`/`&` é
    renderizado como texto, não interpretado. Auditoria: zero sinks de HTML em
    todo `client/`.

## Recap

- O Modo B é **aberto por padrão**; produção pede um `SecurityConfig`.
- **S0** `authenticate` recusa conexões não-autorizadas antes de montar a sessão.
- **S1** `allowed_origins` liga CORS **e** trava a origem no WS.
- **S2** `max_connections` / `max_message_bytes` /
  `max_connections_per_minute` / `max_events_per_minute` limitam carga
  (parcial). Ligou `concurrent_dispatch`? `max_events_per_minute` deixa de ser
  opcional.
- **S3** `verify_jwt` / `jwt_authenticator` autenticam por JWT assinado.
- **S6** `security_headers` / `hsts` / `content_security_policy` endurecem as
  respostas; o cliente é XSS-safe por construção.
- Deploy (S5), escala (S4) e observabilidade de servidor (S8) seguem no
  [roadmap](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/roadmap.md) — Trilho S.

!!! info "Referência de API"
    Todos os campos de `SecurityConfig`: [`tempestweb.server`](../reference/server.md).
