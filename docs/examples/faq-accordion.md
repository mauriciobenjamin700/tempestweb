# FAQ Accordion

> 🚀 **O que você vai construir:** uma página de Perguntas Frequentes com itens expansíveis (`Accordion`), política de abertura única — abrir um item fecha o anterior — e um campo de busca que filtra as entradas em tempo real.

---

## Por que esse exemplo importa?

Padrões de *disclosure* (revelar/ocultar conteúdo sob demanda) aparecem em toda aplicação real: FAQs, seções de ajuda, sumários de pedido, painéis de configuração.
O `Accordion` encapsula esse comportamento de forma declarativa: você diz se está aberto ou fechado e fornece um handler de toggle — o framework cuida do DOM.

Neste tutorial você vai aprender a:

- Usar `Accordion` para revelar e ocultar conteúdo com um clique;
- Implementar a política **single-open** (apenas um item aberto por vez);
- Filtrar uma lista de widgets em tempo real com `Input`;
- Compor layouts limpos com `Card`, `Divider`, `Row`, `Column` e `Text`.

!!! note "Nota"
    Este exemplo roda **sem nenhuma alteração** nos dois modos — WASM (Pyodide no
    browser) e Servidor (FastAPI + WebSocket). A mesma `view()` Python serve os dois.

---

## Pré-requisitos

Instale o tempestweb e confirme que o CLI está disponível:

```bash
pip install tempestweb
tempestweb --version
```

---

## Estrutura do projeto

```
examples/
└── faq-accordion/
    └── app.py
```

Crie a pasta e o arquivo:

```bash
mkdir -p examples/faq-accordion
touch examples/faq-accordion/app.py
```

---

## Passo 1 — Importações e dados do FAQ

Comece com todas as importações necessárias e defina a lista estática de pares pergunta/resposta.

```python
from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Style, Widget
from tempest_core.components import Accordion, Card, Divider
from tempest_core.style import Edge, FontWeight
from tempest_core.widgets import Column, Input, Row, Text
from tempest_core.widgets.events import TextChangeEvent

_FAQ_ENTRIES: list[tuple[str, str]] = [
    (
        "What is tempestweb?",
        "tempestweb is a framework that lets you build interactive web applications "
        "entirely in typed Python. You declare a widget tree once and the framework "
        "renders it in the browser (Mode A, Pyodide/WASM) or via a FastAPI "
        "WebSocket server (Mode B) — your view function never needs to know "
        "which mode is active.",
    ),
    (
        "Do I need to write any JavaScript?",
        "No. The client-side runtime is a small, zero-dependency JavaScript module "
        "that ships with the framework. Application logic lives exclusively in Python; "
        "the JS layer only handles DOM patching and transport I/O.",
    ),
    (
        "What is the difference between Mode A and Mode B?",
        "Mode A runs Python directly in the browser via Pyodide (WebAssembly). "
        "There is no server round-trip for state changes — everything happens "
        "client-side. Mode B runs Python on a FastAPI server; the browser sends "
        "events over a WebSocket and receives patch sequences back. Mode A is "
        "simpler to deploy (static hosting); Mode B gives full server-side access "
        "to databases and services.",
    ),
    (
        "How do I manage state?",
        "Define a plain Python ``@dataclass`` as your state and pass a fresh "
        "instance to ``make_state()``. Inside your ``view`` function you call "
        "``app.set_state(lambda s: ...)`` to mutate state and trigger a "
        "reconciled rebuild. The framework diffs the old and new widget trees "
        "and sends only the minimal patch sequence to the renderer.",
    ),
    (
        "Can I use third-party Python packages?",
        "In Mode B (server) you can use any Python package as normal. In Mode A "
        "(Pyodide) you are limited to packages that Pyodide ships or that are "
        "pure-Python wheels, because the package must run inside the browser's "
        "WebAssembly sandbox.",
    ),
    (
        "Is TypeScript or a build step required?",
        "No TypeScript and no build step. The client runtime is plain ES-module "
        "JavaScript. You open the app with a single ``<script type='module'>`` "
        "tag — no bundler, no transpiler, no node_modules.",
    ),
    (
        "How does styling work?",
        "Styles are inline, typed Python objects (``Style``, ``Edge``, ``Color``, "
        "etc.). There is no CSS cascade. Each widget carries its own ``Style`` "
        "instance; the renderer serialises it to inline DOM styles. This keeps "
        "styles predictable, refactorable with mypy, and free of selector "
        "specificity surprises.",
    ),
]
```

