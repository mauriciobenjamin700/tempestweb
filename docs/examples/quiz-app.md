# Quiz com Pontuação — Formulários e Fluxo de Navegação 🚀

Construa um quiz de múltipla escolha com 5 perguntas sequenciais, seleção de resposta via `RadioGroup`, barra de progresso e tela de resultados com nota — tudo isso **sem citar o transporte** nem escrever uma linha de JavaScript.

---

## O que você vai construir

Um quiz completo e funcional com:

- 📋 5 perguntas de ciência da computação apresentadas **uma por vez**
- 🔘 Seleção de resposta via **`RadioGroup`** (nenhum campo de texto, apenas cliques)
- 📊 **`ProgressBar`** mostrando o avanço ao longo do quiz
- ➡ Botão **Next** (avança) que só habilita após uma resposta ser selecionada
- ✅ Botão **Finish** na última pergunta para concluir o quiz
- 🏆 Tela de resultados com **pontuação**, **rótulo de nota** e resumo por questão (✓ / ✗)
- 🔄 Botão **Restart Quiz** para começar tudo de novo

!!! note "Nota — fluxo de tela vs. rotas"
    Este exemplo usa uma **variável booleana de estado** (`finished`) para alternar entre a tela de pergunta e a tela de resultados. Não há rotas nem URLs — o tempestweb reconstrói a árvore de widgets a cada mudança de estado. Para navegação com histórico e URLs veja o exemplo [Tabs - Perfil](./tabs-profile.md).

---

## Pré-requisitos

Certifique-se de ter o tempestweb instalado:

```bash
pip install tempestweb
```

Leitura recomendada antes de começar (opcional):

- [Tutorial básico](../tutorial/index.md) — primeiros passos com `App`, `view` e `set_state`
- [Gerenciando estado](../tutorial/state.md) — como `set_state` funciona
- [Modos de execução](../tutorial/modes.md) — WASM vs. servidor
- [Formulários de login](./login-form.md) — outro exemplo com formulários e validação

---

## Criando o projeto

```bash
mkdir -p examples/quiz-app
touch examples/quiz-app/app.py
```

---

## Passo 1 — Modelando os dados

Antes de pensar em UI, pense nos dados. O quiz tem dois tipos de dado distintos:

1. **Dados estáticos** — as perguntas e respostas corretas (nunca mudam em tempo de execução)
2. **Estado dinâmico** — o progresso do usuário (muda a cada interação)

Separe os dois. Para os dados estáticos, use um `dataclass` imutável (`frozen=True`) e uma constante de módulo:

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Question:
    """A single quiz question with answer options and the correct answer index.

    Attributes:
        prompt: The question text shown to the user.
        options: The list of answer labels in display order.
        correct: The 0-based index of the correct option.
    """

    prompt: str
    options: list[str]
    correct: int


#: The ordered list of questions used by the quiz.
QUESTIONS: list[Question] = [
    Question(
        prompt="Which data structure gives O(1) average-case lookup by key?",
        options=["Linked list", "Hash map", "Binary search tree", "Sorted array"],
        correct=1,
    ),
    Question(
        prompt="What is the time complexity of quicksort in the average case?",
        options=["O(n)", "O(n²)", "O(n log n)", "O(log n)"],
        correct=2,
    ),
    Question(
        prompt="Which HTTP method is idempotent and safe (read-only)?",
        options=["POST", "PUT", "DELETE", "GET"],
        correct=3,
    ),
    Question(
        prompt="In Python, which keyword is used to declare an async function?",
        options=["await", "async", "yield", "defer"],
        correct=1,
    ),
    Question(
        prompt="Which SQL clause filters groups produced by GROUP BY?",
        options=["WHERE", "HAVING", "FILTER", "LIMIT"],
        correct=1,
    ),
]
```

!!! tip "Dica — `frozen=True`"
    `frozen=True` torna o dataclass **imutável**: tentativas de alterar um campo levantam `FrozenInstanceError`. É a forma pythônica de declarar que `Question` é um dado de configuração, não estado mutável. O tempestweb nunca vai tentar aplicar patches sobre ele.

---

## Passo 2 — Definindo o estado

O estado precisa guardar apenas o **mínimo necessário** para reconstruir qualquer tela:

| Campo | Tipo | Significado |
|---|---|---|
| `current` | `int` | Índice da pergunta em exibição |
| `answers` | `dict[int, int]` | Mapeamento questão → opção escolhida |
| `finished` | `bool` | O usuário concluiu o quiz? |

```python
@dataclass
class QuizState:
    """All runtime state for the quiz application.

    Attributes:
        current: The index of the question currently displayed.
        answers: A mapping of question index to the chosen option index.
        finished: Whether the user has completed all questions.
    """

    current: int = 0
    answers: dict[int, int] = field(default_factory=dict)
    finished: bool = False


