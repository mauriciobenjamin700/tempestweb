# Auth Gate JWT

Construa um **app de login com guarda de rota** que usa `AuthStore`, `route_guard`,
decodificação de JWT offline e um logger de auditoria — tudo em Python puro, sem
HTML nem JavaScript. 🔐

Ao final deste tutorial você terá um app funcional que demonstra o trilho **O4
(Observability › Auth)** do tempestweb: o `AuthStore` guarda o token e direciona
qual tela renderizar, o `route_guard` redireciona quem não está autenticado, tokens
JWT são decodificados sem biblioteca externa, e cada evento relevante (login,
logout, falha) deixa um rastro auditável nos `LogRecord`s do `Logger`.

---

## O problema

Todo app autenticado precisa resolver quatro questões ao mesmo tempo:

1. **Onde guardar o token?** — num lugar observável que dispare re-renders ao mudar.
2. **Como proteger rotas?** — redirecionar para `/login` sem poluir a `view` com
   condicionais espalhadas.
3. **O que o token diz?** — `sub`, `role`, `exp` ficam no payload do JWT e o
   cliente precisa lê-los para decidir se deve renovar o token.
4. **Como auditar eventos?** — logar login, logout e falhas de forma estruturada,
   sem acoplar a lógica de negócio ao `print`.

O tempestweb resolve isso com a superfície de auth do pacote
`tempestweb.observability`: `AuthStore` (loja observável), `route_guard` (guarda
de rota puro), `decode_jwt` + `is_jwt_expired` (helpers de JWT offline) e `Logger`
(log estruturado com sinks plugáveis).

!!! note "O que você vai exercitar"
    - `create_auth_store` / `AuthStore` — criar, popular e observar a loja de token.
    - `route_guard` — construir um guarda que redireciona requests não autenticados.
    - `decode_jwt` — decodificar o payload de um JWT sem verificar a assinatura.
    - `is_jwt_expired` — checar expiração com um `now` fixo (determinístico em
      testes).
    - `create_logger` / `Logger` / `LogRecord` / `LoggerSink` — registrar eventos
      com nível, mensagem e campos estruturados.
    - Construção de JWTs unsigned para demos e testes offline.

---

## Pré-requisitos

Certifique-se de ter feito a [Instalação](../installation.md) e lido o
[Tutorial do Counter](../tutorial/index.md). Este exemplo assume que você já
conhece `App`, `set_state`, `make_state` e `view`.

Para entender como o `route_guard` mapeia para o sistema de navegação completo do
tempestweb, veja [Navegação](../tutorial/index.md).

---

## O app completo

Este é o código exato de
[`examples/auth-jwt/app.py`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/auth-jwt/app.py).
Copie, rode, e depois leia a explicação seção por seção.

