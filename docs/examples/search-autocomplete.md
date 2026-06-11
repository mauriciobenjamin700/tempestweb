# Busca com Autocomplete

Construa uma **busca de países com filtragem em tempo real**: conforme o usuário
digita, o widget `Autocomplete` exibe sugestões; pílulas `Chip` permitem restringir
por continente antes mesmo de digitar. 🔍

Ao final deste tutorial você terá um app completo que exercita `Autocomplete`,
`Chip`, `Wrap`, `Column`, `Row`, `Text` e `Button` — com dois handlers tipados
(`on_change` e `on_select`) e estado derivado recalculado a cada interação.

---

## O problema

Caixas de busca com autocomplete são onipresentes, mas implementá-las
corretamente envolve três desafios simultâneos:

1. **Filtragem ao vivo** — a lista de sugestões muda a cada tecla.
2. **Seleção vs. digitação** — confirmar uma sugestão é diferente de continuar
   digitando; o estado precisa distinguir os dois.
3. **Filtragem por categoria** — o usuário quer restringir o universo de
   resultados *antes* de digitar, usando pílulas clicáveis.

O tempestweb resolve tudo isso com estado explícito e dois eventos tipados:
`TextChangeEvent` (cada keystroke) e `SelectEvent` (item escolhido).

!!! note "O que você vai exercitar"
    - `Autocomplete` — campo com lista de sugestões dinâmica.
    - `Chip` — pílula clicável com estado `selected` para filtros de categoria.
    - `Wrap` — layout que flui as pílulas automaticamente quando o espaço é insuficiente.
    - `TextChangeEvent` e `SelectEvent` — os dois eventos tipados do `Autocomplete`.
    - Estado derivado com `recompute()` — sugestões recalculadas sempre que query ou categoria mudam.
    - Closures nos handlers de categoria — `_make_chip` captura o `cat` correto para cada pílula.

---

## Pré-requisitos

Antes de continuar, certifique-se de ter feito a
[Instalação](../installation.md) e lido o
[Tutorial do Counter](../tutorial/index.md) — este exemplo assume que você já
conhece `Column`, `Row`, `Text`, `App`, `make_state`, `view` e o ciclo de
`set_state`.

---

## O app completo

Este é o código exato de
[`examples/search-autocomplete/app.py`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/search-autocomplete/app.py).
Copie, rode, e depois leia a explicação peça por peça.

