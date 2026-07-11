# Modo C — transpile (Python → JavaScript nativo) 🧪

Os Modos A (WASM) e B (servidor) mantêm o **Python vivo** em tempo de execução —
no browser (Pyodide) ou no servidor. O **Modo C** faz diferente: um compilador
transcreve a **camada de app** do seu Python tipado para **JavaScript nativo**.
Zero runtime Python, hospedagem estática, first-paint e SEO ótimos. É a "história
do TypeScript" para Python. 🚀

!!! warning "Experimental (spike)"
    O Modo C está em construção. Ele já roda apps no estilo do contador — estado,
    `view()`, handlers, Button/Input estilizados — mas a API pode mudar e o
    subset de Python aceito ainda é restrito. Para telas ricas hoje, use os
    Modos A/B; volte ao Modo C conforme ele amadurece.

## Por que existe

| | Modo A (WASM) | Modo B (servidor) | **Modo C (transpile)** |
|---|---|---|---|
| Runtime Python | browser (~6 MB Pyodide) | servidor vivo | **nenhum** |
| First paint / SEO | ruim | bom | **ótimo** |
| Hospedagem | estática | servidor + WS/cliente | **estática** |
| Custo de escala | zero servidor | stateful por cliente | **zero servidor** |

O segredo: o cliente JS (`dom.js`, `style.js`, `events.js`) já é nativo e
compartilhado pelos três modos. O Modo C **não transpila Python inteiro** — só a
camada de app; todo o renderizador continua sendo o mesmo JS.

## Seu primeiro build

Pegue o app do contador (o mesmo que roda nos Modos A/B, sem mudar uma linha):

```python
from dataclasses import dataclass

from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.style import Edge


@dataclass
class CounterState:
    value: int = 0


def make_state() -> CounterState:
    return CounterState()


def view(app: App[CounterState]) -> Widget:
    def increment() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    def decrement() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value - 1))

    return Column(
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Count: {app.state.value}", key="label"),
            Row(
                style=Style(gap=4.0),
                children=[
                    Button(label="-", on_click=decrement, key="dec"),
                    Button(label="+", on_click=increment, key="inc"),
                ],
            ),
        ],
    )
```

Gere o bundle estático:

```bash
tempestweb build --mode transpile --path examples/counter
```

Isso escreve um diretório `dist/transpile/` **totalmente estático** — sem Python:

```text
dist/transpile/
├── index.html                     # monta o app via mountApp
└── client/
    ├── tempestweb.js dom.js style.js events.js …   # o cliente compartilhado
    └── transpile/
        ├── app.gen.js             # o seu app.py transcrito para JS nativo
        ├── runtime.js widgets.js diff.js
        └── widget-styles.gen.js   # estilos MD3 resolvidos do core
```

Sirva com qualquer host estático (ou localmente):

```bash
tempestweb run --mode transpile --path examples/counter
```

Durante o desenvolvimento, use o loop com **livereload** — edite o `app.py` e o
browser recarrega com o bundle recompilado:

```bash
tempestweb dev --mode transpile --path examples/counter
```

!!! check "O que aconteceu"
    Seu `view()` virou `app.gen.js` — JavaScript nativo. O runtime segura o
    estado, roda `view()`, faz o **diff** em JS e aplica **patches granulares** ao
    DOM. Nenhum Python é baixado ou executado no browser.

## O que o compilador emite

O `app.py` acima vira, essencialmente:

```javascript
import { State } from "./runtime.js";
import { Button, Column, Edge, Row, Style, Text } from "./widgets.js";

export class CounterState extends State {
  constructor() {
    super();
    this.value = 0;
  }
}

export function makeState() {
  return new CounterState();
}

export function view(app) {
  const increment = () => {
    app.setState((s) => {
      s.value = (s.value + 1);
    });
  };
  // …
  return Column({
    style: Style({ gap: 8.0, padding: Edge.all(16) }),
    children: [
      Text({ content: `Count: ${app.state.value}`, key: "label" }),
      // …
    ],
  });
}
```