```python
"""JWT auth gate — client-side auth with AuthStore, route guard, and JWT helpers.

This example wires the full O4 auth surface into a realistic login-gate pattern:

- An **AuthStore** (created via ``create_auth_store``) is held inside State and
  drives which screen renders — a login prompt when logged out, a protected
  dashboard when logged in.
- A hand-built unsigned JWT (``header.payload.signature`` with a base64url-
  encoded JSON payload) is decoded offline by ``decode_jwt`` and inspected for
  expiry via ``is_jwt_expired(token, now=<fixed>)``.
- A **Logger** records every login and logout event for auditability.
- ``route_guard`` decides which screen to show based on auth status.

The ``view`` is transport-agnostic and runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

No bridge is needed: the initial mount calls no native capability, so
``build(view(app))`` is green with no bridge installed.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any

from tempest_core import App, Widget
from tempest_core.style import AlignItems, Color, Edge, FontWeight, Style, TextAlign
from tempest_core.widgets import (
    Button,
    Column,
    Input,
    KeyboardType,
    Row,
    Text,
)
from tempest_core.widgets.events import TextChangeEvent
from tempestweb.observability import (
    AuthStore,
    Logger,
    LoggerSink,
    LogRecord,
    create_auth_store,
    create_logger,
    decode_jwt,
    is_jwt_expired,
    route_guard,
)

# ---------------------------------------------------------------------------
# JWT helpers — build offline-verifiable tokens for the demo
# ---------------------------------------------------------------------------

# A fixed "now" timestamp used throughout the demo so expiry display is
# deterministic in tests (and in the initial render).
_DEMO_NOW: float = 1_800_000_000.0  # arbitrary fixed epoch, well in the past


def _b64url(obj: dict[str, Any]) -> str:
    """Encode *obj* as a URL-safe base64 string without padding.

    Args:
        obj: A JSON-serialisable dict.

    Returns:
        The base64url-encoded JSON without trailing ``=`` characters.
    """
    raw: bytes = json.dumps(obj, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def make_jwt(claims: dict[str, Any]) -> str:
    """Build an unsigned compact JWT carrying *claims*.

    The signature segment is the literal string ``"sig"`` — it is
    intentionally not a real HMAC so the token can be decoded offline by
    ``decode_jwt`` without a secret. **Never use this pattern in production.**

    Args:
        claims: Arbitrary JSON-serialisable claims.

    Returns:
        A ``header.payload.sig`` JWT string.
    """
    header: str = _b64url({"alg": "none", "typ": "JWT"})
    payload: str = _b64url(claims)
    return f"{header}.{payload}.sig"


# Pre-built tokens used by the demo.
# ``exp`` is set relative to _DEMO_NOW so the expiry indicator is stable:
# the "alice" token expires 1 hour after the demo epoch (= not yet expired at
# _DEMO_NOW); the "bob" token expired 1 hour before (= already expired).
_ALICE_TOKEN: str = make_jwt(
    {
        "sub": "alice",
        "name": "Alice Souza",
        "role": "admin",
        "exp": int(_DEMO_NOW) + 3600,  # expires 1 h after the demo epoch
    }
)

_BOB_TOKEN: str = make_jwt(
    {
        "sub": "bob",
        "name": "Bob Lima",
        "role": "user",
        "exp": int(_DEMO_NOW) - 3600,  # expired 1 h before the demo epoch
    }
)

# Demo credential store (username → (password, JWT)).
_CREDENTIALS: dict[str, tuple[str, str]] = {
    "alice": ("secret", _ALICE_TOKEN),
    "bob": ("p4ssw0rd", _BOB_TOKEN),
}

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class AuthAppState:
    """All mutable state for the auth-gate app.

    Attributes:
        store: The observable auth store holding the current token and user.
        log: The logger; its records are read by the view.
        username: The draft username the user is typing.
        password: The draft password the user is typing.
        error: A top-level login error message (wrong credentials, etc.).
        log_records: Accumulated log records shown in the audit trail.
        current_route: The route the app is trying to render.
    """

    store: AuthStore = field(default_factory=create_auth_store)
    log: Logger = field(init=False)
    username: str = ""
    password: str = ""
    error: str = ""
    log_records: list[LogRecord] = field(default_factory=list)
    current_route: str = "/dashboard"

    def __post_init__(self) -> None:
        """Wire up the logger with an in-state sink so records drive re-renders.

        Returns:
            None.
        """

        def _append_sink(record: LogRecord) -> None:
            """Append a log record to the state list.

            Args:
                record: The structured record to store.
            """
            self.log_records.append(record)

        sink: LoggerSink = _append_sink
        self.log = create_logger(sinks=[sink], level="INFO")


def make_state() -> AuthAppState:
    """Build the initial, logged-out application state.

    Returns:
        A fresh :class:`AuthAppState`.
    """
    return AuthAppState()


# ---------------------------------------------------------------------------
# Screen helpers
# ---------------------------------------------------------------------------


def _token_badge(token: str) -> Widget:
    """Render a small info card showing decoded JWT claims and expiry.

    Args:
        token: The JWT to inspect.

    Returns:
        A widget tree summarising the token claims and whether it is expired.
    """
    claims: dict[str, Any] = decode_jwt(token)
    expired: bool = is_jwt_expired(token, now=_DEMO_NOW)

    sub: str = str(claims.get("sub", "—"))
    role: str = str(claims.get("role", "—"))
    exp_label: str = "expired" if expired else "valid"
    exp_color: Color = (
        Color.from_hex("#dc2626") if expired else Color.from_hex("#16a34a")
    )

    return Column(
        key="token-badge",
        style=Style(
            gap=4.0,
            padding=Edge.all(12.0),
            background=Color.from_hex("#f0fdf4"),
            radius=8.0,
        ),
        children=[
            Text(
                content="JWT Claims",
                style=Style(font_weight=FontWeight.BOLD, font_size=13.0),
                key="badge-title",
            ),
            Text(content=f"sub: {sub}", key="badge-sub"),
            Text(content=f"role: {role}", key="badge-role"),
            Text(
                content=f"token: {exp_label}",
                style=Style(color=exp_color, font_weight=FontWeight.BOLD),
                key="badge-exp",
            ),
        ],
    )


def _audit_trail(records: list[LogRecord]) -> Widget:
    """Render the last few log records as a compact audit trail.

    Args:
        records: The accumulated :class:`~tempestweb.observability.LogRecord` list.

    Returns:
        A widget tree listing the records (newest last), or an empty-state row.
    """
    if not records:
        return Row(
            key="audit-empty",
            children=[
                Text(
                    content="No log entries yet.",
                    style=Style(color=Color.from_hex("#6b7280"), font_size=12.0),
                    key="audit-empty-text",
                )
            ],
        )

    entries: list[Widget] = [
        Text(
            content=f"[{r.level}] {r.message}",
            style=Style(font_size=12.0, color=Color.from_hex("#374151")),
            key=f"audit-{i}",
        )
        for i, r in enumerate(records[-5:])  # show at most the last 5
    ]
    return Column(key="audit-records", style=Style(gap=2.0), children=entries)


# ---------------------------------------------------------------------------
# Sub-screens
# ---------------------------------------------------------------------------


def _login_screen(app: App[AuthAppState]) -> Widget:
    """Render the login prompt.

    Args:
        app: The application handle.

    Returns:
        A widget tree with username/password inputs and a login button.
    """

    def on_username(event: TextChangeEvent) -> None:
        """Update the draft username.

        Args:
            event: The text change event carrying the new value.
        """
        value: str = event.value

        def _set(s: AuthAppState) -> None:
            s.username = value
            s.error = ""

        app.set_state(_set)

    def on_password(event: TextChangeEvent) -> None:
        """Update the draft password.

        Args:
            event: The text change event carrying the new value.
        """
        value: str = event.value

        def _set(s: AuthAppState) -> None:
            s.password = value
            s.error = ""

        app.set_state(_set)

    def do_login() -> None:
        """Validate credentials and log in if correct.

        Looks the username up in the demo credential store, checks the
        password, then calls ``store.login`` with the matching JWT and a
        user-info dict.  Failures are surfaced via ``state.error``.

        Returns:
            None.
        """
        username: str = app.state.username.strip()
        password: str = app.state.password

        entry: tuple[str, str] | None = _CREDENTIALS.get(username)
        if entry is None or entry[0] != password:
            app.state.log.warning("login failed", username=username)

            def set_error(s: AuthAppState) -> None:
                s.error = "Invalid username or password."

            app.set_state(set_error)
            return

        _pw, token = entry
        claims: dict[str, Any] = decode_jwt(token)
        app.state.log.info(
            "login successful",
            username=username,
            role=str(claims.get("role", "?")),
        )
        user_info: dict[str, Any] = {
            "sub": username,
            "name": claims.get("name", username),
        }
        app.state.store.login(token, user_info)

        def on_logged_in(s: AuthAppState) -> None:
            s.error = ""
            s.username = ""
            s.password = ""
            s.current_route = "/dashboard"

        app.set_state(on_logged_in)

    error_widgets: list[Widget] = []
    if app.state.error:
        error_widgets.append(
            Text(
                content=app.state.error,
                style=Style(color=Color.from_hex("#dc2626"), font_size=13.0),
                key="login-error",
            )
        )

    return Column(
        key="login-screen",
        style=Style(
            gap=16.0,
            padding=Edge.all(24.0),
            align=AlignItems.CENTER,
        ),
        children=[
            Text(
                content="Sign in",
                style=Style(
                    font_size=26.0,
                    font_weight=FontWeight.BOLD,
                    text_align=TextAlign.CENTER,
                ),
                key="login-heading",
            ),
            Text(
                content="Demo users: alice / secret  ·  bob / p4ssw0rd",
                style=Style(font_size=12.0, color=Color.from_hex("#6b7280")),
                key="login-hint",
            ),
            Input(
                value=app.state.username,
                placeholder="Username",
                keyboard=KeyboardType.TEXT,
                on_change=on_username,
                key="username-input",
            ),
            Input(
                value=app.state.password,
                placeholder="Password",
                secure=True,
                keyboard=KeyboardType.PASSWORD,
                on_change=on_password,
                key="password-input",
            ),
            *error_widgets,
            Button(label="Sign in", on_click=do_login, key="login-btn"),
            _audit_trail(app.state.log_records),
        ],
    )


def _dashboard_screen(app: App[AuthAppState]) -> Widget:
    """Render the protected dashboard.

    Args:
        app: The application handle.

    Returns:
        A widget tree showing the user's token claims and a logout button.
    """
    token: str | None = app.state.store.token
    user: dict[str, Any] | None = app.state.store.user
    display_name: str = (
        str(user.get("name", user.get("sub", "User"))) if user else "User"
    )

    def do_logout() -> None:
        """Log out and return to the login screen.

        Returns:
            None.
        """
        uname: str = str(user.get("sub", "?")) if user else "?"
        app.state.log.info("logout", username=uname)
        app.state.store.logout()

        def on_logged_out(s: AuthAppState) -> None:
            s.current_route = "/login"

        app.set_state(on_logged_out)

    token_widget: Widget = (
        _token_badge(token)
        if token is not None
        else Text(content="No token.", key="no-token")
    )

    return Column(
        key="dashboard-screen",
        style=Style(gap=16.0, padding=Edge.all(24.0)),
        children=[
            Text(
                content=f"Welcome, {display_name}!",
                style=Style(
                    font_size=24.0,
                    font_weight=FontWeight.BOLD,
                    color=Color.from_hex("#1d4ed8"),
                ),
                key="dash-heading",
            ),
            Text(
                content=(
                    "This is a protected page. Only authenticated users can see it."
                ),
                style=Style(font_size=14.0, color=Color.from_hex("#374151")),
                key="dash-body",
            ),
            token_widget,
            Button(label="Log out", on_click=do_logout, key="logout-btn"),
            Column(
                key="audit-section",
                style=Style(gap=4.0),
                children=[
                    Text(
                        content="Audit trail",
                        style=Style(font_weight=FontWeight.BOLD, font_size=13.0),
                        key="audit-title",
                    ),
                    _audit_trail(app.state.log_records),
                ],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# view
# ---------------------------------------------------------------------------


def view(app: App[AuthAppState]) -> Widget:
    """Render the auth-gate app from the current application state.

    Uses ``route_guard`` to decide whether to show the login screen or the
    protected dashboard. The guard's decision is based on the ``AuthStore``
    held inside ``state``.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current auth + route state.
    """
    guard = route_guard(app.state.store, redirect_to="/login")
    effective_route: str = guard(app.state.current_route)

    if effective_route == "/dashboard":
        return _dashboard_screen(app)
    return _login_screen(app)
```

