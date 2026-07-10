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
    `audio`, `file`, `notifications`.

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

## O subset suportado

O Modo C aceita um **subset tipado** de Python — o suficiente para a camada de
app. Um construto fora dele vira **erro de compilação** claro (`arquivo:linha`),
no espírito do `mypy --strict`.

!!! info "Dentro do subset hoje"
    - **Expressões:** aritmética (`+ - * / %`), comparação (`== != < <= > >=`),
      booleanos (`and`/`or`), unários (`not`/`-`), ternário (`a if c else b`),
      list comprehensions (`[e for x in it if c]`), `in`/`not in`, indexação,
      f-strings, lambdas de expressão.
    - **Statements:** `if`/`elif`/`else`, `for … in`, atribuição, `+=` e afins,
      `return`.
    - **Estruturas:** `@dataclass` de estado (campos + métodos), `make_state()`,
      `view()` com closures de handler.
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
    fora: dict/set/tuple, f-strings com format-spec.

## Recapitulando

- **Modo C** transcreve a camada de app Python para **JS nativo** — zero runtime
  Python, bundle estático, first-paint/SEO ótimos.
- `tempestweb build --mode transpile` gera um diretório servível por qualquer CDN;
  `run --mode transpile` serve localmente.
- O mesmo `view()` dos Modos A/B roda aqui — estado, handlers, `Button`/`Input`
  estilizados, binding reativo.
- É **experimental**: subset restrito e API sujeita a mudança. Detalhes de design
  em [`docs/modo-c-transpile.md`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/modo-c-transpile.md).
