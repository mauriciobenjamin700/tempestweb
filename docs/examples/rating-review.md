# Formulário de Avaliação (Rating & Review)

> 🚀 **O que você vai construir:** um formulário completo de avaliação de produto — estrelas clicáveis com `Rating`, tags de aspecto togláveis com `Chip`, campo de texto livre com `TextArea`, validação inline e um cartão de resumo pós-envio.

---

## Por que esse exemplo importa?

Formulários de avaliação estão em toda parte — lojas, serviços, apps de entrega.
Eles combinam três tipos de controle de seleção num fluxo único:

| Controle | Widget | Finalidade |
|---|---|---|
| Nota com estrelas | `Rating` | Valor inteiro de 1 a N |
| Tags de aspecto | `Chip` | Seleção múltipla por toggle |
| Texto livre | `TextArea` | Corpo narrativo com contador |

Neste tutorial você vai aprender a:

- Usar `Rating` para capturar uma nota inteira;
- Criar handlers de toggle com fábrica de closures para `Chip`;
- Sincronizar `TextArea` via `TextChangeEvent`;
- Exibir um erro de validação inline antes de aceitar o envio;
- Mostrar um cartão de resumo após a submissão e redefinir o formulário.

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
└── rating-review/
    └── app.py
```

Crie a pasta e o arquivo:

```bash
mkdir -p examples/rating-review
touch examples/rating-review/app.py
```

---

## Passo 1 — Imports e catálogo de tags

Comece declarando os imports e a lista de palavras-chave que o revisor pode
selecionar como tags de aspecto.

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from tempestweb._core import App, Style, Widget
from tempestweb._core.components import Card, Chip, Divider, Rating
from tempestweb._core.style import Edge, FontWeight
from tempestweb._core.widgets import Button, Column, Row, Text, TextArea, Wrap
from tempestweb._core.widgets.events import TextChangeEvent

# ---------------------------------------------------------------------------
# Chip tag catalogue — aspect keywords the reviewer can toggle.
# ---------------------------------------------------------------------------
_ALL_TAGS: list[str] = [
    "Quality",
    "Value for money",
    "Fast delivery",
    "Great packaging",
    "Accurate description",
    "Good customer service",
    "Would recommend",
]
```

!!! tip "Dica"
    `_ALL_TAGS` é uma constante de módulo — não vive no estado porque nunca muda.
    O estado guarda apenas quais tags estão *selecionadas*.

**O que acabou de acontecer:**

- Os componentes `Rating` e `Chip` vêm de `tempestweb._core.components`.
- `Wrap` (de `tempestweb._core.widgets`) distribui os chips em múltiplas linhas
  automaticamente quando o espaço é insuficiente.
- `TextChangeEvent` é o evento disparado pelo `TextArea` a cada edição.

---

## Passo 2 — Definir o estado

O estado modela todos os dados mutáveis do formulário e o resultado pós-envio.

```python
@dataclass
class Review:
    """A completed review assembled from the form.

    Attributes:
        rating: The 1-based star rating chosen by the reviewer.
        tags: The aspect keywords selected by the reviewer.
        body: The free-text review body.
    """

    rating: int
    tags: list[str]
    body: str


@dataclass
class ReviewState:
    """State for the rating & review app.

    Attributes:
        rating: The currently selected star rating (0 = none chosen yet).
        selected_tags: The set of tag labels currently toggled on.
        body: The current text in the review TextArea.
        error: An inline validation message shown near the submit button.
        submitted_review: The assembled review after a valid submission, or
            ``None`` while the form is still being filled in.
    """

    rating: int = 0
    selected_tags: list[str] = field(default_factory=list)
    body: str = ""
    error: str = ""
    submitted_review: Review | None = None


def make_state() -> ReviewState:
    """Build the initial, empty review state.

    Returns:
        A fresh :class:`ReviewState` with nothing selected.
    """
    return ReviewState()
```

!!! info "Info"
    `submitted_review: Review | None = None` é o "modo do formulário". Enquanto
    for `None`, o `view` renderiza o formulário interativo. Quando preenchido,
    renderiza o cartão de resumo — troca de view sem mudança de rota.

**Dois dataclasses, responsabilidades separadas:**

- `Review` é **imutável após construção** — representa a avaliação finalizada.
- `ReviewState` é **mutável** — representa o trabalho em andamento no formulário.