```python
"""Search with autocomplete — exercises Autocomplete, Chip, and dynamic filtering.

A realistic country-search widget: as the user types, the
:class:`~tempestweb._core.widgets.Autocomplete` widget narrows the suggestion
list in real time. Selecting a suggestion commits it as the active choice and
shows it as a :class:`~tempestweb._core.components.Chip` below the field. The
user can clear the committed choice with a button and start over.

The demo also showcases *category filtering*: three
:class:`~tempestweb._core.components.Chip` pills let the user restrict suggestions
to a continent (All / Americas / Europe), so the autocomplete's ``options``
list changes whenever the query *or* the category filter changes.

Run in either mode — the ``view`` function is transport-agnostic::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempestweb._core import App, Style, Widget
from tempestweb._core.components import Chip
from tempestweb._core.style import Edge
from tempestweb._core.widgets import (
    Autocomplete,
    Button,
    Column,
    Row,
    Text,
    Wrap,
)
from tempestweb._core.widgets.events import SelectEvent, TextChangeEvent

# ---------------------------------------------------------------------------
# Data catalog
# ---------------------------------------------------------------------------

_COUNTRIES: list[tuple[str, str]] = [
    ("Argentina", "Americas"),
    ("Bolivia", "Americas"),
    ("Brazil", "Americas"),
    ("Canada", "Americas"),
    ("Chile", "Americas"),
    ("Colombia", "Americas"),
    ("Ecuador", "Americas"),
    ("Mexico", "Americas"),
    ("Paraguay", "Americas"),
    ("Peru", "Americas"),
    ("United States", "Americas"),
    ("Uruguay", "Americas"),
    ("Venezuela", "Americas"),
    ("Austria", "Europe"),
    ("Belgium", "Europe"),
    ("Czech Republic", "Europe"),
    ("Denmark", "Europe"),
    ("Finland", "Europe"),
    ("France", "Europe"),
    ("Germany", "Europe"),
    ("Greece", "Europe"),
    ("Hungary", "Europe"),
    ("Ireland", "Europe"),
    ("Italy", "Europe"),
    ("Netherlands", "Europe"),
    ("Norway", "Europe"),
    ("Poland", "Europe"),
    ("Portugal", "Europe"),
    ("Romania", "Europe"),
    ("Spain", "Europe"),
    ("Sweden", "Europe"),
    ("Switzerland", "Europe"),
    ("United Kingdom", "Europe"),
]

_CATEGORIES: list[str] = ["All", "Americas", "Europe"]

_MAX_SUGGESTIONS: int = 8


def _filter_suggestions(query: str, category: str) -> list[str]:
    """Return up to ``_MAX_SUGGESTIONS`` country names matching the current query.

    Matching is case-insensitive and substring-based so partial strings like
    ``"bra"`` find ``"Brazil"`` immediately. The ``category`` filter limits the
    pool to a single continent when it is not ``"All"``.

    Args:
        query: The current text typed into the search field.
        category: The active category filter — ``"All"`` disables the filter.

    Returns:
        A list of at most :data:`_MAX_SUGGESTIONS` matching country names in
        alphabetical order.
    """
    q = query.strip().lower()
    matches: list[str] = []
    for name, continent in _COUNTRIES:
        if category != "All" and continent != category:
            continue
        if not q or q in name.lower():
            matches.append(name)
    return sorted(matches)[:_MAX_SUGGESTIONS]


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class SearchState:
    """State for the search-autocomplete example.

    Attributes:
        query: The live text in the autocomplete field.
        category: The active continent filter.
        committed: The country name that was explicitly selected, or ``""``
            when nothing has been confirmed yet.
        suggestions: The current filtered suggestion list derived from
            ``query`` and ``category``; recomputed on every relevant mutation.
    """

    query: str = ""
    category: str = "All"
    committed: str = ""
    suggestions: list[str] = field(default_factory=list)

    def recompute(self) -> None:
        """Refresh :attr:`suggestions` from the current query and category.

        Called internally after every mutation that changes the filter state.
        """
        self.suggestions = _filter_suggestions(self.query, self.category)


def make_state() -> SearchState:
    """Build the initial state with a full suggestion list.

    Returns:
        A fresh :class:`SearchState` with all countries visible and no active
        query or selection.
    """
    s = SearchState()
    s.recompute()
    return s


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[SearchState]) -> Widget:
    """Render the search-autocomplete UI from the current state.

    The view is a vertical column with three sections:

    1. **Category filter** — three :class:`Chip` pills to narrow by continent.
    2. **Autocomplete field** — the live-filtered text field.
    3. **Result area** — either a confirmation card for the committed country
       or a placeholder prompt.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    s: SearchState = app.state

    # -- handlers ----------------------------------------------------------

    def on_query_change(event: TextChangeEvent) -> None:
        """Update the live query and refresh suggestions on each keystroke.

        Args:
            event: The text-change event carrying the new input value.
        """

        def mutate(st: SearchState) -> None:
            st.query = event.value
            st.committed = ""
            st.recompute()

        app.set_state(mutate)

    def on_suggestion_select(event: SelectEvent) -> None:
        """Commit the selected suggestion and clear the live query.

        Args:
            event: The select event carrying the chosen suggestion value.
        """

        def mutate(st: SearchState) -> None:
            st.committed = event.value
            st.query = event.value
            st.suggestions = []

        app.set_state(mutate)

    def on_clear() -> None:
        """Reset the query, committed selection and suggestions."""

        def mutate(st: SearchState) -> None:
            st.query = ""
            st.committed = ""
            st.recompute()

        app.set_state(mutate)

    def on_category(cat: str) -> None:
        """Switch the active category filter and refresh suggestions.

        Args:
            cat: The category label to activate.
        """

        def mutate(st: SearchState) -> None:
            st.category = cat
            st.committed = ""
            st.query = ""
            st.recompute()

        app.set_state(mutate)

    # -- category chips ----------------------------------------------------

    def _make_chip(cat: str) -> Widget:
        """Build one category-filter chip for ``cat``.

        Args:
            cat: The category label this chip represents.

        Returns:
            A :class:`Chip` widget bound to ``on_category``.
        """

        def click() -> None:
            on_category(cat)

        return Chip(
            key=f"cat-{cat}",
            label=cat,
            selected=(s.category == cat),
            on_click=click,
        )

    category_chips: list[Widget] = [_make_chip(cat) for cat in _CATEGORIES]

    # -- result area -------------------------------------------------------

    if s.committed:
        result_children: list[Widget] = [
            Text(
                key="chosen-label",
                content="Selected country:",
                style=Style(font_size=13.0),
            ),
            Row(
                key="chosen-row",
                style=Style(gap=8.0),
                children=[
                    Text(
                        key="chosen-value",
                        content=s.committed,
                        style=Style(font_size=18.0),
                    ),
                    Button(
                        key="clear-btn",
                        label="Clear",
                        on_click=on_clear,
                        style=Style(
                            padding=Edge.symmetric(vertical=4.0, horizontal=10.0),
                            radius=6.0,
                        ),
                    ),
                ],
            ),
        ]
    else:
        result_children = [
            Text(
                key="prompt",
                content="Type a country name or pick one from the suggestions.",
                style=Style(font_size=14.0),
            ),
        ]

    # -- root layout -------------------------------------------------------

    return Column(
        key="root",
        style=Style(gap=16.0, padding=Edge.all(24.0)),
        children=[
            Text(
                key="heading",
                content="Country Search",
                style=Style(font_size=22.0),
            ),
            Text(
                key="subheading",
                content="Filter by continent, then search:",
                style=Style(font_size=14.0),
            ),
            Wrap(
                key="categories",
                style=Style(gap=8.0),
                children=category_chips,
            ),
            Autocomplete(
                key="search",
                value=s.query,
                placeholder="e.g. Brazil, France…",
                options=s.suggestions,
                on_change=on_query_change,
                on_select=on_suggestion_select,
            ),
            Column(
                key="result",
                style=Style(gap=8.0, padding=Edge.all(12.0), radius=10.0),
                children=result_children,
            ),
        ],
    )
```