---

## Explicando peça por peça

### 1. Construindo JWTs para o demo

O app usa dois tokens pré-construídos — um válido (alice) e um expirado (bob) — para
demonstrar `decode_jwt` e `is_jwt_expired` de forma determinística em testes e na
renderização inicial.

```python
_DEMO_NOW: float = 1_800_000_000.0  # epoch fixo, bem no passado


def _b64url(obj: dict[str, Any]) -> str:
    raw: bytes = json.dumps(obj, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def make_jwt(claims: dict[str, Any]) -> str:
    header: str = _b64url({"alg": "none", "typ": "JWT"})
    payload: str = _b64url(claims)
    return f"{header}.{payload}.sig"


_ALICE_TOKEN: str = make_jwt(
    {"sub": "alice", "name": "Alice Souza", "role": "admin",
     "exp": int(_DEMO_NOW) + 3600}  # válido: 1 h depois do epoch demo
)

_BOB_TOKEN: str = make_jwt(
    {"sub": "bob", "name": "Bob Lima", "role": "user",
     "exp": int(_DEMO_NOW) - 3600}  # expirado: 1 h antes do epoch demo
)
```

Um JWT compacto tem três partes separadas por `.`: `header.payload.signature`.
Aqui a assinatura é literalmente a string `"sig"` — isso é suficiente para o
`decode_jwt` funcionar offline, porque ele **não verifica** a assinatura (esse é
um trabalho do servidor).