def make_state() -> QuizState:
    """Build the initial quiz state — first question, no answers yet.

    Returns:
        A fresh :class:`QuizState` ready to start the quiz.
    """
    return QuizState()
```

!!! tip "Dica — `field(default_factory=dict)`"
    Assim como com listas, **nunca** use `answers: dict[int, int] = {}` em um dataclass. O Python compartilharia o mesmo dicionário entre todas as instâncias. `field(default_factory=dict)` garante um dicionário novo a cada instância.

---

## Passo 3 — Funções auxiliares

Duas funções puras calculam a pontuação e o rótulo de nota. Elas ficam **fora** de `view()` — são facilmente testáveis em isolamento:

```python
def _score(answers: dict[int, int]) -> int:
    """Count the number of correct answers.

    Args:
        answers: A mapping of question index to the chosen option index.

    Returns:
        The number of questions answered correctly.
    """
    return sum(
        1
        for q_idx, chosen in answers.items()
        if 0 <= q_idx < len(QUESTIONS) and QUESTIONS[q_idx].correct == chosen
    )


def _grade_label(score: int, total: int) -> str:
    """Derive a human-readable grade label from the score fraction.

    Args:
        score: The number of correct answers.
        total: The total number of questions.

    Returns:
        A grade string such as ``"Excellent"`` or ``"Needs practice"``.
    """
    if total == 0:
        return "No questions"
    fraction: float = score / total
    if fraction >= 0.9:
        return "Excellent!"
    if fraction >= 0.7:
        return "Good job!"
    if fraction >= 0.5:
        return "Keep it up!"
    return "Needs practice"
```

| Fração acertada | Rótulo |
|---|---|
| ≥ 90 % | `"Excellent!"` |
| ≥ 70 % | `"Good job!"` |
| ≥ 50 % | `"Keep it up!"` |
| < 50 % | `"Needs practice"` |

---

## Passo 4 — O card de pergunta

Agora a UI. O card de pergunta é a parte mais rica: ele contém o `RadioGroup` e o botão de navegação.

A lógica de habilitação do botão merece atenção:

- `selected = state.answers.get(q_idx, -1)` — `-1` significa "nenhuma resposta ainda"
- `button_enabled = selected >= 0` — o botão só reage a cliques após uma seleção

```python
from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.components import AppBar, Card, Divider, RadioGroup
from tempest_core.style import Color, Edge, FontWeight
from tempest_core.widgets import ProgressBar