!!! note "Convenções de nome"
    O compilador traduz a API para o JS idiomático: `make_state` → `makeState`,
    `set_state` → `setState`, `on_click` → `onClick`, `color_scheme` →
    `colorScheme`. `setattr(s, "x", v)` vira `s.x = v`; f-strings viram template
    literals.

## Estado com métodos

Você não precisa se limitar a lambdas `setattr`. Um `@dataclass` com métodos
transpila para uma classe JS — `self` vira `this`:

```python
@dataclass
class Counter:
    value: int = 0

    def increment(self) -> None:
        self.value += 1


def view(app: App[Counter]) -> Widget:
    def inc() -> None:
        app.set_state(lambda s: s.increment())

    return Button(label="+", on_click=inc, key="inc")
```

## Campos de formulário reativos

`Input` resolve o estilo Material 3 e conecta o `on_change`. O binding é de duas
vias: digitar dispara o handler, que atualiza o estado e re-renderiza.

```python
from tempest_core import App, Column, Style, Text, Widget
from tempest_core.style import Edge
from tempest_core.widgets import Input


@dataclass
class FormState:
    name: str = ""


def view(app: App[FormState]) -> Widget:
    def on_name(event) -> None:
        app.set_state(lambda s: setattr(s, "name", event.payload["value"]))

    return Column(
        style=Style(gap=12.0, padding=Edge.all(24)),
        children=[
            Text(content=f"Hello, {app.state.name or 'stranger'}!", key="greet"),
            Input(value=app.state.name, placeholder="Your name", on_change=on_name, key="name"),
        ],
    )
```

Digite no campo e a saudação atualiza ao vivo — sem servidor, sem Python. ✨

## Capacidades nativas (requests, storage, cookies…)

O mesmo `native` tipado dos Modos A/B funciona no Modo C — chamadas `async`
transcritas para chamadas JS em processo à glue de browser compartilhada
(`fetch`, IndexedDB/localStorage, `document.cookie`). Zero Python, zero rede.

```python
from tempestweb import native


@dataclass
class DataState:
    body: str = ""


def view(app: App[DataState]) -> Widget:
    async def fetch_it() -> None:
        res = await native.http.request("GET", "/api/items")
        await native.storage.put("last", res.body)
        await native.cookies.set("seen", "1")
        app.set_state(lambda s: setattr(s, "body", res.body))

    return Button(label="fetch", on_click=fetch_it, key="go")
```

!!! tip "Handlers `async`"
    Um handler pode ser `async def` e usar `await`. O re-render acontece quando o
    `set_state` roda (depois do `await`), então a UI reflete o resultado assim que
    a capacidade resolve. Capacidades disponíveis no Modo C: `http`, `storage`
    (IndexedDB/localStorage), `clipboard`, `geolocation`, `cookies`, `share`,
    `audio`, `file`, `notifications` (incl. WebPush `subscribe`/`unsubscribe`),
    `install` (prompt de instalação PWA), `offline` (fila de mutações durável).

!!! tip "Instalar o PWA (`native.install`)"
    `await native.install.state()` informa `{can_install, installed}`; após um
    gesto do usuário, `await native.install.prompt()` dispara o prompt nativo de
    instalação e resolve com `"accepted"`, `"dismissed"` ou `"unavailable"`. O
    controller já suprime o mini-infobar frio do browser, então você mostra um
    botão "Instalar" no momento certo.

!!! tip "Push (`native.notifications`)"
    `await native.notifications.push_state()` informa `{supported, permission}`
    **sem** disparar prompt — use pra decidir mostrar o botão. `await
    native.notifications.request_permission()` pede permissão; `await
    native.notifications.subscribe(vapid_public_key)` roda o fluxo WebPush do
    browser e devolve o **JSON da assinatura** — você o envia ao seu backend
    (via `native.http` ou enfileirado com `native.offline`). `unsubscribe()`
    cancela. O framework não decide seu schema de endpoint nem o servidor de
    push: só entrega a assinatura crua.