!!! warning "Nunca em produção"
    Tokens sem assinatura real (`alg: none`) são para demos e testes offline.
    Em produção, use `tempest_fastapi_sdk.JWTUtils` (lado servidor) para emitir
    e verificar tokens assinados com HMAC ou RS256. O cliente usa `decode_jwt`
    apenas para *ler* claims (exibição e decisão de renovação), nunca para
    *confiar* neles como autorização.

A tabela abaixo resume os dois usuários de demo:

| Usuário | Senha | Role | Expiração em `_DEMO_NOW` |
|---------|-------|------|--------------------------|
| alice | secret | admin | válido (+ 1 h) |
| bob | p4ssw0rd | user | expirado (− 1 h) |

---

### 2. O estado: `AuthStore` + `Logger` juntos

```python
@dataclass
class AuthAppState:
    store: AuthStore = field(default_factory=create_auth_store)
    log: Logger = field(init=False)
    username: str = ""
    password: str = ""
    error: str = ""
    log_records: list[LogRecord] = field(default_factory=list)
    current_route: str = "/dashboard"

    def __post_init__(self) -> None:
        def _append_sink(record: LogRecord) -> None:
            self.log_records.append(record)

        sink: LoggerSink = _append_sink
        self.log = create_logger(sinks=[sink], level="INFO")
```