def _question_card(app: App[QuizState]) -> Widget:
    """Render the active question card with its RadioGroup and navigation button.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A :class:`Card` containing the question prompt, options and a Next/Finish
        button.
    """
    state: QuizState = app.state
    q_idx: int = state.current
    question: Question = QUESTIONS[q_idx]
    total: int = len(QUESTIONS)
    is_last: bool = q_idx == total - 1
    selected: int = state.answers.get(q_idx, -1)

    def select_option(index: int) -> None:
        """Record the chosen option for the current question.

        Args:
            index: The 0-based index of the selected option.
        """

        def mutate(s: QuizState) -> None:
            s.answers = {**s.answers, q_idx: index}

        app.set_state(mutate)

    def advance() -> None:
        """Move to the next question or finish the quiz."""
        if is_last:
            app.set_state(lambda s: setattr(s, "finished", True))
        else:
            app.set_state(lambda s: setattr(s, "current", s.current + 1))

    button_label: str = "Finish" if is_last else "Next"
    button_enabled: bool = selected >= 0

    return Card(
        key="question-card",
        children=[
            Text(
                content=f"Question {q_idx + 1} of {total}",
                key="q-counter",
                style=Style(font_size=13.0, color=Color.from_hex("#888888")),
            ),
            Text(
                content=question.prompt,
                key="q-prompt",
                style=Style(font_size=17.0, font_weight=FontWeight.BOLD),
            ),
            Divider(key="q-divider"),
            RadioGroup(
                key="q-options",
                options=question.options,
                selected=selected if selected >= 0 else 0,
                on_select=select_option,
            ),
            Button(
                key="q-advance",
                label=button_label,
                on_click=advance if button_enabled else (lambda: None),
                style=Style(
                    padding=Edge.symmetric(vertical=12.0, horizontal=24.0),
                    radius=10.0,
                    font_weight=FontWeight.BOLD,
                ),
            ),
        ],
    )
```

!!! info "Nota — botão desabilitado sem prop `disabled`"
    O botão "Next/Finish" usa `on_click=advance if button_enabled else (lambda: None)`. Enquanto nenhuma opção está selecionada, o clique não faz nada. Isso é o padrão tempestweb para simular um botão desativado: passar um handler vazio em vez de `None`.

!!! tip "Dica — `{**s.answers, q_idx: index}`"
    O handler `select_option` cria um **novo dicionário** em vez de mutar o existente: `s.answers = {**s.answers, q_idx: index}`. Essa imutabilidade de valor é boas práticas em `set_state` — garante que o reconciliador detecte a mudança corretamente e evita efeitos colaterais se o estado for inspecionado em outro lugar.

---

## Passo 5 — O resumo de respostas

Antes da tela de resultados, precisamos de um helper que gera uma linha por questão com ✓ (verde) ou ✗ (vermelho):

```python
def _answers_summary(state: QuizState) -> Widget:
    """Build a compact per-question answer summary.

    Args:
        state: The current quiz state.

    Returns:
        A :class:`Column` listing each question with a correct/wrong marker.
    """
    rows: list[Widget] = []
    for i, question in enumerate(QUESTIONS):
        chosen: int = state.answers.get(i, -1)
        is_correct: bool = chosen == question.correct
        marker: str = "✓" if is_correct else "✗"
        color: Color = Color.from_hex("#2e7d32" if is_correct else "#c62828")
        rows.append(
            Row(
                key=f"summary-row-{i}",
                style=Style(gap=8.0),
                children=[
                    Text(
                        content=marker,
                        key=f"summary-marker-{i}",
                        style=Style(
                            font_size=16.0,
                            color=color,
                            font_weight=FontWeight.BOLD,
                        ),
                    ),
                    Text(
                        content=(
                            question.prompt[:55]
                            + ("…" if len(question.prompt) > 55 else "")
                        ),
                        key=f"summary-prompt-{i}",
                        style=Style(font_size=13.0),
                    ),
                ],
            )
        )
    return Column(
        key="answers-summary",
        style=Style(gap=6.0),
        children=rows,
    )