---

## Explicando peça por peça

### 1. O catálogo de dados

```python
_COUNTRIES: list[tuple[str, str]] = [
    ("Argentina", "Americas"),
    ("Brazil", "Americas"),
    ("France", "Europe"),
    # ...
]

_CATEGORIES: list[str] = ["All", "Americas", "Europe"]

_MAX_SUGGESTIONS: int = 8
```

Os dados ficam fora de qualquer classe — são constantes do módulo, imutáveis.
`_COUNTRIES` é uma lista de tuplas `(nome, continente)`. `_MAX_SUGGESTIONS`
garante que a lista de sugestões não cresça indefinidamente, tornando o DOM
pesado.

!!! tip "Dica"
    Em um app real você buscaria esses dados de uma API ou banco de dados. A
    função `_filter_suggestions` seria `async` e chamaria um repositório. A
    estrutura do `view` e do estado permanece idêntica — só o origin dos dados
    muda.

---

### 2. A função de filtragem pura

```python
def _filter_suggestions(query: str, category: str) -> list[str]:
    q = query.strip().lower()
    matches: list[str] = []
    for name, continent in _COUNTRIES:
        if category != "All" and continent != category:
            continue
        if not q or q in name.lower():
            matches.append(name)
    return sorted(matches)[:_MAX_SUGGESTIONS]
```

Dois critérios combinados:

- **Continente:** se `category != "All"`, exclui países de outros continentes.
- **Query:** `q in name.lower()` faz correspondência por substring
  (case-insensitive). `"bra"` encontra `"Brazil"`. Se `q` é vazio, todos os
  países do continente aparecem.

O resultado é ordenado alfabeticamente e truncado em `_MAX_SUGGESTIONS`.

!!! note "Nota"
    A função não sabe nada sobre `SearchState` nem sobre `App` — ela é
    completamente pura e testável de forma isolada com `pytest`.

---

### 3. O estado com `recompute()`

```python
@dataclass
class SearchState:
    query: str = ""
    category: str = "All"
    committed: str = ""
    suggestions: list[str] = field(default_factory=list)

    def recompute(self) -> None:
        self.suggestions = _filter_suggestions(self.query, self.category)
```

`suggestions` é **estado derivado**: sempre calculado a partir de `query` e
`category`. Em vez de recalcular em cada handler separadamente, o método
`recompute()` centraliza essa lógica. Qualquer handler que mudar `query` ou
`category` chama `recompute()` antes de encerrar a mutação.

