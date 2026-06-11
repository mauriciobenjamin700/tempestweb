# Quiz with Score — Forms & Navigation Flow 🚀

Build a 5-question multiple-choice quiz with sequential navigation, `RadioGroup` answer selection, a progress bar, and a scored results screen — all in **pure Python, with no JavaScript and no transport named**.

---

## What you'll build

A complete, functional quiz featuring:

- 📋 5 computer-science questions presented **one at a time**
- 🔘 Answer selection via **`RadioGroup`** (no text fields, just clicks)
- 📊 **`ProgressBar`** showing how far through the quiz you are
- ➡ **Next** button that only activates once an answer is selected
- ✅ **Finish** button on the last question to complete the quiz
- 🏆 Results screen showing **score**, **grade label**, and a per-question summary (✓ / ✗)
- 🔄 **Restart Quiz** button to play again from the beginning

!!! note "Note — screen switching vs. routing"
    This example uses a single boolean state field (`finished`) to toggle between the question card and the results screen. There are no routes, no URLs — tempestweb reconstructs the widget tree on every state change. For navigation with browser history and URLs see the [Tabs - Profile](./tabs-profile.en.md) example.

---

## Prerequisites

Make sure tempestweb is installed:

```bash
pip install tempestweb
```

Recommended reading (optional):

- [Basic tutorial](../tutorial/index.md) — first steps with `App`, `view`, and `set_state`
- [Managing state](../tutorial/state.md) — how `set_state` works
- [Execution modes](../tutorial/modes.md) — WASM vs. server
- [Login form](./login-form.en.md) — another example with forms and validation

---

## Creating the project

```bash
mkdir -p examples/quiz-app
touch examples/quiz-app/app.py
```

---

## Step 1 — Modelling the data

Before thinking about the UI, think about the data. The quiz has two distinct kinds:

1. **Static data** — the questions and correct answers (never change at runtime)
2. **Dynamic state** — the user's progress (changes on every interaction)

Keep them separate. For static data, use an immutable (`frozen=True`) dataclass and a module-level constant:

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

!!! tip "Tip — `frozen=True`"
    `frozen=True` makes the dataclass **immutable**: any attempt to assign to a field raises `FrozenInstanceError`. This is the Pythonic way to declare that `Question` is configuration data, not mutable state. tempestweb will never try to patch it.

---

## Step 2 — Defining the state

The state only needs to hold the **minimum necessary** to reconstruct any screen:

| Field | Type | Meaning |
|---|---|---|
| `current` | `int` | Index of the question currently on screen |
| `answers` | `dict[int, int]` | Map of question index → chosen option index |
| `finished` | `bool` | Has the user completed the quiz? |

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

!!! tip "Tip — `field(default_factory=dict)`"
    Just like with lists, **never** write `answers: dict[int, int] = {}` in a dataclass. Python would share the same dictionary across all instances. `field(default_factory=dict)` guarantees a fresh dict for every instance.

---

## Step 3 — Pure helper functions

Two pure functions compute the score and grade label. They live **outside** `view()` — easy to test in isolation:

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

| Fraction correct | Label |
|---|---|
| ≥ 90 % | `"Excellent!"` |
| ≥ 70 % | `"Good job!"` |
| ≥ 50 % | `"Keep it up!"` |
| < 50 % | `"Needs practice"` |

---

## Step 4 — The question card

Now the UI. The question card is the richest part: it contains the `RadioGroup` and the navigation button.

The button-enabling logic is worth noting:

- `selected = state.answers.get(q_idx, -1)` — `-1` means "no answer yet"
- `button_enabled = selected >= 0` — the button only reacts to clicks after a selection is made