```

!!! tip "Dica — truncar texto com Python puro"
    `question.prompt[:55] + ("…" if len(question.prompt) > 55 else "")` é a forma pythônica de limitar o comprimento do texto no lado do servidor — sem CSS `text-overflow` nem JS. O widget `Text` recebe a string já truncada.

---

## Passo 6 — A tela de resultados

Quando `state.finished` é `True`, a função `_results_screen` substitui o card de pergunta. Ela chama `_score`, `_grade_label` e `_answers_summary`:

```python
def _results_screen(app: App[QuizState]) -> Widget:
    """Render the final results screen.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A :class:`Column` showing the score, grade and a restart button.
    """
    state: QuizState = app.state
    total: int = len(QUESTIONS)
    score: int = _score(state.answers)
    grade: str = _grade_label(score, total)

    def restart() -> None:
        """Reset the quiz to its initial state."""

        def mutate(s: QuizState) -> None:
            s.current = 0
            s.answers = {}
            s.finished = False

        app.set_state(mutate)

    return Card(
        key="results-card",
        children=[
            Text(
                content="Quiz Complete!",
                key="results-title",
                style=Style(font_size=24.0, font_weight=FontWeight.BOLD),
            ),
            Text(
                content=f"{score} / {total} correct",
                key="results-score",
                style=Style(font_size=32.0, font_weight=FontWeight.BOLD),
            ),
            Text(
                content=grade,
                key="results-grade",
                style=Style(font_size=18.0),
            ),
            Divider(key="results-divider"),
            _answers_summary(state),
            Button(
                key="restart-btn",
                label="Restart Quiz",
                on_click=restart,
                style=Style(
                    padding=Edge.symmetric(vertical=12.0, horizontal=24.0),
                    radius=10.0,
                    font_weight=FontWeight.BOLD,
                ),
            ),
        ],
    )
```

---

## Passo 7 — A função `view` raiz

A função `view` é o ponto de entrada do tempestweb. Ela monta a estrutura de alto nível: `AppBar` + `ProgressBar` + corpo (card de pergunta **ou** tela de resultados):

```python
def view(app: App[QuizState]) -> Widget:
    """Render the entire quiz application from the current state.

    Switches between the active-question screen and the final results screen
    based on :attr:`QuizState.finished`. A :class:`ProgressBar` tracks progress
    at the top of the page regardless of which screen is active.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    state: QuizState = app.state
    total: int = len(QUESTIONS)
    progress: float = (
        1.0 if state.finished else (state.current / total if total > 0 else 0.0)
    )

    body: Widget = _results_screen(app) if state.finished else _question_card(app)

    return Column(
        key="quiz-root",
        style=Style(gap=0.0),
        children=[
            AppBar(
                key="quiz-appbar",
                title="Python & CS Quiz",
            ),
            ProgressBar(
                key="quiz-progress",
                value=progress,
            ),
            Column(
                key="quiz-body",
                style=Style(gap=16.0, padding=Edge.all(16.0)),
                children=[body],
            ),
        ],
    )
```

!!! info "Nota — `ProgressBar` e o cálculo de `progress`"
    `ProgressBar` espera um `float` entre `0.0` e `1.0`. O cálculo `state.current / total` dá a fração de perguntas **já passadas** (não a pergunta atual). Quando `state.finished` é `True`, o valor vai para `1.0` — barra cheia — independentemente de quantas questões foram respondidas.

---

## O app completo

Aqui está o arquivo completo, pronto para copiar:

```python
"""Quiz app — demonstrates Forms & flow with sequential questions and a final score.

A sequence of multiple-choice questions is presented one at a time. Each question
exposes its options as a :class:`~tempest_core.components.RadioGroup`; the user
picks an answer and presses **Next** (or **Finish** on the last question). A
:class:`~tempest_core.widgets.ProgressBar` tracks progress through the quiz.
After the final question a results screen shows the score, a grade label, and a
**Restart** button to play again.

This runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

The application never names a transport.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.components import AppBar, Card, Divider, RadioGroup
from tempest_core.style import Color, Edge, FontWeight
from tempest_core.widgets import ProgressBar

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Question:
    """A single quiz question with answer options and the correct answer index.

    Attributes:
        prompt: The question text shown to the user.
        options: The list of answer labels in display order.
        correct: The 0-based index of the correct option.
    """

    prompt: str
    options: list[str]
    correct: int


