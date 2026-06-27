# PWA Install + WebPush — Notificações Push no Browser 📱

Construa um app **instalável** que pede permissão de notificação ao usuário e,
uma vez concedida, cria uma assinatura **WebPush** — tudo escrito em Python
puro, sem nenhuma linha de JavaScript de aplicação. O mesmo código funciona no
**Modo A** (Python no browser via Pyodide) e no **Modo B** (Python no servidor
via FastAPI + WebSocket).

---

## O que você vai construir

Um fluxo de consentimento PWA/WebPush com **7 fases**:

| Fase | Descrição |
|---|---|
| `IDLE` | Estado inicial — o usuário ainda não interagiu |
| `REQUESTING` | Aguardando a resposta do prompt de permissão do browser |
| `DENIED` | O usuário bloqueou as notificações |
| `GRANTED` | Permissão concedida; assinatura ainda não solicitada |
| `SUBSCRIBING` | Aguardando a criação da assinatura push no browser |
| `SUBSCRIBED` | Totalmente assinado; `subscription` dict disponível |
| `ERROR` | Erro inesperado; campo `error` preenchido |

Além disso, você vai gerar os **artefatos PWA** — `manifest.webmanifest` + conjunto
de ícones PNG válidos — com o script `build_pwa.py`, tudo via Python puro (sem
Pillow, sem dependências externas de imagem).

!!! note "Nota — onde o WebPush realmente acontece"
    O browser é quem executa a Web API de permissão e o `pushManager`. O Python
    apenas **envia** o pedido via `native_call` e **recebe** o resultado. No
    **Modo A**, a chamada vai direto ao `client/native/*.js` via FFI do Pyodide. No
    **Modo B**, ela trafega pelo WebSocket até o browser e volta como
    `native_result`. A sua `view` não precisa saber qual modo está rodando.

---

## Pré-requisitos

```bash
pip install tempestweb
```

Leitura recomendada (opcional):

- [Tutorial básico](../tutorial/index.md) — primeiros passos com `App`, `view` e `set_state`
- [Modos de execução](../tutorial/modes.md) — WASM vs. servidor
- [PWA e offline](../pwa.md) — camada P do roadmap

---

## Criando o projeto

```bash
mkdir -p examples/pwa-webpush
touch examples/pwa-webpush/app.py
touch examples/pwa-webpush/build_pwa.py
```

---

## Passo 1 — Modelando a máquina de estados

Todo app tempestweb começa pelo **estado**. Aqui o estado é uma máquina de fases
explícita com dois callables injetados. Essa injeção é o segredo para testes
determinísticos: você substitui `request_permission` e `subscribe` por fakes sem
precisar de um browser de verdade.

```python
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from tempestweb.native import notifications
from tempestweb.native.notifications import NotificationPermission

#: Chave VAPID pública usada por padrão (placeholder; troque pela sua em produção).
DEMO_VAPID_KEY: str = (
    "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuB"
    "kr3qBUYIHBQFLXYp5Nksh8U"
)

#: Assinatura do coroutine injetado para pedir permissão.
PermissionRequester = Callable[[], Awaitable[NotificationPermission]]

#: Assinatura do coroutine injetado para criar a assinatura push.
Subscriber = Callable[[str], Awaitable[dict[str, Any]]]


class Phase(StrEnum):
    """Fases do fluxo de consentimento PWA/WebPush."""

    IDLE = "idle"
    REQUESTING = "requesting"
    DENIED = "denied"
    GRANTED = "granted"
    SUBSCRIBING = "subscribing"
    SUBSCRIBED = "subscribed"
    ERROR = "error"


@dataclass
class State:
    """Estado top-level do app PWA WebPush Demo.

    Attributes:
        phase: Fase atual do ciclo de vida.
        subscription: Dict da assinatura push quando em SUBSCRIBED.
        error: Mensagem de erro em Phase.ERROR.
        vapid_key: Chave pública VAPID passada para subscribe.
        request_permission: Coroutine injetado para o pedido de permissão.
        subscribe: Coroutine injetado para a assinatura push.
    """

    phase: Phase = Phase.IDLE
    subscription: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    vapid_key: str = DEMO_VAPID_KEY
    request_permission: PermissionRequester = notifications.request_permission
    subscribe: Subscriber = notifications.subscribe


def make_state() -> State:
    """Constrói o estado inicial com os callables reais como padrão.

    Returns:
        Um novo :class:`State` na fase IDLE.
    """
    return State()
```