Dois objetos especiais vivem no estado:

- **`store: AuthStore`** — criado por `create_auth_store()`. Guarda o token e o
  payload de usuário. Quando você chama `store.login(token, user_info)` ou
  `store.logout()`, o store notifica assinantes — o que em um app real dispararia
  um re-render automaticamente.

- **`log: Logger`** — criado em `__post_init__` com um sink que appenda os records
  a `log_records`. Isso fecha o loop: cada chamada `log.info(...)` ou
  `log.warning(...)` atualiza `log_records` no estado, que a `view` lê para
  renderizar o audit trail.

!!! tip "Dica: sinks são qualquer callable"
    `LoggerSink` é um `Protocol` com `__call__(record: LogRecord) -> None`.
    Isso significa que `list.append` já é um sink válido. No `__post_init__`
    usamos uma closure para acessar o atributo do dataclass, mas poderíamos
    escrever `create_logger(sinks=[self.log_records.append])` após o dataclass
    estar inicializado se o Python permitisse. A closure é a forma segura.

!!! note "Por que `log` é `field(init=False)`?"
    O `Logger` precisa de acesso ao `self.log_records`, que só existe depois que
    o dataclass é construído. `field(init=False)` garante que o `__post_init__`
    rode após todos os outros campos serem inicializados.

---

### 3. `create_auth_store` e `AuthStore`

```python
store: AuthStore = field(default_factory=create_auth_store)
```

`create_auth_store()` é um construtor conveniente que retorna um `AuthStore` vazio
(deslogado). O `AuthStore` expõe:

| Propriedade / Método | O que faz |
|----------------------|-----------|
| `store.token` | Retorna o token atual ou `None` |
| `store.user` | Retorna o payload de usuário ou `None` |
| `store.is_authenticated` | `True` se há um token presente |
| `store.login(token, user)` | Armazena o token + usuário, notifica assinantes |
| `store.logout()` | Limpa token e usuário, notifica assinantes |
| `store.set_token(token)` | Substitui só o token (ex.: após refresh) |
| `store.subscribe(fn)` | Registra um listener de mudança; retorna `unsubscribe` |