#: The ordered list of questions used by the quiz.  Defined as a module-level
#: constant so the dataclass stays a plain Python object without embedding
#: question data inside the state.
QUESTIONS: list[Question] = [
    Question(
        prompt="Which data structure gives O(1) average-case lookup by key?",
        options=["Linked list", "Hash map", "Binary search tree", "Sorted array"],
        correct=1,
    ),
    Question(
        prompt="What is the time complexity of quicksort in the average case?",
        options=["O(n)", "O(n²)", "O(n log n)", "O(log n)"],
        correct=2,
    ),
    Question(
        prompt="Which HTTP method is idempotent and safe (read-only)?",
        options=["POST", "PUT", "DELETE", "GET"],
        correct=3,
    ),
    Question(
        prompt="In Python, which keyword is used to declare an async function?",
        options=["await", "async", "yield", "defer"],
        correct=1,
    ),
    Question(
        prompt="Which SQL clause filters groups produced by GROUP BY?",
        options=["WHERE", "HAVING", "FILTER", "LIMIT"],
        correct=1,
    ),
]


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class QuizState:
    """All runtime state for the quiz application.

    Attributes:
        current: The index of the question currently displayed.
        answers: A mapping of question index to the chosen option index.
        finished: Whether the user has completed all questions.
    """

    current: int = 0
    answers: dict[int, int] = field(default_factory=dict)
    finished: bool = False


def make_state() -> QuizState:
    """Build the initial quiz state — first question, no answers yet.

    Returns:
        A fresh :class:`QuizState` ready to start the quiz.
    """
    return QuizState()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _score(answers: dict[int, int]) -> int:
    """Count the number of correct answers.

    Args:
        answers: A mapping of question index to the chosen option index.

    Returns:
        The number of questions answered correctly.
    """
    return sum(
        1
        for q_idx, chosen in answers.items()
        if 0 <= q_idx < len(QUESTIONS) and QUESTIONS[q_idx].correct == chosen
    )


def _grade_label(score: int, total: int) -> str:
    """Derive a human-readable grade label from the score fraction.

    Args:
        score: The number of correct answers.
        total: The total number of questions.

    Returns:
        A grade string such as ``"Excellent"`` or ``"Needs practice"``.
    """
    if total == 0:
        return "No questions"
    fraction: float = score / total
    if fraction >= 0.9:
        return "Excellent!"
    if fraction >= 0.7:
        return "Good job!"
    if fraction >= 0.5:
        return "Keep it up!"
    return "Needs practice"


# ---------------------------------------------------------------------------
# View helpers
# ---------------------------------------------------------------------------


def _question_card(app: App[QuizState]) -> Widget:
    """Render the active question card with its RadioGroup and navigation button.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A :class:`Card` containing the question prompt, options and a Next/Finish
        button.
    """
    state: QuizState = app.state
    q_idx: int = state.current
    question: Question = QUESTIONS[q_idx]
    total: int = len(QUESTIONS)
    is_last: bool = q_idx == total - 1
    selected: int = state.answers.get(q_idx, -1)

    def select_option(index: int) -> None:
        """Record the chosen option for the current question.

        Args:
            index: The 0-based index of the selected option.
        """

        def mutate(s: QuizState) -> None:
            s.answers = {**s.answers, q_idx: index}

        app.set_state(mutate)

    def advance() -> None:
        """Move to the next question or finish the quiz."""
        if is_last:
            app.set_state(lambda s: setattr(s, "finished", True))
        else:
            app.set_state(lambda s: setattr(s, "current", s.current + 1))

    button_label: str = "Finish" if is_last else "Next"
    button_enabled: bool = selected >= 0

    return Card(
        key="question-card",
        children=[
            Text(
                content=f"Question {q_idx + 1} of {total}",
                key="q-counter",
                style=Style(font_size=13.0, color=Color.from_hex("#888888")),
            ),
            Text(
                content=question.prompt,
                key="q-prompt",
                style=Style(font_size=17.0, font_weight=FontWeight.BOLD),
            ),
            Divider(key="q-divider"),
            RadioGroup(
                key="q-options",
                options=question.options,
                selected=selected if selected >= 0 else 0,
                on_select=select_option,
            ),
            Button(
                key="q-advance",
                label=button_label,
                on_click=advance if button_enabled else (lambda: None),
                style=Style(
                    padding=Edge.symmetric(vertical=12.0, horizontal=24.0),
                    radius=10.0,
                    font_weight=FontWeight.BOLD,
                ),
            ),
        ],
    )