!!! tip "Dica — injeção de dependência via dataclass"
    Os campos `request_permission` e `subscribe` têm os callables reais
    (`tempestweb.native.notifications.*`) como valores padrão, então o app roda
    de verdade sem nenhuma configuração. Nos testes, você sobreescreve esses
    campos com fakes — sem monkey-patching, sem mocks globais.

---

## Passo 2 — Os handlers assíncronos

Os handlers ficam dentro de `view()` e são closures sobre `app`. Cada um muda a
fase para um estado de "loading" imediatamente, chama o callable injetado, e
atualiza o estado de acordo com o resultado (ou o erro).

```python
async def handle_request_permission() -> None:
    """Pede permissão de notificação ao browser e atualiza o estado."""
    app.set_state(lambda s: setattr(s, "phase", Phase.REQUESTING))
    try:
        perm = await app.state.request_permission()
    except Exception as exc:  # noqa: BLE001 — surface error to the UI
        message = str(exc)

        def on_error(s: State) -> None:
            s.phase = Phase.ERROR
            s.error = message

        app.set_state(on_error)
        return

    if perm is NotificationPermission.GRANTED:
        app.set_state(lambda s: setattr(s, "phase", Phase.GRANTED))
    elif perm is NotificationPermission.DENIED:
        app.set_state(lambda s: setattr(s, "phase", Phase.DENIED))
    else:
        # DEFAULT — o usuário dispensou o prompt; volta para IDLE
        app.set_state(lambda s: setattr(s, "phase", Phase.IDLE))


async def handle_subscribe() -> None:
    """Cria a assinatura WebPush com a chave VAPID armazenada e atualiza o estado."""
    app.set_state(lambda s: setattr(s, "phase", Phase.SUBSCRIBING))
    try:
        sub = await app.state.subscribe(app.state.vapid_key)
    except Exception as exc:  # noqa: BLE001 — surface error to the UI
        message = str(exc)

        def on_error(s: State) -> None:
            s.phase = Phase.ERROR
            s.error = message

        app.set_state(on_error)
        return

    def on_subscribed(s: State) -> None:
        s.phase = Phase.SUBSCRIBED
        s.subscription = sub

    app.set_state(on_subscribed)


def handle_reset() -> None:
    """Volta o estado para IDLE."""

    def reset(s: State) -> None:
        s.phase = Phase.IDLE
        s.subscription = {}
        s.error = ""

    app.set_state(reset)
```

!!! info "Nota — `Phase.REQUESTING` e `Phase.SUBSCRIBING`"
    Setar a fase para "loading" **antes** de aguardar o callable garante que a UI
    mostre um `Spinner` imediatamente. Se você só atualizasse depois do `await`,
    o usuário ficaria olhando para um botão que não reage durante todo o prompt
    do browser.

---

## Passo 3 — Construindo a árvore de widgets

A `view` é pura: lê `app.state`, decide quais widgets mostrar e retorna a árvore.
O reconciliador calcula o diff e atualiza o DOM com o mínimo de mudanças.