!!! tip "Dica"
    `_FAQ_ENTRIES` é uma constante de módulo — uma lista simples de tuplas
    `(pergunta, resposta)`. Nada de banco de dados, nada de ORM: o foco deste
    exemplo é a UI.

**O que acabou de acontecer:**

- As importações trazem exatamente o que o app usa — sem extras desnecessários.
- `_FAQ_ENTRIES` enumera os pares de conteúdo; o estado vai rastrear qual está aberto e qual texto está sendo buscado.

---

## Passo 2 — Definir o estado

O estado deste app é mínimo: qual item está aberto (ou `-1` para nenhum) e o texto digitado no campo de busca.

```python
@dataclass
class FaqState:
    """State for the FAQ accordion app.

    Attributes:
        open_index: The index of the currently expanded FAQ entry, or ``-1``
            when all items are collapsed.
        query: The current value of the search/filter field.
    """

    open_index: int = -1
    query: str = ""


def make_state() -> FaqState:
    """Build the initial FAQ state with the first entry pre-expanded.

    Returns:
        A fresh :class:`FaqState` with the first accordion open so the page
        renders a non-empty visible body on first mount.
    """
    return FaqState(open_index=0)
```

!!! info "Info"
    `open_index = 0` em `make_state()` faz com que a primeira pergunta já apareça
    expandida ao carregar a página — uma experiência melhor do que uma lista
    completamente recolhida.

**O que está acontecendo:**

| Campo | Tipo | Papel |
|---|---|---|
| `open_index` | `int` | Índice do `Accordion` aberto; `-1` = todos fechados |
| `query` | `str` | Texto digitado no campo de busca em tempo real |

A política de **single-open** é implementada inteiramente na lógica do `view`, não no estado: `open_index` guarda no máximo um índice por vez.

---

## Passo 3 — Handlers de evento

Antes de montar os widgets, defina as duas funções que respondem a interações do usuário. Elas vivem dentro de `view` para ter acesso direto a `app`.

```python
def view(app: App[FaqState]) -> Widget:
    """Render the FAQ accordion page from the current state.

    The page has three regions:

    1. A title heading and a live-search ``Input`` that filters entries.
    2. A ``Column`` of ``Accordion`` items — one per matching FAQ entry.
       A single-open policy means toggling an entry collapses whatever was
       previously open.
    3. A muted footer showing how many entries match the current query.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def on_search(event: TextChangeEvent) -> None:
        """Update the query and reset the open item when the filter changes.

        Args:
            event: The text-change event carrying the new input value.
        """

        def mutate(s: FaqState) -> None:
            s.query = event.value
            s.open_index = -1

        app.set_state(mutate)

    def toggle(entry_index: int) -> None:
        """Expand the clicked entry or collapse it if it is already open.

        Args:
            entry_index: The index into :data:`_FAQ_ENTRIES` that was toggled.
        """

        def mutate(s: FaqState) -> None:
            s.open_index = -1 if s.open_index == entry_index else entry_index

        app.set_state(mutate)
```

!!! tip "Dica"
    Perceba que `on_search` **reseta** `open_index` para `-1` cada vez que o usuário
    digita algo. Isso evita que um item aberto em uma busca anterior continue visível
    de forma confusa ao filtrar de novo.

**Destaques:**

- `app.set_state(mutate)` recebe uma função que modifica o estado no lugar. O framework roda a função, gera o diff da árvore e envia apenas os patches necessários para o DOM — nunca um re-render completo.
- A política single-open no handler `toggle`: `s.open_index = -1 if s.open_index == entry_index else entry_index`. Se o item clicado já estava aberto, fecha; caso contrário, abre o novo (implicitamente fechando qualquer outro, porque `open_index` é um inteiro único).