def _results_screen(app: App[QuizState]) -> Widget:
    """Render the final results screen.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        A :class:`Column` showing the score, grade and a restart button.
    """
    state: QuizState = app.state
    total: int = len(QUESTIONS)
    score: int = _score(state.answers)
    grade: str = _grade_label(score, total)

    def restart() -> None:
        """Reset the quiz to its initial state."""

        def mutate(s: QuizState) -> None:
            s.current = 0
            s.answers = {}
            s.finished = False

        app.set_state(mutate)

    return Card(
        key="results-card",
        children=[
            Text(
                content="Quiz Complete!",
                key="results-title",
                style=Style(font_size=24.0, font_weight=FontWeight.BOLD),
            ),
            Text(
                content=f"{score} / {total} correct",
                key="results-score",
                style=Style(font_size=32.0, font_weight=FontWeight.BOLD),
            ),
            Text(
                content=grade,
                key="results-grade",
                style=Style(font_size=18.0),
            ),
            Divider(key="results-divider"),
            _answers_summary(state),
            Button(
                key="restart-btn",
                label="Restart Quiz",
                on_click=restart,
                style=Style(
                    padding=Edge.symmetric(vertical=12.0, horizontal=24.0),
                    radius=10.0,
                    font_weight=FontWeight.BOLD,
                ),
            ),
        ],
    )


def _answers_summary(state: QuizState) -> Widget:
    """Build a compact per-question answer summary.

    Args:
        state: The current quiz state.

    Returns:
        A :class:`Column` listing each question with a correct/wrong marker.
    """
    rows: list[Widget] = []
    for i, question in enumerate(QUESTIONS):
        chosen: int = state.answers.get(i, -1)
        is_correct: bool = chosen == question.correct
        marker: str = "✓" if is_correct else "✗"
        color: Color = Color.from_hex("#2e7d32" if is_correct else "#c62828")
        rows.append(
            Row(
                key=f"summary-row-{i}",
                style=Style(gap=8.0),
                children=[
                    Text(
                        content=marker,
                        key=f"summary-marker-{i}",
                        style=Style(
                            font_size=16.0,
                            color=color,
                            font_weight=FontWeight.BOLD,
                        ),
                    ),
                    Text(
                        content=(
                            question.prompt[:55]
                            + ("…" if len(question.prompt) > 55 else "")
                        ),
                        key=f"summary-prompt-{i}",
                        style=Style(font_size=13.0),
                    ),
                ],
            )
        )
    return Column(
        key="answers-summary",
        style=Style(gap=6.0),
        children=rows,
    )


# ---------------------------------------------------------------------------
# Root view
# ---------------------------------------------------------------------------