---

## Passo 3 — Handlers de evento

Antes do layout, defina as quatro funções que respondem às interações do usuário.
Elas serão criadas dentro de `view()` para capturar `app` no closure.

```python
def view(app: App[ReviewState]) -> Widget:
    """Render the rating & review form (or summary) from the current state.

    When ``state.submitted_review`` is set the function renders a read-only
    summary card; otherwise it renders the interactive form so the user can
    fill in stars, tags and a text body.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    state: ReviewState = app.state

    # ... (a visão de resumo vem depois — veja o Passo 5)

    def set_rating(value: int) -> None:
        """Update the star rating in state.

        Args:
            value: The 1-based star value reported by the Rating component.
        """
        app.set_state(lambda s: setattr(s, "rating", value))

    def make_tag_handler(tag: str) -> Callable[[], None]:
        """Return a click handler that toggles ``tag`` in the selection list.

        Args:
            tag: The chip label to toggle on or off.

        Returns:
            A zero-argument handler that flips the tag's membership in
            ``state.selected_tags``.
        """

        def handler() -> None:
            def mutate(s: ReviewState) -> None:
                if tag in s.selected_tags:
                    s.selected_tags = [t for t in s.selected_tags if t != tag]
                else:
                    s.selected_tags = [*s.selected_tags, tag]

            app.set_state(mutate)

        return handler

    def edit_body(event: TextChangeEvent) -> None:
        """Synchronize the TextArea value into state.

        Args:
            event: The change event carrying the new text value.
        """
        app.set_state(lambda s: setattr(s, "body", event.value))

    def submit() -> None:
        """Validate the form and, when valid, assemble and store the review."""

        def mutate(s: ReviewState) -> None:
            if s.rating == 0:
                s.error = "Please select at least one star."
                return
            if not s.body.strip():
                s.error = "Please write a short review before submitting."
                return
            s.error = ""
            s.submitted_review = Review(
                rating=s.rating,
                tags=list(s.selected_tags),
                body=s.body.strip(),
            )

        app.set_state(mutate)
```

!!! tip "Dica — fábrica de closures para `Chip`"
    `make_tag_handler(tag)` retorna um handler diferente para cada tag.
    Se você usasse `lambda: toggle(tag)` diretamente num loop, **todas as lambdas
    capturariam o mesmo `tag`** (o último valor do iterador). A fábrica cria um
    escopo novo a cada chamada, garantindo que cada chip alterne apenas o seu
    próprio rótulo.

**Responsabilidades dos handlers:**

| Handler | Dispara quando | O que faz |
|---|---|---|
| `set_rating(value)` | Usuário clica numa estrela | Grava `value` em `state.rating` |
| `make_tag_handler(tag)` | Usuário clica num chip | Adiciona ou remove `tag` de `selected_tags` |
| `edit_body(event)` | Usuário digita no `TextArea` | Grava `event.value` em `state.body` |
| `submit()` | Usuário clica em "Submit review" | Valida e, se ok, monta `Review` |

---

## Passo 4 — Layout do formulário

Agora monte a árvore de widgets do formulário. O `Rating` fica numa `Row` ao lado
da dica textual; os `Chip`s ficam num `Wrap` que quebra linhas automaticamente;
o `TextArea` exibe um contador de caracteres abaixo dele.