```python
from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import Button, Column, Row, Spinner, Text


def view(app: App[State]) -> Widget:
    """Renderiza a UI de consentimento PWA/WebPush a partir do estado atual.

    Args:
        app: O handle da aplicação que expõe ``state`` e ``set_state``.

    Returns:
        A árvore de widgets para o estado atual.
    """
    # ... handlers definidos aqui (ver Passo 2)

    phase = app.state.phase

    status_messages: dict[Phase, str] = {
        Phase.IDLE: "Notifications are not yet enabled.",
        Phase.REQUESTING: "Waiting for browser permission…",
        Phase.DENIED: (
            "Permission denied. You can re-enable notifications"
            " in your browser settings."
        ),
        Phase.GRANTED: (
            "Permission granted. You can now subscribe to push notifications."
        ),
        Phase.SUBSCRIBING: "Creating push subscription…",
        Phase.SUBSCRIBED: "Successfully subscribed to push notifications!",
        Phase.ERROR: f"Error: {app.state.error}",
    }

    status_text: Widget = Text(
        content=status_messages[phase],
        key="status-text",
    )

    children: list[Widget] = [
        Text(
            content="PWA WebPush Demo",
            style=Style(font_size=22.0),
            key="title",
        ),
        Text(
            content="Enable browser push notifications to receive real-time updates.",
            style=Style(font_size=14.0),
            key="subtitle",
        ),
        status_text,
    ]

    if phase is Phase.REQUESTING or phase is Phase.SUBSCRIBING:
        children.append(
            Row(
                style=Style(gap=8.0),
                children=[
                    Spinner(key="loading-spinner"),
                    Text(
                        content=(
                            "Requesting permission…"
                            if phase is Phase.REQUESTING
                            else "Subscribing…"
                        ),
                        key="loading-label",
                    ),
                ],
                key="loading-row",
            )
        )
    elif phase is Phase.IDLE or phase is Phase.DENIED:
        children.append(
            Button(
                label="Enable notifications",
                on_click=handle_request_permission,
                key="btn-enable",
            )
        )
        if phase is Phase.DENIED:
            children.append(
                Button(
                    label="Try again",
                    on_click=handle_request_permission,
                    key="btn-retry",
                )
            )
    elif phase is Phase.GRANTED:
        children.append(
            Button(
                label="Subscribe to push",
                on_click=handle_subscribe,
                key="btn-subscribe",
            )
        )
    elif phase is Phase.SUBSCRIBED:
        endpoint = app.state.subscription.get("endpoint", "")
        children.append(
            Column(
                style=Style(gap=4.0, padding=Edge.all(12.0)),
                children=[
                    Text(content="Subscription endpoint:", key="sub-label"),
                    Text(
                        content=endpoint[:64] + "…" if len(endpoint) > 64 else endpoint,
                        key="sub-endpoint",
                    ),
                ],
                key="sub-details",
            )
        )
        children.append(
            Button(
                label="Reset",
                on_click=handle_reset,
                key="btn-reset",
            )
        )
    elif phase is Phase.ERROR:
        children.append(
            Button(
                label="Try again",
                on_click=handle_reset,
                key="btn-error-reset",
            )
        )

    return Column(
        style=Style(gap=16.0, padding=Edge.all(24.0)),
        children=children,
    )
```

!!! tip "Dica — `if phase is Phase.X` vs `elif`"
    A cadeia `if / elif` na `view` é a máquina de estados **invertida**: em vez de
    transições, você declara *o que mostrar em cada fase*. O reconciliador detecta
    as diferenças entre renders e atualiza só o que mudou no DOM.

---

## Passo 4 — O script de build PWA

O `build_pwa.py` gera os artefatos instaláveis — `manifest.webmanifest` e o
conjunto de ícones — e os valida contra os critérios do Chromium/Lighthouse.
Rode-o separadamente antes de fazer deploy.