---

## Passo 4 — Filtrar as entradas visíveis

Com o estado e os handlers prontos, filtre `_FAQ_ENTRIES` com base na query atual.

```python
    query_lower = app.state.query.strip().lower()
    visible: list[tuple[int, str, str]] = [
        (idx, question, answer)
        for idx, (question, answer) in enumerate(_FAQ_ENTRIES)
        if not query_lower
        or query_lower in question.lower()
        or query_lower in answer.lower()
    ]
```

!!! info "Info"
    A busca verifica tanto a **pergunta** quanto a **resposta** — assim o usuário pode
    digitar uma palavra-chave do conteúdo e encontrar a entrada mesmo sem saber o
    título exato.

**O que está acontecendo:**

- `enumerate(_FAQ_ENTRIES)` preserva o índice original (`idx`) — importante porque `toggle(idx)` precisa do índice global, não da posição dentro da lista filtrada.
- `if not query_lower` — quando o campo está vazio, todas as entradas são visíveis.
- O resultado é `visible: list[tuple[int, str, str]]` — tuplas de `(índice_global, pergunta, resposta)`.

---

## Passo 5 — Construir os itens do Accordion

Itere sobre as entradas visíveis e crie um `Accordion` para cada uma, com a closure de toggle corretamente capturada.

```python
    accordion_items: list[Widget] = []
    for entry_index, question, answer in visible:
        is_open = app.state.open_index == entry_index

        def make_toggle(i: int = entry_index) -> None:
            """Closure toggling entry ``i``.

            Args:
                i: The FAQ entry index to toggle (default-bound at creation).
            """
            toggle(i)

        accordion_items.append(
            Accordion(
                key=f"faq-{entry_index}",
                title=question,
                open=is_open,
                on_toggle=make_toggle,
                children=[
                    Text(
                        content=answer,
                        key=f"answer-{entry_index}",
                        style=Style(font_size=15.0, line_height=1.6),
                    )
                ],
            )
        )
```

!!! warning "Aviso"
    Repare no padrão `def make_toggle(i: int = entry_index)`. Em Python, closures
    em loops capturam a **variável**, não o valor no momento da iteração. Ao usar
    `i = entry_index` como argumento padrão, o valor é capturado no instante da
    criação da função — cada `Accordion` recebe o toggle certo.

**Destaques do `Accordion`:**

| Prop | Tipo | O que faz |
|---|---|---|
| `key` | `str` | Identificador único para o reconciliador |
| `title` | `str` | Texto do cabeçalho clicável |
| `open` | `bool` | Controla se o corpo está expandido (controlled component) |
| `on_toggle` | `callable` | Chamado quando o usuário clica no cabeçalho |
| `children` | `list[Widget]` | Conteúdo exibido quando `open=True` |

---

## Passo 6 — Rodapé com contador e estado vazio

Calcule o texto do contador e prepare a mensagem de estado vazio.

```python
    total = len(_FAQ_ENTRIES)
    shown = len(visible)
    if query_lower:
        stripped = app.state.query.strip()
        counter_text = f'{shown} of {total} questions match "{stripped}"'
    else:
        counter_text = f"{total} questions"
```

Quando nenhuma entrada corresponde à busca, a lista de `accordion_items` fica vazia. Isso será tratado na montagem da árvore final com uma mensagem de feedback.

---

## Passo 7 — Montar a árvore completa

Agora reúna tudo na árvore de widgets retornada por `view`.