```python
    # ------------------------------------------------------------------
    # Star rating label
    # ------------------------------------------------------------------
    rating_labels: dict[int, str] = {
        0: "Tap a star to rate",
        1: "Poor",
        2: "Fair",
        3: "Good",
        4: "Very good",
        5: "Excellent",
    }
    rating_hint: str = rating_labels.get(state.rating, "")

    # ------------------------------------------------------------------
    # Chip row
    # ------------------------------------------------------------------
    chip_widgets: list[Widget] = [
        Chip(
            key=f"chip-{tag}",
            label=tag,
            selected=tag in state.selected_tags,
            on_click=make_tag_handler(tag),
        )
        for tag in _ALL_TAGS
    ]

    # ------------------------------------------------------------------
    # Form layout
    # ------------------------------------------------------------------
    form_children: list[Widget] = [
        # --- Heading ---
        Text(
            content="Leave a review",
            key="heading",
            style=Style(font_size=22.0, font_weight=FontWeight.BOLD),
        ),
        Divider(key="heading-div"),
        # --- Star rating section ---
        Text(
            content="Overall rating",
            key="rating-label",
            style=Style(font_size=15.0, font_weight=FontWeight.BOLD),
        ),
        Row(
            key="rating-row",
            style=Style(gap=12.0),
            children=[
                Rating(
                    key="stars",
                    value=state.rating,
                    max_stars=5,
                    on_rate=set_rating,
                ),
                Text(
                    content=rating_hint,
                    key="rating-hint",
                    style=Style(font_size=14.0),
                ),
            ],
        ),
        # --- Aspect tags section ---
        Text(
            content="What did you think of? (optional)",
            key="tags-label",
            style=Style(font_size=15.0, font_weight=FontWeight.BOLD),
        ),
        Wrap(
            key="chips",
            style=Style(gap=8.0),
            children=chip_widgets,
        ),
        # --- Review body ---
        Text(
            content="Your review",
            key="body-label",
            style=Style(font_size=15.0, font_weight=FontWeight.BOLD),
        ),
        TextArea(
            key="body-input",
            value=state.body,
            placeholder="Share your experience with this product…",
            rows=5,
            max_length=1000,
            on_change=edit_body,
        ),
        Text(
            content=f"{len(state.body)}/1000 characters",
            key="char-count",
            style=Style(font_size=12.0),
        ),
    ]

    # Inline validation error (shown only when non-empty)
    if state.error:
        form_children.append(
            Text(
                content=state.error,
                key="error-msg",
                style=Style(font_size=14.0),
            )
        )

    form_children.append(
        Button(
            label="Submit review",
            on_click=submit,
            key="submit-btn",
        )
    )

    return Column(
        key="review-root",
        style=Style(gap=14.0, padding=Edge.all(20.0)),
        children=form_children,
    )
```

!!! info "Info — `Chip(selected=...)`"
    O parâmetro `selected` é recalculado a cada render: `tag in state.selected_tags`.
    Não há estado interno no `Chip` — a aparência (preenchido vs. contornado) é
    determinada inteiramente pelo estado Python. Essa é a essência do modelo
    declarativo do tempestweb.

!!! tip "Dica — erro inline vs. modal"
    Adicionar o `Text` de erro condicionalmente à lista `form_children` (em vez de
    usar um `if` com dois `return` separados) mantém o restante do formulário visível.
    O usuário pode corrigir o problema sem perder o que já digitou.

**Destaques do layout:**

- `Rating(value=state.rating, max_stars=5, on_rate=set_rating)` — o componente
  renderiza as estrelas; `on_rate` recebe o valor inteiro clicado.
- `Wrap` distribui os filhos em múltiplas linhas conforme o espaço disponível —
  ideal para conjuntos de chips de tamanho variável.
- `TextArea(rows=5, max_length=1000)` — altura inicial em linhas e limite de
  caracteres declarados diretamente no widget.
- O contador `f"{len(state.body)}/1000 characters"` é recalculado a cada
  `TextChangeEvent`, sem nenhum estado extra.

---

## Passo 5 — Cartão de resumo pós-envio

Quando `state.submitted_review` não é `None`, o `view` retorna um layout
completamente diferente — um cartão de leitura com botão de redefinição.

Adicione este bloco **no início de `view`**, logo após `state: ReviewState = app.state`:

```python
    # ------------------------------------------------------------------
    # Post-submission summary view
    # ------------------------------------------------------------------
    if state.submitted_review is not None:
        rev: Review = state.submitted_review
        stars_text: str = "★" * rev.rating + "☆" * (5 - rev.rating)
        tags_text: str = ", ".join(rev.tags) if rev.tags else "—"

        def _reset_mutate(s: ReviewState) -> None:
            s.submitted_review = None
            s.rating = 0
            s.selected_tags = []
            s.body = ""
            s.error = ""

        def reset_form() -> None:
            """Reset the form to initial state."""
            app.set_state(_reset_mutate)

        return Column(
            key="summary-root",
            style=Style(gap=16.0, padding=Edge.all(20.0)),
            children=[
                Text(
                    content="Review submitted!",
                    key="summary-heading",
                    style=Style(font_size=20.0, font_weight=FontWeight.BOLD),
                ),
                Card(
                    key="summary-card",
                    children=[
                        Text(
                            content=f"Rating: {stars_text}",
                            key="sum-rating",
                            style=Style(font_size=18.0),
                        ),
                        Text(
                            content=f"Tags: {tags_text}",
                            key="sum-tags",
                            style=Style(font_size=14.0),
                        ),
                        Divider(key="sum-divider"),
                        Text(
                            content=rev.body,
                            key="sum-body",
                            style=Style(font_size=15.0),
                        ),
                    ],
                ),
                Button(
                    label="Write another review",
                    on_click=reset_form,
                    key="reset-btn",
                ),
            ],
        )
```