!!! info "Estado derivado vs. estado independente"
    `query`, `category` e `committed` são estados **independentes** (o usuário
    os controla diretamente). `suggestions` é **derivado** — nunca deve ser
    alterado diretamente; sempre via `recompute()`. Esse padrão evita
    inconsistências onde `suggestions` e `query` ficam "fora de sincronia".

`make_state()` chama `recompute()` imediatamente, então ao abrir o app o
campo já exibe sugestões (todos os países, sem filtro).

---

### 4. Dois eventos distintos: `on_change` vs. `on_select`

O `Autocomplete` expõe dois handlers com semânticas diferentes:

```python
Autocomplete(
    key="search",
    value=s.query,
    placeholder="e.g. Brazil, France…",
    options=s.suggestions,
    on_change=on_query_change,
    on_select=on_suggestion_select,
)
```

| Handler | Evento | Quando dispara |
|---|---|---|
| `on_change` | `TextChangeEvent` | A cada tecla digitada no campo |
| `on_select` | `SelectEvent` | Quando o usuário clica em uma sugestão |

#### Handler `on_change` — cada keystroke

```python
def on_query_change(event: TextChangeEvent) -> None:
    def mutate(st: SearchState) -> None:
        st.query = event.value
        st.committed = ""
        st.recompute()

    app.set_state(mutate)
```

Três coisas acontecem atomicamente:

1. `st.query` recebe o texto atual do campo.
2. `st.committed` é apagado — o usuário voltou a digitar, então a seleção
   anterior não é mais válida.
3. `st.recompute()` recalcula as sugestões para o novo `query`.

#### Handler `on_select` — seleção de sugestão

```python
def on_suggestion_select(event: SelectEvent) -> None:
    def mutate(st: SearchState) -> None:
        st.committed = event.value
        st.query = event.value
        st.suggestions = []

    app.set_state(mutate)
```

Aqui o comportamento é oposto: a lista de sugestões é **esvaziada** (não há
mais nada para mostrar) e `committed` recebe o valor escolhido. `query` também
recebe o valor para que o campo de texto exiba o nome do país selecionado.

!!! tip "Dica"
    `SelectEvent.value` carrega exatamente o item da lista `options` que o
    usuário clicou — sem necessidade de índice ou mapeamento manual.

---

### 5. Chips de categoria com closures

```python
def _make_chip(cat: str) -> Widget:
    def click() -> None:
        on_category(cat)

    return Chip(
        key=f"cat-{cat}",
        label=cat,
        selected=(s.category == cat),
        on_click=click,
    )

category_chips: list[Widget] = [_make_chip(cat) for cat in _CATEGORIES]
```

A função `_make_chip` cria um chip por categoria. O ponto crítico é o uso de
uma **função-fábrica** em vez de um lambda direto no `for`. Se você escrevesse:

```python
# ❌ Armadilha clássica de closure em loop
for cat in _CATEGORIES:
    Chip(on_click=lambda: on_category(cat), ...)
```

todos os lambdas capturariam a **mesma** variável `cat` do loop — ao clicar,
todos disparariam com o valor final do loop (`"Europe"`). `_make_chip` resolve
isso porque cada chamada cria um **novo escopo** com seu próprio `cat`.

`selected=(s.category == cat)` renderiza o chip como ativo visualmente quando
ele corresponde à categoria atual do estado.

!!! warning "Aviso"
    Esse padrão — fábrica para capturar variável de loop — é necessário sempre
    que você criar widgets com handlers dentro de um `for`. Lambda direto no
    loop é uma armadilha de closure clássica em Python.

---

### 6. Área de resultado condicional

```python
if s.committed:
    result_children: list[Widget] = [
        Text(
            key="chosen-label",
            content="Selected country:",
            style=Style(font_size=13.0),
        ),
        Row(
            key="chosen-row",
            style=Style(gap=8.0),
            children=[
                Text(
                    key="chosen-value",
                    content=s.committed,
                    style=Style(font_size=18.0),
                ),
                Button(
                    key="clear-btn",
                    label="Clear",
                    on_click=on_clear,
                    style=Style(
                        padding=Edge.symmetric(vertical=4.0, horizontal=10.0),
                        radius=6.0,
                    ),
                ),
            ],
        ),
    ]
else:
    result_children = [
        Text(
            key="prompt",
            content="Type a country name or pick one from the suggestions.",
            style=Style(font_size=14.0),
        ),
    ]
```