!!! tip "Fila offline (`native.offline`)"
    Escritas feitas offline sobrevivem: `await native.offline.enqueue("POST",
    url, body)` grava uma mutação durável no IndexedDB (com chave de
    idempotência) e o replay acontece em ordem FIFO quando a conexão volta —
    via o evento `online`, via Background Sync (aba fechada) ou explicitamente
    com `await native.offline.replay()`. Inspecione com `native.offline.size()`
    e `native.offline.pending()`. O servidor deduplica pela chave de
    idempotência, então um replay nunca aplica duas vezes.

!!! tip "Validadores de campo"
    `from tempest_core.validators import validate_email, validate_cpf,
    validate_cnpj, validate_phone` roda **client-side** no Modo C, com o mesmo
    algoritmo e as mesmas mensagens PT-BR do core (port fiel, travado por fixture).
    Combina com `Input` + estado para forms validados sem servidor.

## Navegação (rotas + URL)

O Modo C fala a mesma navegação dos Modos A/B: `app.push(Route(...))`,
`app.pop()`, `app.replace(...)`, `app.nav.top` — sincronizados com a URL do
browser (deep-link + voltar/avançar) automaticamente.

```python
from tempest_core import App, Button, Column, Route, Text, Widget


def view(app: App[MyState]) -> Widget:
    def open_product() -> None:
        app.push(Route(name="/products/42"))

    route = app.nav.top
    return Column(children=[
        Text(content=f"rota: {route.name}", key="r"),
        Button(label="abrir produto", on_click=open_product, key="p"),
        Button(label="voltar", on_click=lambda e: app.pop(), key="b"),
    ])
```

!!! info "URL ↔ stack"
    `app.push`/`pop` empurram/voltam a URL (`pushState`); um deep-link ou o
    botão voltar do browser resetam a stack a partir do path
    (`routes_from_path`) — idêntico aos Modos A/B. **Path/query params:** o `name`
    da rota carrega o path completo (incl. `?query`), como no core; leia os
    segmentos por `app.nav.stack`. Um router com params tipados é evolução no
    nível do core.

## Localização (i18n)

`translate` / `t` + `Locale` do core funcionam no Modo C: busca a chave na tabela
`{idioma: {chave: template}}` pelo idioma do locale e interpola `{name}` — mesma
semântica e fallbacks do core (chave/idioma ausente → a própria chave).

```python
from tempest_core import App, Locale, Text, Widget, t

MESSAGES = {
    "pt": {"greet": "Olá, {name}!"},
    "en": {"greet": "Hello, {name}!"},
}


def view(app: App[MyState]) -> Widget:
    loc = Locale(language=app.state.lang)
    return Text(content=t("greet", locale=loc, translations=MESSAGES, name="Ana"), key="g")
```

Troque `app.state.lang` num handler e a UI re-renderiza no novo idioma —
verificado no Playwright (PT → EN ao vivo). A tabela `MESSAGES` é uma **constante
de módulo** (agora suportada no subset).

## Tema + responsividade

O Modo C expõe `app.theme` e `app.media` como nos Modos A/B. `app.theme.is_dark()`
resolve claro/escuro (`DARK`/`LIGHT` absolutos; `SYSTEM` segue o SO); `app.media`
carrega `width`/`height`/`platform_dark_mode`/`orientation` — sincronizado com o
browser (matchMedia + resize) → a UI **re-renderiza responsivamente**.

```python
from tempest_core import App, Column, Text, Theme, ThemeMode, Widget


def view(app: App[MyState]) -> Widget:
    dark = app.theme.is_dark(platform_dark_mode=app.media.platform_dark_mode)
    wide = app.media.width >= 600.0

    def toggle() -> None:
        app.set_theme(Theme(mode=ThemeMode.LIGHT if dark else ThemeMode.DARK))

    return Column(children=[
        Text(content=("escuro" if dark else "claro"), key="s"),
        Text(content=("largo" if wide else "estreito"), key="l"),
    ])
```