```python
    return Column(
        key="faq-root",
        style=Style(
            gap=0.0,
            padding=Edge.symmetric(vertical=24.0, horizontal=20.0),
        ),
        children=[
            # Page heading
            Text(
                content="Frequently Asked Questions",
                key="heading",
                style=Style(font_size=26.0, font_weight=FontWeight.BOLD),
            ),
            Text(
                content="Browse the most common questions or search below.",
                key="subtitle",
                style=Style(font_size=14.0, margin=Edge(top=6.0, bottom=20.0)),
            ),
            # Search bar
            Card(
                key="search-card",
                children=[
                    Row(
                        key="search-row",
                        style=Style(gap=8.0),
                        children=[
                            Text(content="Search:", key="search-label"),
                            Input(
                                key="search-input",
                                value=app.state.query,
                                placeholder="Filter questions…",
                                on_change=on_search,
                            ),
                        ],
                    )
                ],
            ),
            # Accordion list (or empty-state message)
            Column(
                key="accordion-list",
                style=Style(gap=8.0, margin=Edge(top=16.0)),
                children=(
                    accordion_items
                    if accordion_items
                    else [
                        Text(
                            content="No questions match your search.",
                            key="empty-msg",
                            style=Style(font_size=14.0),
                        )
                    ]
                ),
            ),
            # Divider + footer
            Divider(
                key="footer-divider",
                style=Style(margin=Edge(top=24.0, bottom=8.0)),
            ),
            Text(
                content=counter_text,
                key="footer-counter",
                style=Style(font_size=12.0),
            ),
        ],
    )
```

**O que está acontecendo:**

- O `Column` raiz usa `Edge.symmetric(vertical=24.0, horizontal=20.0)` para um espaçamento confortável sem precisar definir cada lado manualmente.
- O `Input` é **controlado**: `value=app.state.query` garante que o campo sempre reflita o estado — nunca há dessincronia entre o que está na tela e o que está no estado.
- A expressão ternária `accordion_items if accordion_items else [Text(...)]` entrega o estado vazio de forma declarativa: nenhum `if` extra, nenhuma lógica de renderização condicional fora da árvore.
- `Divider` com `style=Style(margin=Edge(top=24.0, bottom=8.0))` separa visualmente o rodapé do conteúdo principal.

!!! tip "Dica"
    `Edge.symmetric(vertical=v, horizontal=h)` é um atalho de `Style` para definir
    `top=v, bottom=v, left=h, right=h` de uma vez. Veja outros atalhos como
    `Edge.all(n)` e `Edge.only(top=n)` no exemplo
    [Perfil com Abas](./tabs-profile.md).

---

## Passo 8 — O arquivo completo

Aqui está o `app.py` completo, pronto para copiar e colar:

