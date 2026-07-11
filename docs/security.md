# Segurança (Modo B)

!!! abstract "O que você vai aprender"
    Como **proteger o host do Modo B** (servidor FastAPI + WebSocket/SSE): exigir
    autenticação em cada conexão, restringir origens (CORS) e verificar JWT no
    servidor. Os modos estáticos (A/WASM e C/transpile) são só bundles servidos
    por CDN — não têm servidor a proteger.

Por padrão o `create_app(state_factory, view)` é **aberto**: qualquer cliente
conecta. Para produção, passe um `SecurityConfig`.

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

## Recap

- O Modo B é **aberto por padrão**; produção pede um `SecurityConfig`.
- **S0** `authenticate` recusa conexões não-autorizadas antes de montar a sessão.
- **S1** `allowed_origins` liga CORS **e** trava a origem no WS.
- **S3** `verify_jwt` / `jwt_authenticator` autenticam por JWT assinado.
- Limites/anti-DoS (S2), headers de segurança (S6) e deploy (S5) estão no
  [roadmap](roadmap.md) — Trilho S.