!!! check "Responsividade adaptativa"
    Redimensione a janela ou mude o `prefers-color-scheme` do SO e o `view`
    re-renderiza — verificado no Playwright (400px→estreito, 900px→largo; toggle
    de tema claro↔escuro). Os breakpoints do core (`Breakpoints`: sm/md/lg/xl)
    também estão disponíveis.

## Animação (transições)

Anime declarativamente: dê ao `Style` de um widget um `Transition` e o **browser**
faz o tween quando um campo estilizado muda (largura, cor, opacidade) — sem
runtime Python, sem driver de frame.

```python
from tempest_core import App, Container, Style, Widget
from tempest_core.style import Color, Curve, Transition


def view(app: App[MyState]) -> Widget:
    w = 320.0 if app.state.big else 120.0
    return Container(key="box", style=Style(
        width=w,
        background=Color(r=103, g=80, b=164, a=1.0),
        transition=Transition(duration_ms=400, curve=Curve.EASE_IN_OUT),
    ))
```

!!! check "Verificado"
    Trocar `app.state.big` num handler anima a largura de 120→320px em 400ms
    (Playwright confirmou a transição CSS aplicada). Curvas: `linear`, `ease`,
    `ease-in`, `ease-out`, `ease-in-out`, `bounce`, `elastic`.

### Animação imperativa (AnimationController)

Para controle por frame, use `AnimationController` + `Tween` — o runtime dirige
os controllers num loop `requestAnimationFrame`, computando o valor a cada frame
e re-renderizando.

```python
from tempest_core.animation import AnimationController, Tween
from tempest_core.style import Curve


def make_state() -> S:
    s = S()
    s.anim = AnimationController(0.6, curve=Curve.EASE_OUT)
    return s


def view(app: App[S]) -> Widget:
    w = Tween(begin=100.0, end=340.0).at(app.state.anim.value)

    def go() -> None:
        app.state.anim.forward()
        app.register_animation(app.state.anim)

    return Container(key="box", style=Style(width=w))
```

`forward()`/`reverse()`/`stop()`, curvas eased **e springs** (`Spring`) — mesma
matemática do core. Verificado no Playwright: a largura anima 100→340 (ease-out)
e assenta. **Isto fecha 100% da cobertura do tempest-core no Modo C.**

## O tour completo

Tudo acima — estado com métodos, navegação, i18n, tema + responsividade, um
formulário validado e uma animação imperativa — vive junto num único app de
referência, [`examples/transpile-tour`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/transpile-tour/app.py):

```bash
tempestweb build --mode transpile --path examples/transpile-tour
tempestweb dev   --mode transpile --path examples/transpile-tour   # livereload
```

!!! tip "Um só `view`, todos os modos"
    O mesmo `view()` do tour roda inalterado nos Modos A e B. O `build` valida
    isso renderizando pelo core real — uma API que só existisse no Modo C
    quebraria o build, então o tour é prova viva de portabilidade.

## PWA: instalável e offline

Você já tem um bundle 100% estático e sem Python — o alvo **perfeito** para uma
PWA. Por isso o `build --mode transpile` já emite a camada PWA inteira **sozinho**:
o usuário pode **instalar** seu app na tela inicial e, depois da primeira visita,
abri-lo **offline**. Sem passo extra, sem configurar nada. 🚀

Basta o build de sempre:

```bash
tempestweb build --mode transpile --path examples/transpile-tour
```

Além do bundle do app, o Modo C agora escreve a camada PWA junto:

```text
dist/transpile/
├── index.html               # linka o manifest, theme-color, apple-touch-icon
│                            #   e registra o service worker
├── manifest.webmanifest     # metadados de instalação (nome, ícones, cores)
├── sw.js                    # service worker cache-first (app shell)
├── register.js              # registra o sw.js no carregamento
├── icons/                   # o conjunto de ícones (maskable + apple-touch)
└── client/ …                # o cliente compartilhado + o seu app.gen.js
```