```python
"""FAQ Accordion — demonstrates the Disclosure pattern with ``Accordion``.

A realistic FAQ page that manages a list of question/answer pairs and tracks
which entry (if any) is currently expanded.  The app enforces a single-open
policy: opening one item automatically collapses the previously open one,
keeping the page compact and focused.  A search field filters the visible
entries in real time so users can quickly jump to the answer they need.

Like every tempestweb example, this exact ``view`` runs unchanged in both
execution modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

The application never names a transport — that is the whole point.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Style, Widget
from tempest_core.components import Accordion, Card, Divider
from tempest_core.style import Edge, FontWeight
from tempest_core.widgets import Column, Input, Row, Text
from tempest_core.widgets.events import TextChangeEvent

_FAQ_ENTRIES: list[tuple[str, str]] = [
    (
        "What is tempestweb?",
        "tempestweb is a framework that lets you build interactive web applications "
        "entirely in typed Python. You declare a widget tree once and the framework "
        "renders it in the browser (Mode A, Pyodide/WASM) or via a FastAPI "
        "WebSocket server (Mode B) — your view function never needs to know "
        "which mode is active.",
    ),
    (
        "Do I need to write any JavaScript?",
        "No. The client-side runtime is a small, zero-dependency JavaScript module "
        "that ships with the framework. Application logic lives exclusively in Python; "
        "the JS layer only handles DOM patching and transport I/O.",
    ),
    (
        "What is the difference between Mode A and Mode B?",
        "Mode A runs Python directly in the browser via Pyodide (WebAssembly). "
        "There is no server round-trip for state changes — everything happens "
        "client-side. Mode B runs Python on a FastAPI server; the browser sends "
        "events over a WebSocket and receives patch sequences back. Mode A is "
        "simpler to deploy (static hosting); Mode B gives full server-side access "
        "to databases and services.",
    ),
    (
        "How do I manage state?",
        "Define a plain Python ``@dataclass`` as your state and pass a fresh "
        "instance to ``make_state()``. Inside your ``view`` function you call "
        "``app.set_state(lambda s: ...)`` to mutate state and trigger a "
        "reconciled rebuild. The framework diffs the old and new widget trees "
        "and sends only the minimal patch sequence to the renderer.",
    ),
    (
        "Can I use third-party Python packages?",
        "In Mode B (server) you can use any Python package as normal. In Mode A "
        "(Pyodide) you are limited to packages that Pyodide ships or that are "
        "pure-Python wheels, because the package must run inside the browser's "
        "WebAssembly sandbox.",
    ),
    (
        "Is TypeScript or a build step required?",
        "No TypeScript and no build step. The client runtime is plain ES-module "
        "JavaScript. You open the app with a single ``<script type='module'>`` "
        "tag — no bundler, no transpiler, no node_modules.",
    ),
    (
        "How does styling work?",
        "Styles are inline, typed Python objects (``Style``, ``Edge``, ``Color``, "
        "etc.). There is no CSS cascade. Each widget carries its own ``Style`` "
        "instance; the renderer serialises it to inline DOM styles. This keeps "
        "styles predictable, refactorable with mypy, and free of selector "
        "specificity surprises.",
    ),
]


@dataclass
class FaqState:
    """State for the FAQ accordion app.

    Attributes:
        open_index: The index of the currently expanded FAQ entry, or ``-1``
            when all items are collapsed.
        query: The current value of the search/filter field.
    """

    open_index: int = -1
    query: str = ""


def make_state() -> FaqState:
    """Build the initial FAQ state with the first entry pre-expanded.

    Returns:
        A fresh :class:`FaqState` with the first accordion open so the page
        renders a non-empty visible body on first mount.
    """
    return FaqState(open_index=0)


def view(app: App[FaqState]) -> Widget:
    """Render the FAQ accordion page from the current state.

    The page has three regions:

    1. A title heading and a live-search ``Input`` that filters entries.
    2. A ``Column`` of ``Accordion`` items — one per matching FAQ entry.
       A single-open policy means toggling an entry collapses whatever was
       previously open.
    3. A muted footer showing how many entries match the current query.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def on_search(event: TextChangeEvent) -> None:
        """Update the query and reset the open item when the filter changes.

        Args:
            event: The text-change event carrying the new input value.
        """

        def mutate(s: FaqState) -> None:
            s.query = event.value
            s.open_index = -1

        app.set_state(mutate)

    def toggle(entry_index: int) -> None:
        """Expand the clicked entry or collapse it if it is already open.

        Args:
            entry_index: The index into :data:`_FAQ_ENTRIES` that was toggled.
        """

        def mutate(s: FaqState) -> None:
            s.open_index = -1 if s.open_index == entry_index else entry_index

        app.set_state(mutate)

    query_lower = app.state.query.strip().lower()
    visible: list[tuple[int, str, str]] = [
        (idx, question, answer)
        for idx, (question, answer) in enumerate(_FAQ_ENTRIES)
        if not query_lower
        or query_lower in question.lower()
        or query_lower in answer.lower()
    ]

    accordion_items: list[Widget] = []
    for entry_index, question, answer in visible:
        is_open = app.state.open_index == entry_index

        def make_toggle(i: int = entry_index) -> None:
            """Closure toggling entry ``i``.

            Args:
                i: The FAQ entry index to toggle (default-bound at creation).
            """
            toggle(i)

        accordion_items.append(
            Accordion(
                key=f"faq-{entry_index}",
                title=question,
                open=is_open,
                on_toggle=make_toggle,
                children=[
                    Text(
                        content=answer,
                        key=f"answer-{entry_index}",
                        style=Style(font_size=15.0, line_height=1.6),
                    )
                ],
            )
        )

    total = len(_FAQ_ENTRIES)
    shown = len(visible)
    if query_lower:
        stripped = app.state.query.strip()
        counter_text = f'{shown} of {total} questions match "{stripped}"'
    else:
        counter_text = f"{total} questions"

    return Column(
        key="faq-root",
        style=Style(
            gap=0.0,
            padding=Edge.symmetric(vertical=24.0, horizontal=20.0),
        ),
        children=[
            Text(
                content="Frequently Asked Questions",
                key="heading",
                style=Style(font_size=26.0, font_weight=FontWeight.BOLD),
            ),
            Text(
                content="Browse the most common questions or search below.",
                key="subtitle",
                style=Style(font_size=14.0, margin=Edge(top=6.0, bottom=20.0)),
            ),
            Card(
                key="search-card",
                children=[
                    Row(
                        key="search-row",
                        style=Style(gap=8.0),
                        children=[
                            Text(content="Search:", key="search-label"),
                            Input(
                                key="search-input",
                                value=app.state.query,
                                placeholder="Filter questions…",
                                on_change=on_search,
                            ),
                        ],
                    )
                ],
            ),
            Column(
                key="accordion-list",
                style=Style(gap=8.0, margin=Edge(top=16.0)),
                children=(
                    accordion_items
                    if accordion_items
                    else [
                        Text(
                            content="No questions match your search.",
                            key="empty-msg",
                            style=Style(font_size=14.0),
                        )
                    ]
                ),
            ),
            Divider(
                key="footer-divider",
                style=Style(margin=Edge(top=24.0, bottom=8.0)),
            ),
            Text(
                content=counter_text,
                key="footer-counter",
                style=Style(font_size=12.0),
            ),
        ],
    )
```