```python
"""PWA build script — emite manifest.webmanifest + conjunto de ícones."""

from __future__ import annotations

import json
from pathlib import Path

from tempestweb.pwa import (
    ManifestOptions,
    emit_icons,
    validate_installable,
    write_manifest,
)

#: Metadados do app para este demo.
OPTIONS: ManifestOptions = ManifestOptions(
    name="PWA WebPush Demo",
    short_name="WebPush",
    description="A tempestweb demo that shows PWA install and WebPush notifications.",
    start_url="/",
    scope="/",
    display="standalone",
    theme_color="#111827",
    background_color="#f9fafb",
    lang="pt-BR",
    categories=["utilities"],
)


def main(dest: Path | None = None) -> dict[str, list[str | Path]]:
    """Emite o manifest e o conjunto de ícones em ``dest``, depois valida.

    Args:
        dest: Diretório raiz de saída. Padrão: ``<raiz do repo>/build``.

    Returns:
        Dict com ``"manifest"`` (caminho do manifest) e ``"icons"`` (lista de paths).
    """
    if dest is None:
        dest = Path(__file__).resolve().parents[2] / "build"

    # 1. Escreve manifest.webmanifest
    manifest_path = write_manifest(dest / "manifest.webmanifest", options=OPTIONS)

    # 2. Emite o conjunto de ícones
    icon_paths = emit_icons(dest / "icons")

    # 3. Valida instalabilidade (deve retornar [])
    manifest_dict = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = validate_installable(manifest_dict)

    print(f"manifest  -> {manifest_path}")
    print(f"icons     -> {len(icon_paths)} files under {dest / 'icons'}")
    print(f"installable? {errors if errors else '✓ yes (no errors)'}")

    return {
        "manifest": [manifest_path],
        "icons": icon_paths,
    }


if __name__ == "__main__":
    main()
```

Execute assim:

```bash
python examples/pwa-webpush/build_pwa.py
```

Saída esperada:

```
manifest  -> /caminho/para/build/manifest.webmanifest
icons     -> 5 files under /caminho/para/build/icons
installable? ✓ yes (no errors)
```

!!! info "O que `validate_installable` verifica?"
    Os critérios do Chromium/Lighthouse para PWA instalável:

    - `name` **ou** `short_name` preenchido
    - `start_url` preenchido
    - `display` em `{"standalone", "fullscreen", "minimal-ui"}`
    - Um ícone PNG 192×192 presente
    - Um ícone PNG 512×512 presente
    - Pelo menos um ícone com `purpose` contendo `"any"`

    Uma lista vazia (`[]`) significa que o app está pronto para instalação.

### Os campos de `ManifestOptions`

| Campo | Tipo | Descrição |
|---|---|---|
| `name` | `str` | Nome completo do app |
| `short_name` | `str` | Rótulo na tela inicial |
| `description` | `str` | Descrição humana |
| `start_url` | `str` | URL aberta ao lançar |
| `scope` | `str` | Escopo de navegação |
| `display` | `str` | Modo de display (`"standalone"`, `"fullscreen"`, `"minimal-ui"`) |
| `theme_color` | `str` | Cor da barra de ferramentas (CSS color) |
| `background_color` | `str` | Fundo do splash (CSS color) |
| `lang` | `str` | Tag BCP-47 do idioma |
| `categories` | `list[str]` | Categorias na loja de apps |
| `icons` | `list[dict]` | Substitui `DEFAULT_ICONS` quando preenchido |
| `shortcuts` | `list[dict]` | Atalhos P5 (avançado) |
| `share_target` | `dict \| None` | Alvo de compartilhamento P5 |
| `file_handlers` | `list[dict]` | Handlers de arquivo P5 |

---

## O app completo

Aqui está o `app.py` completo, pronto para copiar:

```python
"""PWA install + WebPush demo — exercises notification permission + subscription.

Like :mod:`examples.counter.app`, this exact ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

This example demonstrates the PWA/WebPush flow:

1. The user presses **Enable notifications** — the app calls
   :func:`~tempestweb.native.notifications.request_permission` and stores the
   resulting :class:`~tempestweb.native.notifications.NotificationPermission`.
2. If permission is *granted*, the button changes to **Subscribe to push** —
   pressing it calls :func:`~tempestweb.native.notifications.subscribe` with the
   injected VAPID public key and stores the raw subscription dict returned by the
   browser.
3. The current status (idle / requesting / subscribing / subscribed / denied) is
   rendered in a :class:`~tempest_core.widgets.Text` feedback label so the user
   always sees what happened.

State machine
-------------
* ``Phase.IDLE``         — initial; the user has not interacted yet.
* ``Phase.REQUESTING``   — :func:`request_permission` is in flight.
* ``Phase.DENIED``       — the user blocked notifications.
* ``Phase.GRANTED``      — permission granted; subscription not yet requested.
* ``Phase.SUBSCRIBING``  — :func:`subscribe` is in flight.
* ``Phase.SUBSCRIBED``   — fully subscribed; ``subscription`` dict is populated.
* ``Phase.ERROR``        — unexpected error; ``error`` field has the message.

Dependency injection
--------------------
Both async callables (``request_permission`` and ``subscribe``) are injected
into ``State`` so :func:`build` is deterministic with *no bridge installed*.
The initial mount only reads ``app.state`` — the callables are never invoked
until the user presses a button.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import Button, Column, Row, Spinner, Text
from tempestweb.native import notifications
from tempestweb.native.notifications import NotificationPermission

#: Default VAPID public key used when none is injected (placeholder only;
#: a real app replaces this with its own server key).
DEMO_VAPID_KEY: str = (
    "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuB"
    "kr3qBUYIHBQFLXYp5Nksh8U"
)

# ---------------------------------------------------------------------------
# Injected callable types
# ---------------------------------------------------------------------------

#: Signature of the injected permission-request coroutine.
PermissionRequester = Callable[[], Awaitable[NotificationPermission]]

#: Signature of the injected subscribe coroutine.
Subscriber = Callable[[str], Awaitable[dict[str, Any]]]


# ---------------------------------------------------------------------------
# Phase
# ---------------------------------------------------------------------------


class Phase(StrEnum):
    """Lifecycle phases of the PWA WebPush consent flow.

    Attributes:
        IDLE: No user action yet.
        REQUESTING: Awaiting the browser permission prompt.
        DENIED: The user denied notification permission.
        GRANTED: Permission granted; WebPush subscription not yet requested.
        SUBSCRIBING: Awaiting the browser push subscription creation.
        SUBSCRIBED: Fully subscribed; ``subscription`` dict is available.
        ERROR: An unexpected error occurred.
    """

    IDLE = "idle"
    REQUESTING = "requesting"
    DENIED = "denied"
    GRANTED = "granted"
    SUBSCRIBING = "subscribing"
    SUBSCRIBED = "subscribed"
    ERROR = "error"


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class State:
    """Top-level state for the PWA WebPush demo app.

    Attributes:
        phase: Current lifecycle phase.
        subscription: The raw push subscription dict once subscribed.
        error: Human-readable error message, populated in ``Phase.ERROR``.
        vapid_key: VAPID public key passed to :func:`subscribe`.
        request_permission: Injected coroutine for the permission request.
        subscribe: Injected coroutine for the push subscription.
    """

    phase: Phase = Phase.IDLE
    subscription: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    vapid_key: str = DEMO_VAPID_KEY
    request_permission: PermissionRequester = notifications.request_permission
    subscribe: Subscriber = notifications.subscribe


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_state() -> State:
    """Build the initial idle state with real capability defaults.

    Returns:
        A fresh :class:`State` in the ``IDLE`` phase.
    """
    return State()


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[State]) -> Widget:
    """Render the PWA/WebPush consent UI from the current state.

    The view is a single :class:`~tempest_core.widgets.Column` containing:

    * A title.
    * A status feedback text that reflects the current phase.
    * A primary action button (changes label and handler per phase).
    * A subscription details section once fully subscribed.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    # ------------------------------------------------------------------
    # Async handlers
    # ------------------------------------------------------------------

    async def handle_request_permission() -> None:
        """Ask the browser for notification permission and update state."""
        app.set_state(lambda s: setattr(s, "phase", Phase.REQUESTING))
        try:
            perm = await app.state.request_permission()
        except Exception as exc:  # noqa: BLE001 — surface error to the UI
            message = str(exc)

            def on_error(s: State) -> None:
                s.phase = Phase.ERROR
                s.error = message

            app.set_state(on_error)
            return

        if perm is NotificationPermission.GRANTED:
            app.set_state(lambda s: setattr(s, "phase", Phase.GRANTED))
        elif perm is NotificationPermission.DENIED:
            app.set_state(lambda s: setattr(s, "phase", Phase.DENIED))
        else:
            # DEFAULT — the user dismissed the prompt; stay at IDLE
            app.set_state(lambda s: setattr(s, "phase", Phase.IDLE))

    async def handle_subscribe() -> None:
        """Subscribe to WebPush using the stored VAPID key and update state."""
        app.set_state(lambda s: setattr(s, "phase", Phase.SUBSCRIBING))
        try:
            sub = await app.state.subscribe(app.state.vapid_key)
        except Exception as exc:  # noqa: BLE001 — surface error to the UI
            message = str(exc)

            def on_error(s: State) -> None:
                s.phase = Phase.ERROR
                s.error = message

            app.set_state(on_error)
            return

        def on_subscribed(s: State) -> None:
            s.phase = Phase.SUBSCRIBED
            s.subscription = sub

        app.set_state(on_subscribed)

    def handle_reset() -> None:
        """Reset state back to IDLE."""

        def reset(s: State) -> None:
            s.phase = Phase.IDLE
            s.subscription = {}
            s.error = ""

        app.set_state(reset)

    # ------------------------------------------------------------------
    # Status label
    # ------------------------------------------------------------------

    phase = app.state.phase

    status_messages: dict[Phase, str] = {
        Phase.IDLE: "Notifications are not yet enabled.",
        Phase.REQUESTING: "Waiting for browser permission…",
        Phase.DENIED: (
            "Permission denied. You can re-enable notifications"
            " in your browser settings."
        ),
        Phase.GRANTED: (
            "Permission granted. You can now subscribe to push notifications."
        ),
        Phase.SUBSCRIBING: "Creating push subscription…",
        Phase.SUBSCRIBED: "Successfully subscribed to push notifications!",
        Phase.ERROR: f"Error: {app.state.error}",
    }

    status_text: Widget = Text(
        content=status_messages[phase],
        key="status-text",
    )

    # ------------------------------------------------------------------
    # Primary action button
    # ------------------------------------------------------------------

    children: list[Widget] = [
        Text(
            content="PWA WebPush Demo",
            style=Style(font_size=22.0),
            key="title",
        ),
        Text(
            content="Enable browser push notifications to receive real-time updates.",
            style=Style(font_size=14.0),
            key="subtitle",
        ),
        status_text,
    ]

    if phase is Phase.REQUESTING or phase is Phase.SUBSCRIBING:
        children.append(
            Row(
                style=Style(gap=8.0),
                children=[
                    Spinner(key="loading-spinner"),
                    Text(
                        content=(
                            "Requesting permission…"
                            if phase is Phase.REQUESTING
                            else "Subscribing…"
                        ),
                        key="loading-label",
                    ),
                ],
                key="loading-row",
            )
        )
    elif phase is Phase.IDLE or phase is Phase.DENIED:
        children.append(
            Button(
                label="Enable notifications",
                on_click=handle_request_permission,
                key="btn-enable",
            )
        )
        if phase is Phase.DENIED:
            children.append(
                Button(
                    label="Try again",
                    on_click=handle_request_permission,
                    key="btn-retry",
                )
            )
    elif phase is Phase.GRANTED:
        children.append(
            Button(
                label="Subscribe to push",
                on_click=handle_subscribe,
                key="btn-subscribe",
            )
        )
    elif phase is Phase.SUBSCRIBED:
        endpoint = app.state.subscription.get("endpoint", "")
        children.append(
            Column(
                style=Style(gap=4.0, padding=Edge.all(12.0)),
                children=[
                    Text(content="Subscription endpoint:", key="sub-label"),
                    Text(
                        content=endpoint[:64] + "…" if len(endpoint) > 64 else endpoint,
                        key="sub-endpoint",
                    ),
                ],
                key="sub-details",
            )
        )
        children.append(
            Button(
                label="Reset",
                on_click=handle_reset,
                key="btn-reset",
            )
        )
    elif phase is Phase.ERROR:
        children.append(
            Button(
                label="Try again",
                on_click=handle_reset,
                key="btn-error-reset",
            )
        )

    return Column(
        style=Style(gap=16.0, padding=Edge.all(24.0)),
        children=children,
    )
```