!!! warning "Aviso — `return` antecipado em `view`"
    O `return` dentro do `if state.submitted_review is not None` encerra a função
    antes de construir o formulário. Isso é **intencional** — é o mesmo padrão de
    "early return" usado para mostrar telas de loading ou de erro. O reconciliador
    recebe uma árvore completamente diferente e aplica os patches necessários no DOM.

**Fluxo completo de estado:**

```
rating=0, body="", submitted_review=None
        ↓ usuário preenche e clica "Submit review"
rating=4, body="Ótimo produto!", submitted_review=Review(...)
        ↓ reconciliador troca a árvore
cartão de resumo aparece
        ↓ usuário clica "Write another review"
rating=0, body="", submitted_review=None
        ↓ formulário reaparece
```

---

## Passo 6 — Código completo

Aqui está o arquivo `app.py` completo, pronto para copiar e colar:

```python
"""Rating & review — exercises Rating stars, Chip tag toggles and TextArea.

This exact ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

The demo builds a complete product-review form:

* A :class:`~tempestweb._core.components.Rating` row lets the user pick 1–5 stars.
* A :class:`~tempestweb._core.widgets.Wrap` of togglable
  :class:`~tempestweb._core.components.Chip` widgets lets the user tag the review
  with relevant aspect keywords (e.g. "Quality", "Value for money").
* A :class:`~tempestweb._core.widgets.TextArea` collects the free-text body.
* A submit :class:`~tempestweb._core.widgets.Button` assembles and stores the
  finished review in the state, while a guard ensures at least one star and a
  non-empty body before accepting.

The assembled review is displayed as a read-only summary card after submission,
and a "Write another" button resets the form for the next review.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from tempestweb._core import App, Style, Widget
from tempestweb._core.components import Card, Chip, Divider, Rating
from tempestweb._core.style import Edge, FontWeight
from tempestweb._core.widgets import Button, Column, Row, Text, TextArea, Wrap
from tempestweb._core.widgets.events import TextChangeEvent

# ---------------------------------------------------------------------------
# Chip tag catalogue — aspect keywords the reviewer can toggle.
# ---------------------------------------------------------------------------
_ALL_TAGS: list[str] = [
    "Quality",
    "Value for money",
    "Fast delivery",
    "Great packaging",
    "Accurate description",
    "Good customer service",
    "Would recommend",
]


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class Review:
    """A completed review assembled from the form.

    Attributes:
        rating: The 1-based star rating chosen by the reviewer.
        tags: The aspect keywords selected by the reviewer.
        body: The free-text review body.
    """

    rating: int
    tags: list[str]
    body: str


@dataclass
class ReviewState:
    """State for the rating & review app.

    Attributes:
        rating: The currently selected star rating (0 = none chosen yet).
        selected_tags: The set of tag labels currently toggled on.
        body: The current text in the review TextArea.
        error: An inline validation message shown near the submit button.
        submitted_review: The assembled review after a valid submission, or
            ``None`` while the form is still being filled in.
    """

    rating: int = 0
    selected_tags: list[str] = field(default_factory=list)
    body: str = ""
    error: str = ""
    submitted_review: Review | None = None


def make_state() -> ReviewState:
    """Build the initial, empty review state.

    Returns:
        A fresh :class:`ReviewState` with nothing selected.
    """
    return ReviewState()


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[ReviewState]) -> Widget:
    """Render the rating & review form (or summary) from the current state.

    When ``state.submitted_review`` is set the function renders a read-only
    summary card; otherwise it renders the interactive form so the user can
    fill in stars, tags and a text body.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    state: ReviewState = app.state

    # ------------------------------------------------------------------
    # Post-submission summary view
    # ------------------------------------------------------------------
    if state.submitted_review is not None:
        rev: Review = state.submitted_review
        stars_text: str = "★" * rev.rating + "☆" * (5 - rev.rating)
        tags_text: str = ", ".join(rev.tags) if rev.tags else "—"

        def _reset_mutate(s: ReviewState) -> None:
            s.submitted_review = None
            s.rating = 0
            s.selected_tags = []
            s.body = ""
            s.error = ""

        def reset_form() -> None:
            """Reset the form to initial state."""
            app.set_state(_reset_mutate)

        return Column(
            key="summary-root",
            style=Style(gap=16.0, padding=Edge.all(20.0)),
            children=[
                Text(
                    content="Review submitted!",
                    key="summary-heading",
                    style=Style(font_size=20.0, font_weight=FontWeight.BOLD),
                ),
                Card(
                    key="summary-card",
                    children=[
                        Text(
                            content=f"Rating: {stars_text}",
                            key="sum-rating",
                            style=Style(font_size=18.0),
                        ),
                        Text(
                            content=f"Tags: {tags_text}",
                            key="sum-tags",
                            style=Style(font_size=14.0),
                        ),
                        Divider(key="sum-divider"),
                        Text(
                            content=rev.body,
                            key="sum-body",
                            style=Style(font_size=15.0),
                        ),
                    ],
                ),
                Button(
                    label="Write another review",
                    on_click=reset_form,
                    key="reset-btn",
                ),
            ],
        )

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def set_rating(value: int) -> None:
        """Update the star rating in state.

        Args:
            value: The 1-based star value reported by the Rating component.
        """
        app.set_state(lambda s: setattr(s, "rating", value))

    def make_tag_handler(tag: str) -> Callable[[], None]:
        """Return a click handler that toggles ``tag`` in the selection list.

        Args:
            tag: The chip label to toggle on or off.

        Returns:
            A zero-argument handler that flips the tag's membership in
            ``state.selected_tags``.
        """

        def handler() -> None:
            def mutate(s: ReviewState) -> None:
                if tag in s.selected_tags:
                    s.selected_tags = [t for t in s.selected_tags if t != tag]
                else:
                    s.selected_tags = [*s.selected_tags, tag]

            app.set_state(mutate)

        return handler

    def edit_body(event: TextChangeEvent) -> None:
        """Synchronize the TextArea value into state.

        Args:
            event: The change event carrying the new text value.
        """
        app.set_state(lambda s: setattr(s, "body", event.value))

    def submit() -> None:
        """Validate the form and, when valid, assemble and store the review."""

        def mutate(s: ReviewState) -> None:
            if s.rating == 0:
                s.error = "Please select at least one star."
                return
            if not s.body.strip():
                s.error = "Please write a short review before submitting."
                return
            s.error = ""
            s.submitted_review = Review(
                rating=s.rating,
                tags=list(s.selected_tags),
                body=s.body.strip(),
            )

        app.set_state(mutate)

    # ------------------------------------------------------------------
    # Star rating label
    # ------------------------------------------------------------------
    rating_labels: dict[int, str] = {
        0: "Tap a star to rate",
        1: "Poor",
        2: "Fair",
        3: "Good",
        4: "Very good",
        5: "Excellent",
    }
    rating_hint: str = rating_labels.get(state.rating, "")

    # ------------------------------------------------------------------
    # Chip row
    # ------------------------------------------------------------------
    chip_widgets: list[Widget] = [
        Chip(
            key=f"chip-{tag}",
            label=tag,
            selected=tag in state.selected_tags,
            on_click=make_tag_handler(tag),
        )
        for tag in _ALL_TAGS
    ]

    # ------------------------------------------------------------------
    # Form layout
    # ------------------------------------------------------------------
    form_children: list[Widget] = [
        # --- Heading ---
        Text(
            content="Leave a review",
            key="heading",
            style=Style(font_size=22.0, font_weight=FontWeight.BOLD),
        ),
        Divider(key="heading-div"),
        # --- Star rating section ---
        Text(
            content="Overall rating",
            key="rating-label",
            style=Style(font_size=15.0, font_weight=FontWeight.BOLD),
        ),
        Row(
            key="rating-row",
            style=Style(gap=12.0),
            children=[
                Rating(
                    key="stars",
                    value=state.rating,
                    max_stars=5,
                    on_rate=set_rating,
                ),
                Text(
                    content=rating_hint,
                    key="rating-hint",
                    style=Style(font_size=14.0),
                ),
            ],
        ),
        # --- Aspect tags section ---
        Text(
            content="What did you think of? (optional)",
            key="tags-label",
            style=Style(font_size=15.0, font_weight=FontWeight.BOLD),
        ),
        Wrap(
            key="chips",
            style=Style(gap=8.0),
            children=chip_widgets,
        ),
        # --- Review body ---
        Text(
            content="Your review",
            key="body-label",
            style=Style(font_size=15.0, font_weight=FontWeight.BOLD),
        ),
        TextArea(
            key="body-input",
            value=state.body,
            placeholder="Share your experience with this product…",
            rows=5,
            max_length=1000,
            on_change=edit_body,
        ),
        Text(
            content=f"{len(state.body)}/1000 characters",
            key="char-count",
            style=Style(font_size=12.0),
        ),
    ]

    # Inline validation error (shown only when non-empty)
    if state.error:
        form_children.append(
            Text(
                content=state.error,
                key="error-msg",
                style=Style(font_size=14.0),
            )
        )

    form_children.append(
        Button(
            label="Submit review",
            on_click=submit,
            key="submit-btn",
        )
    )

    return Column(
        key="review-root",
        style=Style(gap=14.0, padding=Edge.all(20.0)),
        children=form_children,
    )
```