---

## Passo 9 — Executar o app

Execute no **Modo A** (Python no browser via Pyodide/WASM):

```bash
tempestweb dev --mode wasm --path examples/faq-accordion
```

Execute no **Modo B** (Python no servidor via FastAPI + WebSocket):

```bash
tempestweb dev --mode server --path examples/faq-accordion
```

Abra `http://localhost:8000` no browser. Você deve ver:

- ✅ Título "Frequently Asked Questions" em destaque;
- ✅ Subtítulo e campo de busca dentro de um `Card`;
- ✅ Primeira pergunta já expandida ao carregar (graças a `make_state(open_index=0)`);
- ✅ Clicar em qualquer pergunta a expande e fecha a anteriormente aberta;
- ✅ Clicar em uma pergunta já aberta a recolhe;
- ✅ Digitar no campo de busca filtra os itens em tempo real;
- ✅ Quando nenhuma entrada corresponde, a mensagem "No questions match your search." aparece;
- ✅ O rodapé mostra o total de perguntas ou quantas correspondem à busca atual.

!!! check "Verificação completa"
    Para garantir que o código passa em todas as checagens de qualidade:

    ```bash
    ruff check examples/faq-accordion/app.py
    ruff format --check examples/faq-accordion/app.py
    mypy examples/faq-accordion/app.py
    ```

    Todos os três devem sair com código 0.

---

## Recapitulando

Neste tutorial você construiu uma página de FAQ completa com filtro ao vivo e aprendeu:

- 💡 **`Accordion`** é um *controlled component*: `open=bool` e `on_toggle=callable` são tudo o que você precisa. O estado fica no seu `@dataclass`, não dentro do widget.
- 💡 A **política single-open** cabe em uma linha: `s.open_index = -1 if s.open_index == entry_index else entry_index`. Nenhuma lógica especial de framework necessária.
- 💡 **Closures em loops** exigem o padrão `def f(i: int = entry_index)` para capturar o valor correto em cada iteração — uma pegadinha clássica do Python.
- 💡 **`Input` controlado** (`value=app.state.query`) garante que o campo nunca fique fora de sincronia com o estado — essencial para filtros ao vivo.
- 💡 **`Card` + `Row` + `Divider`** compõem um layout limpo sem nenhuma linha de CSS manual.
- 💡 O mesmo `app.py` roda nos dois modos — WASM e Servidor — sem nenhuma alteração.

---

## Próximos passos

- Veja o [tutorial central](../tutorial/index.md) para entender o ciclo de vida completo do tempestweb.
- Explore o padrão de abas no exemplo [Perfil com Abas](./tabs-profile.md).
- Adicione animações de abertura/fechamento ao `Accordion` com o `AnimatedSwitcher` (em breve).