---

## Rodando o exemplo ▶

### Modo A — Python no browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm examples/pwa-webpush/app.py
```

O Python roda **dentro do browser** via Pyodide. A chamada `request_permission`
vai diretamente ao `client/native/notifications.js` via FFI — sem servidor,
sem rede extra.

### Modo B — Python no servidor (FastAPI + WebSocket)

```bash
tempestweb dev --mode server examples/pwa-webpush/app.py
```

O Python roda no servidor. Cada `await app.state.request_permission()` serializa
um envelope `native_call`, envia pelo WebSocket até o browser, aguarda a resposta
`native_result` e retoma a coroutine.

!!! check "Verificação"
    Em qualquer modo, você deve ver:

    1. Título "PWA WebPush Demo" e subtítulo descritivo
    2. Status label: "Notifications are not yet enabled."
    3. Botão **Enable notifications**
    4. Clique no botão → label muda para "Waiting for browser permission…" + Spinner
    5. Conceda a permissão no prompt do browser → botão muda para **Subscribe to push**
    6. Clique em **Subscribe to push** → Spinner aparece novamente
    7. Após a assinatura: seção "Subscription endpoint:" e botão **Reset**
    8. Clique em **Reset** → volta para o estado inicial

!!! warning "Aviso — permissão no browser"
    O prompt de permissão de notificação só aparece em páginas servidas via
    **HTTPS** ou **localhost**. No `tempestweb dev` local, `localhost` funciona.
    Em produção, você precisa de HTTPS.

---

## Como funciona a ponte nativa

O diagrama abaixo mostra o caminho de uma chamada `request_permission` no
**Modo B** (servidor):

```
Python view()
    │
    ├─ await app.state.request_permission()
    │       │
    │       ▼
    │  send_native_call("notifications.request_permission", {})
    │       │
    │       ▼
    │  ProxyBridge.call(envelope)  ── native_call ──► browser (WS)
    │       │                                              │
    │       │                           client/native/notifications.js
    │       │                           Notification.requestPermission()
    │       │                                              │
    │       │◄────────── native_result ◄──────────────────┘
    │       │
    │  resolve_native_result(call_id, payload)
    │       │
    └─ NotificationPermission.GRANTED / DENIED / DEFAULT