def view(app: App[QuizState]) -> Widget:
    """Render the entire quiz application from the current state.

    Switches between the active-question screen and the final results screen
    based on :attr:`QuizState.finished`. A :class:`ProgressBar` tracks progress
    at the top of the page regardless of which screen is active.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    state: QuizState = app.state
    total: int = len(QUESTIONS)
    progress: float = (
        1.0 if state.finished else (state.current / total if total > 0 else 0.0)
    )

    body: Widget = _results_screen(app) if state.finished else _question_card(app)

    return Column(
        key="quiz-root",
        style=Style(gap=0.0),
        children=[
            AppBar(
                key="quiz-appbar",
                title="Python & CS Quiz",
            ),
            ProgressBar(
                key="quiz-progress",
                value=progress,
            ),
            Column(
                key="quiz-body",
                style=Style(gap=16.0, padding=Edge.all(16.0)),
                children=[body],
            ),
        ],
    )
```

---

## Rodando o exemplo ▶

### Modo A — Python no browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm --path examples/quiz-app
```

O Python roda **dentro do browser** via Pyodide. Nenhum servidor necessário.

### Modo B — Python no servidor (FastAPI + WebSocket)

```bash
tempestweb dev --mode server --path examples/quiz-app
```

O Python roda no servidor; o browser recebe patches JSON pelo WebSocket e aplica ao DOM.

!!! check "Verificação"
    Em qualquer modo, você deve ver:

    1. `AppBar` com título **"Python & CS Quiz"**
    2. `ProgressBar` vazia (`0 %`) logo abaixo da barra
    3. Card com **Pergunta 1 de 5** e quatro opções no `RadioGroup`
    4. Botão **Next** presente, mas inativo (clique não avança)
    5. Selecione uma opção → botão **Next** passa a funcionar
    6. Clique **Next** → pergunta 2 aparece, `ProgressBar` avança para 20 %
    7. Na pergunta 5 o botão mostra **Finish**
    8. Clique **Finish** → tela de resultados com pontuação, nota e resumo ✓/✗
    9. Clique **Restart Quiz** → quiz volta à pergunta 1 zerado

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

# Testes
pytest -q
```

Todos devem passar em verde. O exemplo foi projetado para ser `mypy --strict` clean — toda variável, parâmetro e retorno está anotado explicitamente.

---

## Como funciona por dentro

### O ciclo de atualização

```
Usuário clica em uma opção do RadioGroup
      │
      ▼
on_select(index) é chamado
      │
      ▼
select_option(index) chama app.set_state(mutate)
      │
      ▼
tempestweb aplica o mutador → answers atualizado
      │
      ▼
view(app) é chamado novamente → nova árvore de widgets
      │
      ▼
reconciliador calcula diff (patches mínimos)
      │
      ▼
DOM atualizado — apenas o RadioGroup e o botão mudam
```

### Troca de tela sem rotas

A lógica de troca entre card de pergunta e tela de resultados está em uma única linha dentro de `view`:

```python
body: Widget = _results_screen(app) if state.finished else _question_card(app)
```

Quando `state.finished` muda de `False` para `True`, o reconciliador remove toda a subárvore do card de pergunta e insere a da tela de resultados. Não há roteamento, não há URL — apenas estado Python.

### Widgets usados neste exemplo

| Widget | Papel |
|---|---|
| `AppBar` | Barra superior com título |
| `ProgressBar` | Indicador visual de avanço (0.0–1.0) |
| `Card` | Container visual com sombra/borda |
| `Divider` | Separador horizontal visual |
| `RadioGroup` | Grupo de opções mutuamente exclusivas |
| `Column` | Layout vertical |
| `Row` | Layout horizontal |
| `Text` | Rótulo de texto |
| `Button` | Botão com handler de clique |

---

## Recapitulando

Neste tutorial você aprendeu:

- ✅ Separar **dados estáticos** (`frozen=True`) de **estado dinâmico** (`@dataclass`)
- ✅ Usar `RadioGroup` para seleção exclusiva e tratar o índice escolhido em `set_state`
- ✅ Implementar **navegação por estado** (`finished: bool`) sem rotas nem URLs
- ✅ Calcular `ProgressBar` como uma fração derivada do estado atual
- ✅ Desabilitar botões passando um handler vazio `lambda: None` em vez de `None`
- ✅ Construir um resumo de respostas por questão com marcadores coloridos ✓/✗
- ✅ Escrever funções auxiliares puras e testáveis fora de `view()`

---

## Próximos passos

Experimente estender o exemplo:

- 💡 Adicione um **timer por pergunta** — guarde `time_limit: int` no estado e use um tick periódico para avançar automaticamente (veja [Stopwatch](./stopwatch.md) para o padrão de timer)
- 💡 Adicione **embaralhamento de perguntas** — em `make_state`, sorteie a ordem e guarde-a no estado
- 💡 Explore o exemplo [Signup Wizard](./signup-wizard.md) para um fluxo multi-passo com validação por etapa
- 💡 Veja o [Settings Panel](./settings-panel.md) para outros exemplos de `RadioGroup` em contexto de preferências
