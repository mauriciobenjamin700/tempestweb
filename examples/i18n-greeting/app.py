"""Internationalized greeting — demonstrates :mod:`tempestweb._core.i18n`.

This example is a non-trivial showcase of the i18n helpers:

* :class:`~tempestweb._core.i18n.Locale` — language, region, RTL flag.
* :func:`~tempestweb._core.i18n.translate` (alias :data:`~tempestweb._core.i18n.t`)
  — key look-up with ``str.format`` interpolation.

The user can:

1. Pick a language via a :class:`~tempestweb._core.components.SegmentedControl`
   (English, Português, العربية).
2. Type their name into an :class:`~tempestweb._core.widgets.Input`; the greeting
   headline interpolates it in real time.
3. See a "fun fact" card whose text also re-renders through ``t()``.

Both mode A (WASM/Pyodide) and mode B (server + WebSocket) run this exact
``view`` unchanged — the app never names a transport.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempestweb._core import App, Locale, Style, Widget, t
from tempestweb._core.components import Card, Divider, SegmentedControl
from tempestweb._core.style import Edge, FontWeight, TextAlign
from tempestweb._core.widgets import Column, Input, Text
from tempestweb._core.widgets.events import TextChangeEvent

# ---------------------------------------------------------------------------
# Translation catalogue
# ---------------------------------------------------------------------------

#: All localised strings keyed by BCP-47 language tag then message key.
TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "app_title": "Internationalized Greeting",
        "pick_language": "Language",
        "name_label": "Your name",
        "name_placeholder": "Type your name…",
        "greeting": "Hello, {name}!",
        "greeting_anonymous": "Hello, stranger!",
        "fun_fact_title": "Did you know?",
        "fun_fact": (
            "The word 'hello' as a phone greeting was popularised by "
            "Thomas Edison in 1877. Before that, 'ahoy' was preferred."
        ),
        "locale_info": "Active locale: {tag} — direction: {direction}",
        "ltr": "left-to-right",
        "rtl": "right-to-left",
    },
    "pt": {
        "app_title": "Saudação Internacionalizada",
        "pick_language": "Idioma",
        "name_label": "Seu nome",
        "name_placeholder": "Digite seu nome…",
        "greeting": "Olá, {name}!",
        "greeting_anonymous": "Olá, desconhecido(a)!",
        "fun_fact_title": "Você sabia?",
        "fun_fact": (
            "A palavra olá é considerada um abrasileiramento de halloa, "
            "exclamação náutica inglesa usada para chamar barcos ao longe."
        ),
        "locale_info": "Localidade ativa: {tag} — direção: {direction}",
        "ltr": "esquerda para direita",
        "rtl": "direita para esquerda",
    },
    "ar": {
        "app_title": "تحية دولية",
        "pick_language": "اللغة",
        "name_label": "اسمك",
        "name_placeholder": "اكتب اسمك…",
        "greeting": "مرحباً، {name}!",
        "greeting_anonymous": "مرحباً أيها الغريب!",
        "fun_fact_title": "هل تعلم؟",
        "fun_fact": (
            "كلمة مرحباً مشتقة من الرحب بمعنى الاتساع، "
            "وكأنك تقول للضيف: أهلاً في رحابة هذا المكان."
        ),
        "locale_info": "اللغة النشطة: {tag} — الاتجاه: {direction}",
        "ltr": "من اليسار إلى اليمين",
        "rtl": "من اليمين إلى اليسار",
    },
}

# ---------------------------------------------------------------------------
# Available locales (parallel lists — index is the shared key)
# ---------------------------------------------------------------------------

LOCALE_LABELS: list[str] = ["English", "Português", "العربية"]
LOCALES: list[Locale] = [
    Locale(language="en", region="US", rtl=False),
    Locale(language="pt", region="BR", rtl=False),
    Locale(language="ar", region="SA", rtl=True),
]

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class GreetingState:
    """State for the internationalized greeting app.

    Attributes:
        locale_index: Index into :data:`LOCALES` / :data:`LOCALE_LABELS`.
        name: The visitor's name as typed into the input field.
    """

    locale_index: int = 0
    name: str = field(default="")


def make_state() -> GreetingState:
    """Build the initial state — English locale, empty name.

    Returns:
        A fresh :class:`GreetingState`.
    """
    return GreetingState()


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[GreetingState]) -> Widget:
    """Render the greeting UI from the current state.

    Reads the active :class:`~tempestweb._core.i18n.Locale` from ``app.state``
    and translates every visible string via
    :func:`~tempestweb._core.i18n.translate` so that switching the language
    selector re-renders the entire tree in the new locale without any
    conditional logic scattered through the widget tree.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    locale: Locale = LOCALES[app.state.locale_index]

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def on_locale_selected(index: int) -> None:
        """Switch the active locale.

        Args:
            index: Zero-based index of the chosen segment in
                :data:`LOCALE_LABELS`.
        """
        app.set_state(lambda s: setattr(s, "locale_index", index))

    def on_name_change(event: TextChangeEvent) -> None:
        """Update the visitor name from the input field.

        Args:
            event: The text-change event carrying the new value.
        """
        app.set_state(lambda s: setattr(s, "name", event.value))

    # ------------------------------------------------------------------
    # Derived strings — all go through translate()
    # ------------------------------------------------------------------

    greeting: str = (
        t("greeting", locale, TRANSLATIONS, name=app.state.name)
        if app.state.name.strip()
        else t("greeting_anonymous", locale, TRANSLATIONS)
    )
    direction_key: str = "rtl" if locale.rtl else "ltr"
    locale_info: str = t(
        "locale_info",
        locale,
        TRANSLATIONS,
        tag=locale.tag,
        direction=t(direction_key, locale, TRANSLATIONS),
    )

    # ------------------------------------------------------------------
    # Layout — text-align mirrors the locale direction
    # ------------------------------------------------------------------

    text_align: TextAlign = TextAlign.RIGHT if locale.rtl else TextAlign.LEFT

    return Column(
        key="root",
        style=Style(gap=20.0, padding=Edge.all(24.0)),
        children=[
            # Title
            Text(
                key="title",
                content=t("app_title", locale, TRANSLATIONS),
                style=Style(
                    font_size=22.0,
                    font_weight=FontWeight.BOLD,
                    text_align=TextAlign.CENTER,
                ),
            ),
            Divider(key="title-div"),
            # Language picker
            Column(
                key="lang-col",
                style=Style(gap=8.0),
                children=[
                    Text(
                        key="lang-label",
                        content=t("pick_language", locale, TRANSLATIONS),
                        style=Style(font_size=14.0, font_weight=FontWeight.BOLD),
                    ),
                    SegmentedControl(
                        key="lang-picker",
                        options=LOCALE_LABELS,
                        selected=app.state.locale_index,
                        on_select=on_locale_selected,
                    ),
                ],
            ),
            # Name input
            Column(
                key="name-col",
                style=Style(gap=8.0),
                children=[
                    Text(
                        key="name-label",
                        content=t("name_label", locale, TRANSLATIONS),
                        style=Style(font_size=14.0, font_weight=FontWeight.BOLD),
                    ),
                    Input(
                        key="name-input",
                        value=app.state.name,
                        placeholder=t("name_placeholder", locale, TRANSLATIONS),
                        on_change=on_name_change,
                    ),
                ],
            ),
            # Greeting headline
            Text(
                key="greeting",
                content=greeting,
                style=Style(
                    font_size=28.0,
                    font_weight=FontWeight.BOLD,
                    text_align=text_align,
                ),
            ),
            # Fun-fact card
            Card(
                key="fun-fact-card",
                children=[
                    Text(
                        key="fact-title",
                        content=t("fun_fact_title", locale, TRANSLATIONS),
                        style=Style(
                            font_size=15.0,
                            font_weight=FontWeight.BOLD,
                            text_align=text_align,
                        ),
                    ),
                    Text(
                        key="fact-body",
                        content=t("fun_fact", locale, TRANSLATIONS),
                        style=Style(font_size=14.0, text_align=text_align),
                    ),
                ],
            ),
            # Active-locale metadata
            Text(
                key="locale-info",
                content=locale_info,
                style=Style(font_size=12.0, text_align=TextAlign.CENTER),
            ),
        ],
    )