```

No **Modo A** (WASM), a mesma chamada Python vai direto ao JavaScript via FFI
do Pyodide — sem nenhum round-trip de rede.

!!! info "Nota — `install_bridge` / `uninstall_bridge`"
    O bootstrap do runtime (Modo A ou B) chama `install_bridge(bridge)` uma vez.
    Nos testes, você faz o mesmo com um `_FakeBridge` e chama `uninstall_bridge()`
    no teardown para garantir isolamento entre testes.

---

## Gerando os artefatos PWA

### Rodando o script de build

```bash
python examples/pwa-webpush/build_pwa.py
```

Isso cria em `build/`:

```
build/
├── manifest.webmanifest
└── icons/
    ├── icon-192.png
    ├── icon-512.png
    ├── maskable-192.png
    ├── maskable-512.png
    └── apple-touch-icon.png
```

### Validando instalabilidade diretamente

```python
import json
from pathlib import Path
from tempestweb.pwa import validate_installable

manifest = json.loads(Path("build/manifest.webmanifest").read_text())
errors = validate_installable(manifest)
print(errors)  # [] significa instalável
```

### Usando em outro script

`build_pwa.main(dest)` é importável — você pode apontar `dest` para um `tmp_path`
do pytest ou para um diretório de deploy customizado:

```python
from pathlib import Path
from examples.pwa_webpush import build_pwa

result = build_pwa.main(Path("/meu/deploy/dir"))
print(result["manifest"])  # [Path('/meu/deploy/dir/manifest.webmanifest')]
print(len(result["icons"]))  # 5
```

---

## Verificação automatizada ✅

Rode os quatro checks antes de commitar:

```bash
# Lint
ruff check .

# Formatação
ruff format --check .