O `sw.js` **pré-cacheia o bundle estático inteiro** — `index.html`, o cliente
compartilhado, `client/transpile/*` (incl. o seu `app.gen.js`), a árvore nativa,
os ícones e o manifest. Depois da primeira carga, o app abre e roda **sem rede**.

!!! tip "Offline de verdade ✅"
    Isso não é offline "meia-boca": com o servidor HTTP **desligado**, recarregar
    a página ainda **renderiza o tour** e a navegação continua funcionando —
    verificado ao vivo no Playwright (servidor morto, reload, tour intacto). Como
    o Modo C é um bundle estático sem Python, não há nada que dependa do servidor
    depois do primeiro fetch.

### Configurando o manifest com `[pwa]`

Os metadados de instalação vêm de uma seção opcional `[pwa]` no seu
`tempestweb.toml`. Todos os campos são opcionais — sem a seção, o build usa
padrões sensatos derivados do nome do projeto:

```toml
[pwa]
name = "Weather Pro"
short_name = "WPro"
theme_color = "#0a84ff"
display = "standalone"
```

| Campo | Tipo | Padrão | O que faz |
|---|---|---|---|
| `name` | string | nome do projeto | Nome completo exibido na instalação/splash. |
| `short_name` | string | — | Nome curto para o ícone da tela inicial. |
| `description` | string | — | Descrição do app no prompt de instalação. |
| `theme_color` | string | `"#111111"` | Cor do tema (barra do navegador + `<meta name="theme-color">`). |
| `background_color` | string | `"#ffffff"` | Cor de fundo da splash de abertura. |
| `display` | string | `"standalone"` | Modo de exibição: `standalone`, `fullscreen` ou `minimal-ui`. |
| `orientation` | string | — | Orientação preferida (ex.: `portrait`, `landscape`). |
| `lang` | string | `"pt-BR"` | Idioma primário do app. |
| `categories` | lista de string | — | Categorias da app store (ex.: `["productivity"]`). |

!!! warning "Valor de `display` válido"
    `display` aceita apenas `"standalone"`, `"fullscreen"` ou `"minimal-ui"`. Um
    valor fora dessa lista é **erro de build** — falha cedo, no espírito do resto
    do compilador do Modo C.

!!! note "Automático no Modo C"
    Você não precisa escrever service worker, manifest nem código de registro à
    mão: o `build --mode transpile` gera tudo. A seção `[pwa]` só **ajusta** os
    metadados de instalação — o comportamento offline vem de graça porque o bundle
    é estático.

!!! tip "Prompt de atualização"
    Quando você publica uma versão nova, o service worker antigo continua no ar
    até a aba fechar. O shell detecta o worker em espera e mostra um banner
    discreto **"nova versão disponível → Atualizar"**; ao confirmar, o worker novo
    assume e a página recarrega uma vez. Automático — nada a escrever no app.

## O subset suportado

O Modo C aceita um **subset tipado** de Python — o suficiente para a camada de
app. Um construto fora dele vira **erro de compilação** claro (`arquivo:linha`),
no espírito do `mypy --strict`.