A `view` constrói a lista de filhos do painel de resultado **antes** de
montar a árvore final. Quando há `committed`, exibe o nome em destaque e um
botão "Clear". Quando não há, exibe apenas uma instrução.

Montar `result_children` antes do `return Column(...)` mantém o código legível:
a árvore principal fica limpa, sem lógicas `if/else` aninhadas no meio dos
argumentos.

!!! tip "Dica"
    Esse padrão — pré-computar listas de filhos — é recomendado sempre que a
    árvore tiver ramificações condicionais. Evita ternários profundamente
    aninhados nos argumentos do widget pai.

---

### 7. O layout com `Wrap`

```python
Wrap(
    key="categories",
    style=Style(gap=8.0),
    children=category_chips,
),
```

`Wrap` é um container que posiciona os filhos em linha e **quebra para a
próxima linha** automaticamente quando o espaço horizontal se esgota. Para três
chips curtos isso raramente importa, mas com muitas categorias (ou em telas
estreitas) o comportamento se torna essencial — diferente de `Row`, que
transbordaria o container.

---

### 8. `Edge.symmetric` para padding assimétrico

```python
style=Style(
    padding=Edge.symmetric(vertical=4.0, horizontal=10.0),
    radius=6.0,
),
```

`Edge.symmetric` cria um `Edge` com `top=bottom=vertical` e
`left=right=horizontal` — um atalho conveniente para padding de botão
("mais largo do que alto"). Compare com `Edge.all(n)` (mesmo valor nos quatro
lados) e `Edge(top, right, bottom, left)` (controle total).

---

## Rodando o app 🚀

Salve o arquivo em `examples/search-autocomplete/app.py` e escolha o modo:

=== "Modo WASM (Python no browser)"

    ```bash
    tempestweb dev --mode wasm examples/search-autocomplete/app.py
    ```

    O Pyodide carrega o Python completo no browser. Nenhum servidor, nenhum
    WebSocket — os handlers Python rodam localmente no tab.

=== "Modo Server (FastAPI + WebSocket)"

    ```bash
    tempestweb dev --mode server examples/search-autocomplete/app.py
    ```

    Um servidor FastAPI sobe localmente. O cliente JS conecta via WebSocket,
    envia os eventos de digitação/seleção e recebe patches de diff de volta.

!!! check "Mesmo código, dois modos"
    Repare que o `app.py` não menciona `wasm` nem `server` em lugar algum.
    A fronteira de transporte fica completamente dentro do `tempestweb` — você
    só escolhe no momento de rodar.

Abra o browser em `http://localhost:8000` e experimente:

1. Clique em **"Americas"** — as sugestões mudam para países das Américas.
2. Digite `"bra"` — a lista se filtra para `Brazil` imediatamente.
3. Clique em `Brazil` na lista — o painel de resultado exibe o país selecionado.
4. Clique em **"Clear"** — o campo e o resultado voltam ao estado inicial.

---

## Recapitulando

Neste exemplo você aprendeu:

- ✅ **`Autocomplete`** — campo com sugestões dinâmicas via `options`; dois
  handlers tipados: `on_change` (`TextChangeEvent`) e `on_select` (`SelectEvent`).
- ✅ **`Chip` com `selected`** — pílula clicável com estado visual de ativo/inativo.
- ✅ **`Wrap`** — container que quebra linha automaticamente, ideal para conjuntos de chips.
- ✅ **Estado derivado + `recompute()`** — centraliza o recálculo de `suggestions` em um único método.
- ✅ **Fábrica de closures em loop** — `_make_chip(cat)` captura cada valor de `cat` corretamente; lambda direto no loop seria uma armadilha.
- ✅ **Pré-computar filhos condicionais** — monta `result_children` antes do `return` para manter a árvore principal legível.
- ✅ **`Edge.symmetric`** — atalho para padding assimétrico (botões, chips).

---

## Próximos passos

- Leia o [Tutorial do Counter](../tutorial/index.md) se ainda não o fez — ele
  explica `set_state` e o ciclo de rebuild com mais profundidade.
- Compare com o exemplo de [Formulário de Login](login-form.md) para ver como
  `on_change` é usado com múltiplos campos de texto.
- Veja como o exemplo de [Abas de Perfil](tabs-profile.md) usa `Chip` em um
  contexto de navegação.
- Explore outros exemplos na seção **Exemplos** para mais padrões de estado e
  composição de widgets.