# Tipos
mypy --strict tempestweb

# Testes (10 testes verdes, incluindo Grupo A e Grupo B)
pytest -q tests/unit/test_example_pwa_webpush.py
```

Os 10 testes cobrem:

| Grupo | Teste | O que verifica |
|---|---|---|
| A | `test_initial_build_requires_no_bridge` | Render inicial não invoca bridge |
| A | `test_request_permission_granted_transitions_to_granted` | `IDLE → GRANTED` + botão subscribe aparece |
| A | `test_request_permission_denied_transitions_to_denied` | `IDLE → DENIED` + botões enable e retry |
| A | `test_subscribe_transitions_to_subscribed` | `GRANTED → SUBSCRIBED` + endpoint exibido |
| A | `test_reset_returns_to_idle` | `SUBSCRIBED → IDLE` + estado limpo |
| A | `test_permission_error_transitions_to_error` | Exceção → `ERROR` + botão try-again |
| B | `test_build_pwa_main_produces_installable_manifest` | `validate_installable` retorna `[]` |
| B | `test_build_pwa_main_writes_icon_files` | 5 PNGs válidos escritos |
| B | `test_build_pwa_manifest_fields` | Campos `name`, `short_name`, `display` corretos |
| B | `test_build_pwa_validate_installable_direct` | `build_manifest(OPTIONS)` é instalável |

---

## Como funciona por dentro

### O ciclo de atualização com `async`

```
Clique no botão
      │
      ▼
handler assíncrono (ex: handle_request_permission)
      │
      ├─ app.set_state(phase = REQUESTING)  ← render imediato com Spinner
      │
      ▼
await app.state.request_permission()        ← bridge resolve via FFI (A) ou WS (B)
      │
      ▼
app.set_state(phase = GRANTED / DENIED / IDLE / ERROR)
      │
      ▼
view(app) chamada novamente → nova árvore de widgets
      │
      ▼
reconciliador calcula diff (patches)
      │
      ▼
DOM atualizado (mínimo de mudanças)
```

### Por que injetar callables no estado?

Se `request_permission` e `subscribe` fossem chamadas diretas ao módulo
`notifications`, testar a `view` exigiria um bridge real instalado. Com a injeção,
você escreve:

```python
app.state.request_permission = lambda: NotificationPermission.GRANTED
```

e o handler funciona identicamente — sem nenhum setup de bridge.

### Ícones sem Pillow

`emit_icons` gera PNGs RGBA 8-bit usando apenas `struct` e `zlib` da stdlib. Cada
ícone maskable recebe um inset de 10% para que a área de arte fique dentro da zona
segura das máscaras do SO. O resultado é aceito por browsers e pelo Lighthouse.

---

## Recapitulando

Neste tutorial você aprendeu:

- ✅ Modelar um **fluxo de consentimento** como máquina de estados explícita com `StrEnum`
- ✅ Injetar callables assíncronos no estado para **testes determinísticos** sem bridge
- ✅ Usar fases de "loading" (`REQUESTING`, `SUBSCRIBING`) para feedback visual imediato
- ✅ Chamar `tempestweb.native.notifications.request_permission` e `subscribe` do Python
- ✅ Gerar e validar um `manifest.webmanifest` instalável com `write_manifest` e `validate_installable`
- ✅ Emitir ícones PNG válidos sem dependências externas via `emit_icons`
- ✅ Rodar o mesmo app nos **dois modos** sem alterar uma linha do `view`

---

## Próximos passos

- 💡 Adicione um **servidor de envio WebPush** usando `tempestweb.server.webpush.WebPushService`
  com sua própria chave VAPID gerada por `py-vapid`
- 💡 Persista a `subscription` no `localStorage` via `tempestweb.native.storage.put` para
  não pedir re-assinatura a cada visita
- 💡 Explore a [documentação PWA](../pwa.md) para o Service Worker (P1) e o modo offline-first (P2)
- 💡 Leia o [exemplo de notification-center](notification-center.md) para ver como exibir
  notificações locais com `tempestweb.native.notifications.notify`
