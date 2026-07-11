# Tour do Modo C — um app transpilado para JS nativo 🧭

**Modos: A/B/C** — este é o exemplo-vitrine do **Modo C (transpile)**.

Um único app que exercita o coração do core — **estado + métodos**, **navegação**
(rotas/URL), **i18n**, **tema + responsividade**, um **formulário validado** e uma
**caixa animada** (`AnimationController`) — e roda **sem nenhum Python no browser**:
o app inteiro é transcrito para JavaScript nativo. 🚀

!!! success "O mesmo `view`, os três modos"
    Este exemplo é o mostruário do Modo C, mas o **mesmo** `view` roda inalterado
    nos Modos A (WASM) e B (servidor). Você escreve a lógica uma vez; o compilador
    decide se ela vira JS nativo (C) ou continua Python vivo (A/B). Veja o guia
    completo em [Modo C — transpile](../transpile.md).

---

## O que este exemplo mostra

- **Estado tipado com métodos** — `TourState.set_email` valida e guarda o e-mail.
- **Navegação por rotas** — `app.push(Route(...))` / `app.pop()` alternam entre a
  tela inicial e o formulário; o compilador transcreve a pilha de navegação.
- **i18n** — `t()` resolve as strings a partir de um dicionário de traduções, e o
  botão **lang** troca o idioma em tempo real.
- **Tema + responsividade** — `app.theme.is_dark(...)` e `app.media.width` derivam
  o esquema de cores e o layout (`wide`/`narrow`) do ambiente.
- **Formulário validado** — `validate_email` do core roda como validação nativa.
- **Animação** — um `AnimationController` + `Tween` interpolam a largura de um
  `Container`, registrados via `app.register_animation`.
- **Capacidades nativas no Modo C** — `native.install.prompt()` (instalação PWA) e
  `native.offline.enqueue/size` (fila durável) funcionam também no bundle estático.

---

## Rodando ▶

```bash
# Build estático (Modo C) — gera o bundle JS nativo:
tempestweb build --mode transpile examples/transpile-tour

# Dev com livereload (Modo C):
tempestweb dev --mode transpile examples/transpile-tour
```

!!! tip "Rode-o também nos Modos A/B"
    ```bash
    tempestweb run --mode wasm   examples/transpile-tour   # Python no browser
    tempestweb run --mode server examples/transpile-tour   # Python no servidor
    ```
    Nenhuma linha do `app.py` muda entre os modos.

---

## O código

```python
"""Mode C tour — one transpiled app exercising the core in native JS."""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import (
    App,
    Button,
    Column,
    Container,
    Locale,
    Route,
    Row,
    Style,
    Text,
    Theme,
    ThemeMode,
    Widget,
    t,
)
from tempest_core.animation import AnimationController, Tween
from tempest_core.style import Color, Curve, Edge
from tempest_core.validators import validate_email
from tempest_core.widgets import Input
from tempestweb import native

MESSAGES = {
    "pt": {"title": "Tour do Modo C", "home": "Início", "form": "Formulário"},
    "en": {"title": "Mode C tour", "home": "Home", "form": "Form"},
}


@dataclass
class TourState:
    """State for the tour."""

    lang: str = "pt"
    email: str = ""
    email_error: str = ""
    install: str = ""
    queued: int = 0
    box: object = field(default=None)

    def set_email(self, value: str) -> None:
        """Store the email and its validation result."""
        self.email = value
        self.email_error = validate_email(value) or "ok"


def make_state() -> TourState:
    """Build the initial state with an animation controller."""
    state = TourState()
    state.box = AnimationController(0.5, curve=Curve.EASE_OUT)
    return state


def view(app: App[TourState]) -> Widget:
    """Render the tour, branching on the current route."""
    loc = Locale(language=app.state.lang)
    dark = app.theme.is_dark(platform_dark_mode=app.media.platform_dark_mode)
    wide = app.media.width >= 600.0

    def toggle_lang() -> None:
        app.set_state(lambda s: setattr(s, "lang", "en" if s.lang == "pt" else "pt"))

    def toggle_theme() -> None:
        app.set_theme(Theme(mode=ThemeMode.LIGHT if dark else ThemeMode.DARK))

    def go_form() -> None:
        app.push(Route(name="/form"))

    def go_home() -> None:
        app.pop()

    def on_email(event: object) -> None:
        value = event.payload["value"]
        app.set_state(lambda s: s.set_email(value))

    def grow() -> None:
        app.state.box.forward()
        app.register_animation(app.state.box)

    async def do_install() -> None:
        outcome = await native.install.prompt()
        app.set_state(lambda s: setattr(s, "install", outcome))

    async def queue_write() -> None:
        await native.offline.enqueue("POST", "/api/log", {"n": app.state.queued})
        count = await native.offline.size()
        app.set_state(lambda s: setattr(s, "queued", count))

    header = Row(
        style=Style(gap=8.0),
        children=[
            Text(content=t("title", locale=loc, translations=MESSAGES), key="title"),
            Text(content=("dark" if dark else "light"), key="scheme"),
            Text(content=("wide" if wide else "narrow"), key="layout"),
        ],
    )
    controls = Row(
        style=Style(gap=8.0),
        children=[
            Button(label="lang", on_click=toggle_lang, key="lang"),
            Button(label="theme", on_click=toggle_theme, key="theme"),
        ],
    )

    if app.nav.top.name == "/form":
        body = Column(
            style=Style(gap=10.0),
            children=[
                Text(content=t("form", locale=loc, translations=MESSAGES), key="fh"),
                Input(
                    value=app.state.email,
                    placeholder="email",
                    on_change=on_email,
                    key="email",
                ),
                Text(content=app.state.email_error, key="err"),
                Button(
                    label=t("home", locale=loc, translations=MESSAGES),
                    on_click=go_home,
                    key="back",
                ),
            ],
        )
    else:
        width = Tween(begin=120.0, end=320.0).at(app.state.box.value)
        body = Column(
            style=Style(gap=10.0),
            children=[
                Container(
                    key="box",
                    style=Style(
                        width=width,
                        height=48.0,
                        background=Color(r=103, g=80, b=164, a=1.0),
                        radius=8.0,
                        transition=None,
                    ),
                    children=[],
                ),
                Button(label="grow", on_click=grow, key="grow"),
                Button(label="install", on_click=do_install, key="install"),
                Text(content=app.state.install, key="installout"),
                Button(label="queue", on_click=queue_write, key="queue"),
                Text(content=f"queued={app.state.queued}", key="queuedout"),
                Button(
                    label=t("form", locale=loc, translations=MESSAGES),
                    on_click=go_form,
                    key="toform",
                ),
            ],
        )

    return Column(
        style=Style(gap=16.0, padding=Edge.all(24)),
        children=[header, controls, body],
    )
```

