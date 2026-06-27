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