!!! info "Dentro do subset hoje"
    - **Expressões:** aritmética (`+ - * / % ** //`), comparação
      (`== != < <= > >=`, encadeada `a < b < c`), booleanos (`and`/`or`), unários
      (`not`/`-`), ternário (`a if c else b`), comprehensions de lista e de dict
      (inclusive alvo em tupla `for k, v in …`), literais
      `list`/`tuple`/`set`/`dict`, `in`/`not in`, indexação e **slices**
      (`x[a:b]`), f-strings (formatos `{x:.2f}`, `{x:,}`, `{x:,.2f}`, `{x:.1%}`,
      `{x:d}`; conversões `{x!s}`, `{x!r}`), lambdas de expressão.
    - **Builtins:** `len`, `str`/`int`/`float`/`bool`, `abs`, `round(x[, n])`,
      `min`/`max` (variádico ou sobre um iterável), `sum(it)`, `range(...)`,
      `enumerate(it)`, `zip(a, b)`.
    - **Statements:** `if`/`elif`/`else`, `for … in` (com alvo em tupla),
      `while`, `break`/`continue`, `try`/`except`/`finally` (um `except` pega
      tudo; vários fazem dispatch por nome da classe de exceção), `with … as x`
      (protocolo `__enter__`/`__exit__`), `raise Exc("msg")` / `raise` (re-raise
      dentro de `except`), `assert cond[, msg]`, atribuição (inclusive unpacking
      `a, b = par` e encadeada `a = b = x`), `+=` e afins, `return`.
    - **Estruturas:** `@dataclass` de estado (campos + métodos), herança de
      dataclass (`class B(A)` → `extends`), `make_state()`, `view()` com closures
      de handler.
    - **Componentes de layout:** `HStack` / `VStack` (aliases ergonômicos estilo
      SwiftUI) — `gap` por token (`"md"`) ou px, `align`/`justify` diretos.
    - **Widgets:** **todos os ~64 widgets do `tempest_core`** — layout (`Column`,
      `Row`, `Container`, `Stack`, `Wrap`, `ScrollView`, `SafeArea`, `Spacer`),
      exibição (`Text`, `Icon`, `Image`, `Svg`, `Spinner`, `Skeleton`,
      `ProgressBar`), entrada (`Button`, `Input`, `TextArea`, `Switch`,
      `Checkbox`, `Slider`, `RangeSlider`, `Dropdown`, `DatePicker`, …), overlays
      (`Dialog`, `BottomSheet`, `Popover`, `Toast`, `Tooltip`), gestos
      (`GestureDetector`, `Draggable`, `PanHandler`, …) e mais. Os builders JS são
      **gerados** por introspecção do core (`widgets.gen.js`), com o estilo MD3
      resolvido dos 14 widgets estilizados.

!!! note "Eventos por widget"
    Cada handler é ligado ao evento DOM que o renderizador (`dom.js`) emite para
    aquele widget: `Button.on_click` → clique; `Input`/`Checkbox` (controles
    nativos) → `input`/`change`; um `Switch` (div) → clique. Handlers de widgets
    cujo evento o cliente ainda não emite (ex.: `on_scan`, `on_reorder`) ficam
    registrados mas inertes por ora.

!!! warning "Ainda fora do subset"
    A maior parte de `tempest_core.components` (Card, DataTable, Tabs, charts,
    inputs de formulário …). Diferente dos widgets, componentes são **composição
    Python** que expande em primitivos no `build()` — muitos a partir de dados/
    loops — então não são auto-portáveis para um runtime sem Python. Os aliases de
    layout `HStack`/`VStack` são a exceção (expandem em `Row`/`Column`). Também
    fora: comprehensions multi-loop ou com alvo desestruturado (`for k, v in …`),
    e format-specs de f-string além dos suportados (ex.: alinhamento `{x:>5}`,
    sinal `{x:+.2f}`, hex/bin `{x:x}`, dinâmico `{x:.{n}f}`, conversão `!a`).

## Recapitulando

- **Modo C** transcreve a camada de app Python para **JS nativo** — zero runtime
  Python, bundle estático, first-paint/SEO ótimos.
- `tempestweb build --mode transpile` gera um diretório servível por qualquer CDN;
  `run --mode transpile` serve localmente.
- O mesmo `view()` dos Modos A/B roda aqui — estado, handlers, `Button`/`Input`
  estilizados, binding reativo.
- É **experimental**: subset restrito e API sujeita a mudança. Detalhes de design
  em [`docs/modo-c-transpile.md`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/modo-c-transpile.md).