---

## Passo 7 — Executar o app

Execute no **Modo A** (Python no browser via Pyodide):

```bash
tempestweb dev --mode wasm examples/rating-review/app.py
```

Execute no **Modo B** (Python no servidor via FastAPI + WebSocket):

```bash
tempestweb dev --mode server examples/rating-review/app.py
```

Abra `http://localhost:8000` no browser. Você deve ver:

- ✅ Título "Leave a review" em negrito com um `Divider` abaixo;
- ✅ Cinco estrelas clicáveis — a dica textual muda conforme a nota;
- ✅ Sete chips de aspecto togláveis que ficam preenchidos quando selecionados;
- ✅ `TextArea` com contador de caracteres `0/1000` atualizado em tempo real;
- ✅ Clicar em "Submit review" sem nota exibe o erro inline;
- ✅ Submissão válida substitui o formulário pelo cartão de resumo;
- ✅ "Write another review" redefine tudo para o estado inicial.

---

## Recapitulando

Neste tutorial você construiu um formulário de avaliação completo e aprendeu:

- 💡 **`Rating(value=..., max_stars=5, on_rate=handler)`** — recebe um inteiro e
  chama `handler(value)` ao clicar. Sem estado interno: a aparência é determinada
  por `value` vindo do estado Python.
- 💡 **`Chip(selected=..., on_click=handler)`** — o visual preenchido/contornado
  vem de `selected`; use uma fábrica de closures (`make_tag_handler`) para gerar
  um handler distinto por chip em loops.
- 💡 **`TextArea(value=..., on_change=handler)`** — sincronize via `event.value`
  no `TextChangeEvent`; o contador de caracteres é derivado diretamente do estado.
- 💡 **`Wrap`** distribui filhos em múltiplas linhas — ideal para conjuntos de
  chips de tamanho variável.
- 💡 **Validação inline** — adicione ou omita o widget de erro condicionalmente na
  lista `form_children` em vez de usar dois `return` separados. O usuário mantém
  o que já preencheu.
- 💡 **`submitted_review: Review | None`** funciona como seletor de modo: `None` →
  formulário; preenchido → resumo. Nenhuma rota extra necessária.
- 💡 O mesmo `app.py` roda nos dois modos — WASM e Servidor — sem nenhuma alteração.

---

## Próximos passos

- Veja o [tutorial central](../tutorial/index.md) para entender o ciclo de vida
  completo do tempestweb.
- Explore o exemplo [login-form](login-form.md) para ver validação em múltiplos
  campos com feedback por campo.
- Veja [signup-wizard](signup-wizard.md) para um formulário multi-etapa com
  barra de progresso.
- Consulte [data-table](data-table.md) para exibir as avaliações coletadas em
  formato tabular.