---

## Peça por peça

### Estado com um método

`TourState` não é só um saco de campos: `set_email` encapsula a regra de negócio
(guardar o valor **e** revalidar). O Modo C transcreve métodos de dataclass para
JS — por isso o exemplo os usa em vez de mutar o estado direto no handler.

### Navegação dirige o corpo

```python
if app.nav.top.name == "/form":
    ...   # tela do formulário
else:
    ...   # tela inicial com a caixa animada
```

O `view` ramifica no **topo da pilha de navegação**. `go_form` empurra a rota
`/form`; `go_home` faz `pop()`. No Modo C isso vira histórico de URL nativo.

### i18n, tema e responsividade derivados do ambiente

```python
loc = Locale(language=app.state.lang)
dark = app.theme.is_dark(platform_dark_mode=app.media.platform_dark_mode)
wide = app.media.width >= 600.0
```

Nada disso vive no estado do app — tudo é **derivado** a cada render de
`app.theme`, `app.media` e `app.state.lang`. O botão **lang** só troca uma string;
o resto recalcula sozinho.

### Animação com `AnimationController` + `Tween`

```python
width = Tween(begin=120.0, end=320.0).at(app.state.box.value)
```

`grow()` chama `box.forward()` e registra o controller com
`app.register_animation`. O runtime avança o valor a cada frame e re-renderiza; o
`Tween` mapeia `0.0 → 1.0` para `120px → 320px`.

!!! info "Capacidades nativas no Modo C"
    `do_install` e `queue_write` são handlers `async` que chamam
    `native.install.prompt()` e `native.offline.enqueue/size`. O Modo C tem
    **história completa de PWA** — instalação, offline e fila de mutações
    funcionam no bundle estático, sem servidor Python.

---

## Recapitulando

Neste exemplo você viu:

- ✅ Um **único app** exercitando estado+métodos, navegação, i18n, tema,
  responsividade, formulário validado e animação
- ✅ O **Modo C** transcrevendo tudo isso para **JavaScript nativo** — zero Python
  no browser
- ✅ Que o **mesmo `view`** roda inalterado nos Modos A/B
- ✅ Capacidades nativas (PWA install, fila offline) rodando no bundle estático

---

## Próximos passos

- 💡 Leia [Modo C — transpile](../transpile.md) para o subset suportado e o pipeline de build
- 💡 Veja [Fila offline](offline-queue.md) para o mergulho na `native.offline`
- 💡 Explore [PWA e offline](../pwa.md) para instalação e WebPush ponta a ponta