No app de demo, o store é consultado pelo `route_guard` e pelo `_dashboard_screen`
para exibir nome e token.

---

### 4. `route_guard`: protegendo rotas em uma linha

```python
def view(app: App[AuthAppState]) -> Widget:
    guard = route_guard(app.state.store, redirect_to="/login")
    effective_route: str = guard(app.state.current_route)

    if effective_route == "/dashboard":
        return _dashboard_screen(app)
    return _login_screen(app)
```

`route_guard(store, redirect_to="/login")` retorna uma função `guard`. Quando você
chama `guard("/dashboard")`:

- Se `store.is_authenticated` é `True` → devolve `"/dashboard"` inalterado.
- Se `store.is_authenticated` é `False` → devolve `"/login"` (o `redirect_to`).
- Se a rota solicitada já é `"/login"` → devolve `"/login"` sem loop infinito.

O resultado (`effective_route`) é o que a `view` usa para decidir qual sub-árvore
renderizar. Toda a lógica de guarda é capturada em uma chamada — não há
condicionais espalhadas pelo código.

!!! check "Sem dependência de router"
    `route_guard` é uma função pura — não depende de nenhum sistema de navegação.
    Você pode usá-la isoladamente (como nos testes unitários) ou junto ao router
    completo do tempestweb quando precisar de histórico e deep links.

---

### 5. `decode_jwt` e `is_jwt_expired`

O `_token_badge` usa os dois helpers para inspecionar o token sem fazer nenhuma
chamada de rede:

```python
def _token_badge(token: str) -> Widget:
    claims: dict[str, Any] = decode_jwt(token)
    expired: bool = is_jwt_expired(token, now=_DEMO_NOW)

    sub: str = str(claims.get("sub", "—"))
    role: str = str(claims.get("role", "—"))
    exp_label: str = "expired" if expired else "valid"
    exp_color: Color = (
        Color.from_hex("#dc2626") if expired else Color.from_hex("#16a34a")
    )
    ...
```

**`decode_jwt(token)`** divide o JWT em três partes pelo `.`, pega o segmento do
meio (payload), decodifica o base64url e deserializa o JSON. Devolve um
`dict[str, Any]` com os claims — `sub`, `role`, `exp`, etc. Se o token for
malformado, lança `JWTError`.

**`is_jwt_expired(token, now=_DEMO_NOW)`** chama `decode_jwt` internamente, lê o
claim `exp` e compara com `now`. O parâmetro `now` é opcional (padrão:
`time.time()`); neste app usamos `_DEMO_NOW` para tornar os testes determinísticos.

!!! info "Resultado com os tokens de demo"
    - `is_jwt_expired(_ALICE_TOKEN, now=_DEMO_NOW)` → `False` (válido)
    - `is_jwt_expired(_BOB_TOKEN, now=_DEMO_NOW)` → `True` (expirado)

    Ao fazer login com alice, o badge aparece verde ("valid"). Isso acontece porque
    `_ALICE_TOKEN.exp = _DEMO_NOW + 3600` e `_DEMO_NOW < _DEMO_NOW + 3600`.

!!! warning "Sem verificação de assinatura"
    `decode_jwt` é propositalmente client-side: ele lê os claims para o cliente
    decidir *quando* renovar o token e *o que mostrar* na UI. A validade
    criptográfica do token é responsabilidade do servidor — use
    `server_decode_jwt(token, secret)` no lado FastAPI (Modo B).

---

### 6. O Logger e o audit trail

```python
app.state.log.info(
    "login successful",
    username=username,
    role=str(claims.get("role", "?")),
)
```

O `Logger` tem métodos de nível convencional: `debug`, `info`, `warning`, `error`,
`critical`. Cada um aceita uma mensagem e campos estruturados arbitrários como
`**kwargs`. O que chega ao sink é um `LogRecord`:

```python
@dataclass(frozen=True)
class LogRecord:
    level: LogLevel          # "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL"
    message: str
    fields: dict[str, Any]   # os kwargs passados na chamada
```

No app, o sink que criamos no `__post_init__` appenda cada record a
`state.log_records`. A `_audit_trail` renderiza os últimos 5:

```python
def _audit_trail(records: list[LogRecord]) -> Widget:
    if not records:
        return Row(
            key="audit-empty",
            children=[
                Text(
                    content="No log entries yet.",
                    style=Style(color=Color.from_hex("#6b7280"), font_size=12.0),
                    key="audit-empty-text",
                )
            ],
        )

    entries: list[Widget] = [
        Text(
            content=f"[{r.level}] {r.message}",
            style=Style(font_size=12.0, color=Color.from_hex("#374151")),
            key=f"audit-{i}",
        )
        for i, r in enumerate(records[-5:])
    ]
    return Column(key="audit-records", style=Style(gap=2.0), children=entries)
```

!!! tip "Dica: múltiplos sinks em paralelo"
    `create_logger(sinks=[sink_a, sink_b], level="INFO")` entrega cada record a
    `sink_a` e `sink_b`. Se um sink lançar exceção, os demais ainda recebem o
    record — um destino quebrado não derruba o logging. Isso é útil para logar
    simultaneamente na UI (sink de estado) e num servidor remoto (sink HTTP).

---

### 7. O handler de login passo a passo

```python
def do_login() -> None:
    username: str = app.state.username.strip()
    password: str = app.state.password

    entry: tuple[str, str] | None = _CREDENTIALS.get(username)
    if entry is None or entry[0] != password:
        app.state.log.warning("login failed", username=username)

        def set_error(s: AuthAppState) -> None:
            s.error = "Invalid username or password."

        app.set_state(set_error)
        return

    _pw, token = entry
    claims: dict[str, Any] = decode_jwt(token)
    app.state.log.info(
        "login successful",
        username=username,
        role=str(claims.get("role", "?")),
    )
    user_info: dict[str, Any] = {
        "sub": username,
        "name": claims.get("name", username),
    }
    app.state.store.login(token, user_info)

    def on_logged_in(s: AuthAppState) -> None:
        s.error = ""
        s.username = ""
        s.password = ""
        s.current_route = "/dashboard"

    app.set_state(on_logged_in)
```

O fluxo em ordem:

1. Busca as credenciais no dicionário `_CREDENTIALS`.
2. Se não encontrou ou a senha não bate → `log.warning(...)` + `state.error`.
3. Se encontrou → `decode_jwt(token)` para ler o `role`.
4. `log.info(...)` registra o sucesso com campos estruturados.
5. `store.login(token, user_info)` — armazena o token e notifica assinantes.
6. `app.set_state(on_logged_in)` — limpa os campos e seta `current_route = "/dashboard"`.

Na próxima chamada da `view`, o `route_guard` recebe `"/dashboard"` e
`store.is_authenticated == True`, então deixa passar e `_dashboard_screen` é
renderizado.

---

### 8. O handler de logout

```python
def do_logout() -> None:
    uname: str = str(user.get("sub", "?")) if user else "?"
    app.state.log.info("logout", username=uname)
    app.state.store.logout()

    def on_logged_out(s: AuthAppState) -> None:
        s.current_route = "/login"

    app.set_state(on_logged_out)
```

`store.logout()` limpa `_token` e `_user` e notifica assinantes. Em seguida
`current_route` é setado para `"/login"`. Na próxima `view`, o `route_guard`
recebe `"/login"` com `store.is_authenticated == False` — mas como `"/login"` é
o próprio `redirect_to`, o guard devolve `"/login"` sem loop — e o login screen
é renderizado.

!!! info "Por que não basta chamar `store.logout()`?"
    O `store.logout()` limpa o estado interno do store. O `current_route` é um
    campo separado no `AuthAppState`. Atualizar os dois juntos num único
    `set_state` garante que o próximo render seja consistente: route + auth
    mudam atomicamente do ponto de vista do reconciliador.

---

## Rodando o app 🚀

Salve o arquivo em `examples/auth-jwt/app.py` e escolha o modo:

=== "Modo WASM (Python no browser)"

    ```bash
    tempestweb dev --mode wasm --path examples/auth-jwt
    ```

    O Pyodide carrega o Python completo no browser. `decode_jwt`, `is_jwt_expired`,
    `AuthStore` e `Logger` rodam inteiramente no tab — sem WebSocket, sem servidor.