```python
from tempestweb._core import App, Button, Column, Row, Style, Text, Widget
from tempestweb._core.components import AppBar, Card, Divider, RadioGroup
from tempestweb._core.style import Color, Edge, FontWeight
from tempestweb._core.widgets import ProgressBar


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

!!! info "Note — disabling a button without a `disabled` prop"
    The Next/Finish button uses `on_click=advance if button_enabled else (lambda: None)`. While no option is selected, a click does nothing. This is the tempestweb pattern for a disabled button: pass an empty handler instead of `None`.

!!! tip "Tip — `{**s.answers, q_idx: index}`"
    The `select_option` handler creates a **new dictionary** rather than mutating the existing one: `s.answers = {**s.answers, q_idx: index}`. This immutable-value style in `set_state` ensures the reconciler detects the change correctly and avoids side effects if the state is inspected elsewhere.

---

## Step 5 — The answer summary

Before the results screen, we need a helper that generates one row per question with ✓ (green) or ✗ (red):

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

!!! tip "Tip — truncating text in pure Python"
    `question.prompt[:55] + ("…" if len(question.prompt) > 55 else "")` is the Pythonic way to cap text length server-side — no CSS `text-overflow`, no JS. The `Text` widget receives the already-truncated string.

---

## Step 6 — The results screen

When `state.finished` is `True`, `_results_screen` replaces the question card. It calls `_score`, `_grade_label`, and `_answers_summary`:

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

## Step 7 — The root `view` function

The `view` function is tempestweb's entry point. It assembles the top-level structure: `AppBar` + `ProgressBar` + body (question card **or** results screen):

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

!!! info "Note — `ProgressBar` and the `progress` calculation"
    `ProgressBar` expects a `float` between `0.0` and `1.0`. The formula `state.current / total` gives the fraction of questions **already passed** (not the current question). When `state.finished` is `True`, the value jumps to `1.0` — full bar — regardless of how many questions were answered.

---

## The complete app

Here is the full file, ready to copy:

```python
"""Quiz app — demonstrates Forms & flow with sequential questions and a final score.

A sequence of multiple-choice questions is presented one at a time. Each question
exposes its options as a :class:`~tempestweb._core.components.RadioGroup`; the user
picks an answer and presses **Next** (or **Finish** on the last question). A
:class:`~tempestweb._core.widgets.ProgressBar` tracks progress through the quiz.
After the final question a results screen shows the score, a grade label, and a
**Restart** button to play again.

This runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

The application never names a transport.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempestweb._core import App, Button, Column, Row, Style, Text, Widget
from tempestweb._core.components import AppBar, Card, Divider, RadioGroup
from tempestweb._core.style import Color, Edge, FontWeight
from tempestweb._core.widgets import ProgressBar

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

## Running the example ▶

### Mode A — Python in the browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm examples/quiz-app/app.py
```

Python runs **inside the browser** via Pyodide. No server required.

### Mode B — Python on the server (FastAPI + WebSocket)

```bash
tempestweb dev --mode server examples/quiz-app/app.py
```

Python runs on the server; the browser receives JSON patches over WebSocket and applies them to the DOM.

!!! check "Verification"
    In either mode, you should see:

    1. `AppBar` with title **"Python & CS Quiz"**
    2. Empty `ProgressBar` (0 %) just below the bar
    3. Card showing **Question 1 of 5** and four options in the `RadioGroup`
    4. **Next** button present but inactive (clicking does not advance)
    5. Select an option → **Next** button becomes functional
    6. Click **Next** → question 2 appears, `ProgressBar` advances to 20 %
    7. On question 5 the button reads **Finish**
    8. Click **Finish** → results screen shows score, grade label and ✓/✗ summary
    9. Click **Restart Quiz** → quiz resets to question 1, all answers cleared

---

## Automated verification ✅

Run all four checks before committing:

```bash
# Lint
ruff check .

# Formatting
ruff format --check .

# Types
mypy --strict tempestweb

# Tests
pytest -q
```

All should pass green. The example was designed to be `mypy --strict` clean — every variable, parameter, and return type is explicitly annotated.

---

## How it works under the hood

### The update cycle

```
User clicks a RadioGroup option
      │
      ▼
on_select(index) is called
      │
      ▼
select_option(index) calls app.set_state(mutate)
      │
      ▼
tempestweb applies the mutator → answers updated
      │
      ▼
view(app) is called again → new widget tree
      │
      ▼
reconciler computes diff (minimal patches)
      │
      ▼
DOM updated — only the RadioGroup and button change
```

### Screen switching without routes

The logic that swaps between the question card and the results screen is a single line inside `view`:

```python
body: Widget = _results_screen(app) if state.finished else _question_card(app)
```

When `state.finished` flips from `False` to `True`, the reconciler removes the entire question-card subtree and inserts the results-screen subtree. No routing, no URLs — just Python state.

### Widgets used in this example

| Widget | Role |
|---|---|
| `AppBar` | Top bar with title |
| `ProgressBar` | Visual progress indicator (0.0–1.0) |
| `Card` | Visual container with shadow/border |
| `Divider` | Horizontal visual separator |
| `RadioGroup` | Mutually exclusive option group |
| `Column` | Vertical layout |
| `Row` | Horizontal layout |
| `Text` | Text label |
| `Button` | Button with click handler |

---

## Recap

In this tutorial you learned:

- ✅ Separate **static data** (`frozen=True`) from **dynamic state** (`@dataclass`)
- ✅ Use `RadioGroup` for exclusive selection and handle the chosen index in `set_state`
- ✅ Implement **state-based navigation** (`finished: bool`) without routes or URLs
- ✅ Compute `ProgressBar` as a fraction derived from the current state
- ✅ Disable buttons by passing an empty handler `lambda: None` instead of `None`
- ✅ Build a per-question answer summary with coloured ✓/✗ markers
- ✅ Write pure, testable helper functions outside of `view()`

---

## Next steps

Try extending the example:

- 💡 Add a **per-question timer** — store `time_limit: int` in the state and use a periodic tick to auto-advance (see [Stopwatch](./stopwatch.en.md) for the timer pattern)
- 💡 Add **question shuffling** — in `make_state`, randomise the order and store it in the state
- 💡 Explore the [Signup Wizard](./signup-wizard.en.md) example for a multi-step flow with per-step validation
- 💡 See the [Settings Panel](./settings-panel.md) for more `RadioGroup` usage in a preferences context