=== "Modo Server (FastAPI + WebSocket)"

    ```bash
    tempestweb dev --mode server --path examples/auth-jwt
    ```

    Um servidor FastAPI sobe localmente. O cliente JS envia eventos de input e
    click e recebe patches do reconciliador via WebSocket. O `app.py` não muda.

!!! check "Mesmo código, dois modos"
    O `app.py` não referencia `wasm` nem `server` em nenhum lugar. Não há bridge
    necessária: nenhuma capability nativa é chamada na montagem inicial, então
    `build(view(app))` é verde sem bridge instalada.

Abra o browser em `http://localhost:8000`. Experimente os cenários:

1. **Login com alice / secret** → dashboard com badge verde ("valid").
2. **Login com bob / p4ssw0rd** → dashboard com badge vermelho ("expired").
3. **Senha errada** → mensagem de erro em vermelho, `state.error` setado.
4. **Logout** → tela de login, audit trail com registro de logout.
5. **Navegação direta para `/dashboard` sem login** → `route_guard` redireciona
   para `/login`.

---

## Rodando os testes ✅

```bash
pytest tests/unit/test_example_auth_jwt.py -v
```

Os 20 testes cobrem:

| Grupo | O que verifica |
|-------|----------------|
| **Montagem inicial** | `build(view(app))` produz árvore válida; tela é login; store começa deslogado |
| **Login com alice** | `is_authenticated` vira `True`; dashboard renderiza; log record INFO é escrito; `diff` detecta mudança de árvore |
| **JWT / expiração** | `_ALICE_TOKEN` não expirado em `_DEMO_NOW`; `_BOB_TOKEN` expirado; `decode_jwt` devolve claims corretos; badge aparece no dashboard |
| **Falha de login** | Senha errada mantém `is_authenticated = False`; `state.error` preenchido; tela permanece login; log WARNING escrito |
| **Logout** | `is_authenticated` vira `False`; token limpo; tela volta para login; log INFO escrito |
| **`route_guard` standalone** | Não autenticado → `/login`; autenticado → `/dashboard`; `"/login"` nunca redireciona |

---

## Recapitulando

Neste exemplo você aprendeu:

- ✅ **`create_auth_store` / `AuthStore`** — loja observável que guarda token e
  usuário; `login` / `logout` / `is_authenticated` / `subscribe`.
- ✅ **`route_guard`** — guarda de rota puro que redireciona requests não
  autenticados; sem loop em `redirect_to`.
- ✅ **`decode_jwt`** — decodificação offline do payload do JWT (sem verificação de
  assinatura); retorna `dict[str, Any]`.
- ✅ **`is_jwt_expired`** — verifica o claim `exp` contra um `now` configurável;
  token sem `exp` nunca expira; token malformado trata como expirado.
- ✅ **`create_logger` / `Logger` / `LogRecord` / `LoggerSink`** — log estruturado
  com threshold por nível; múltiplos sinks em paralelo; sink quebrado não afeta
  os demais.
- ✅ **Sink de estado** — fechar o loop entre `Logger` e `view` usando uma closure
  que appenda records a `state.log_records`, fazendo o audit trail re-renderizar
  automaticamente.
- ✅ **JWTs unsigned para demos/testes** — `header.payload.sig` é suficiente para
  exercitar `decode_jwt` e `is_jwt_expired` offline de forma determinística.

---

## Próximos passos

- Leia [Formulário de Login](./login-form.md) para ver validação em três camadas
  com `Form` + `FormField` + `Banner`.
- Explore o exemplo de [Dashboard Shell](./dashboard-shell.md) para ver como o
  `AuthStore` se integra a um layout com barra lateral e header.
- Veja [Notification Center](./notification-center.md) para usar `Logger` com
  um sink que alimenta um painel de notificações ao vivo.
- Consulte a referência de [`tempestweb.observability`](../observability.md)
  para a lista completa de métodos do `AuthStore` e do `RefreshQueue`.
