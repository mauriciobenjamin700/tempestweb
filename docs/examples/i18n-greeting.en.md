# Internationalized Greeting — i18n with Locale and t() 🌍

Build a multilingual greeting app that switches between English, Portuguese, and Arabic (RTL) in real time — and learn how to use `Locale`, `translate()`, and variable interpolation in tempestweb.

---

## What you'll build

An app that showcases tempestweb's i18n system with:

- 🌐 **Language selector** via `SegmentedControl` (English / Português / العربية)
- ✏️ **Name field** with a localised placeholder; the greeting updates letter by letter
- 👋 **Greeting headline** in a large font — interpolates `{name}` in real time via `t()`
- 🃏 **Fun-fact card** with a fully translated title and body
- ↔️ **Dynamic alignment** — texts automatically align right for Arabic (RTL)
- ℹ️ **Metadata line** showing the BCP-47 tag and direction of the active locale

!!! note "Note — one `view`, three languages"
    The app has no conditional logic of the form `if locale == "ar": ...`. Every visible string passes through `t()`, which uses the active locale to look up the catalogue. Switching the language triggers a full re-render, but the `view` code never needs to know which language is active.

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

---

## Creating the project

Create the folder and app file:

```bash
mkdir -p examples/i18n-greeting
touch examples/i18n-greeting/app.py
```

---

## Step 1 — The translation catalogue

Before the UI, we define all the localised strings. The catalogue is a plain dictionary, indexed first by the BCP-47 language tag and then by the message key:

```python
from __future__ import annotations

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
```

!!! tip "Tip — string keys as a contract"
    Keep the **key names** identical across every language (`"greeting"`, `"fun_fact"`, etc.). These are what `t()` looks up — if a key is missing from any language, you'll get an immediate `KeyError` on the first render in that locale, making the omission easy to spot.

---

## Step 2 — Defining the locales

Each language is represented by a `Locale` object carrying the language code, region, and RTL flag:

```python
from tempest_core import Locale

LOCALE_LABELS: list[str] = ["English", "Português", "العربية"]
LOCALES: list[Locale] = [
    Locale(language="en", region="US", rtl=False),
    Locale(language="pt", region="BR", rtl=False),
    Locale(language="ar", region="SA", rtl=True),
]
```

!!! info "Note — `Locale.tag`"
    `Locale` exposes a `.tag` property that returns the full BCP-47 tag (`"en-US"`, `"pt-BR"`, `"ar-SA"`). The `TRANSLATIONS` catalogue uses only the language code (`"en"`, `"pt"`, `"ar"`) as its top-level key — `t()` extracts `locale.language` internally when doing the lookup.

---

## Step 3 — Defining the state

The app's state is minimal: just the index of the selected locale and the name the user has typed.

```python
from dataclasses import dataclass, field


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
```

!!! tip "Tip — index vs. object"
    Storing `locale_index: int` instead of the full `Locale` object keeps the state trivially serializable (an integer is JSON-safe by default). The `Locale` object is derived inside `view()` with `LOCALES[app.state.locale_index]`.

---

## Step 4 — Event handlers

Inside `view()`, two handlers respond to user interactions:

```python
from tempest_core import App, Widget
from tempest_core.widgets.events import TextChangeEvent


def view(app: App[GreetingState]) -> Widget:
    """Render the greeting UI from the current state."""
    locale: Locale = LOCALES[app.state.locale_index]

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
```

Notice that the handlers are defined **inside** `view()`. They capture `app` by closure — the idiomatic tempestweb pattern for keeping `view` pure (no mutable globals).

---

## Step 5 — Deriving strings with `t()`

With the locale and handlers in place, we compute the derived strings before building the widget tree:

```python
from tempest_core import t


def view(app: App[GreetingState]) -> Widget:
    locale: Locale = LOCALES[app.state.locale_index]

    # ... (handlers — see Step 4)

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
```

The full signature of `t()` is:

```
t(key, locale, catalogue, **kwargs) -> str
```

The `**kwargs` are passed directly to `str.format_map()`. This means `"Hello, {name}!"` + `name="Alice"` → `"Hello, Alice!"` — no template engine, just plain Python.

!!! tip "Tip — `t()` inside `t()`"
    Notice that `locale_info` uses `t(direction_key, ...)` **inside** the call to `t("locale_info", ...)`. This is perfectly valid — the result of the inner `t()` is just a plain Python string, which is then passed as `direction=` to the outer one. This composition lets you have fully localised text, including the variable parts.

---

## Step 6 — Building the widget tree

Now we assemble the UI. Text alignment mirrors the locale direction:

```python
from tempest_core import Style
from tempest_core.components import Card, Divider, SegmentedControl
from tempest_core.style import Edge, FontWeight, TextAlign
from tempest_core.widgets import Column, Input, Text


def view(app: App[GreetingState]) -> Widget:
    locale: Locale = LOCALES[app.state.locale_index]

    # ... (handlers and derived strings — see Steps 4 and 5)

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
```

!!! tip "Tip — `text_align` derived from `locale.rtl`"
    `text_align: TextAlign = TextAlign.RIGHT if locale.rtl else TextAlign.LEFT` is computed once and reused in every widget that needs to respect the reading direction. No conditional logic scattered through the tree — just pass `text_align` wherever needed.

---

## The complete app

Here is the full file, ready to copy:

```python
"""Internationalized greeting — demonstrates :mod:`tempest_core.i18n`.

This example is a non-trivial showcase of the i18n helpers:

* :class:`~tempest_core.i18n.Locale` — language, region, RTL flag.
* :func:`~tempest_core.i18n.translate` (alias :data:`~tempest_core.i18n.t`)
  — key look-up with ``str.format`` interpolation.

The user can:

1. Pick a language via a :class:`~tempest_core.components.SegmentedControl`
   (English, Português, العربية).
2. Type their name into an :class:`~tempest_core.widgets.Input`; the greeting
   headline interpolates it in real time.
3. See a "fun fact" card whose text also re-renders through ``t()``.

Both mode A (WASM/Pyodide) and mode B (server + WebSocket) run this exact
``view`` unchanged — the app never names a transport.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Locale, Style, Widget, t
from tempest_core.components import Card, Divider, SegmentedControl
from tempest_core.style import Edge, FontWeight, TextAlign
from tempest_core.widgets import Column, Input, Text
from tempest_core.widgets.events import TextChangeEvent

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

    Reads the active :class:`~tempest_core.i18n.Locale` from ``app.state``
    and translates every visible string via
    :func:`~tempest_core.i18n.translate` so that switching the language
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
```

---

## Running the example ▶

### Mode A — Python in the browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm examples/i18n-greeting/app.py
```

Python runs **inside the browser** via Pyodide. No server required.

### Mode B — Python on the server (FastAPI + WebSocket)

```bash
tempestweb dev --mode server examples/i18n-greeting/app.py
```

Python runs on the server; the browser receives JSON patches over WebSocket and applies them to the DOM.

!!! check "Verification"
    In either mode you should see:

    1. Centred title in English: **"Internationalized Greeting"**
    2. `SegmentedControl` with three options: **English / Português / العربية**
    3. Text field with placeholder **"Type your name…"**
    4. Large greeting: **"Hello, stranger!"** (while the name field is empty)
    5. Click **Português** → the entire UI re-renders in PT-BR instantly
    6. Type a name → the greeting interpolates in real time: **"Olá, Alice!"**
    7. Click **العربية** → texts align right, greeting appears in Arabic
    8. The bottom line shows `ar-SA` and the direction in the active language

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

All should pass green. The example was specifically designed to be `mypy --strict` clean — every variable and return type is explicitly annotated.

---

## How it works under the hood

### The update cycle when switching language

```
Click "Português" in the SegmentedControl
      │
      ▼
on_locale_selected(index=1)
      │
      ▼
app.set_state(lambda s: setattr(s, "locale_index", 1))
      │
      ▼
tempestweb applies mutator → new state (locale_index=1)
      │
      ▼
view(app) called again
      │
      ▼
locale = LOCALES[1]  →  Locale(language="pt", region="BR", rtl=False)
      │
      ▼
t("app_title", locale, TRANSLATIONS)  →  "Saudação Internacionalizada"
t("greeting_anonymous", locale, TRANSLATIONS)  →  "Olá, desconhecido(a)!"
… (all strings re-computed)
      │
      ▼
reconciler computes diff → minimal patches
      │
      ▼
DOM updated
```

### Interpolation: `t()` with `**kwargs`

`t()` essentially does:

```python
catalogue[locale.language][key].format_map(kwargs)
```

So `t("greeting", locale, TRANSLATIONS, name="Alice")` resolves `"Olá, {name}!"` → `"Olá, Alice!"` with pure Python, zero dependencies.

### RTL support without CSS

tempestweb has no CSS cascade. Text alignment is a `Style` attribute — `TextAlign.RIGHT` or `TextAlign.LEFT`. The `text_align` variable is computed once from `locale.rtl` and passed to every widget that needs to respect the reading direction. Simple and explicit.

### Catalogue as data, not as a framework

`TRANSLATIONS` is a plain Python `dict`. You can load it from a JSON file, a database, or an external translation package — `t()` only requires an object that satisfies `catalogue[language][key]`. For larger apps, consider loading each language on demand to keep startup payload small.

---

## Recap

In this tutorial you learned:

- ✅ Build a **translation catalogue** as `dict[str, dict[str, str]]`
- ✅ Use `Locale` to encapsulate language, region, and RTL direction
- ✅ Call `t(key, locale, catalogue, **kwargs)` for lookups with interpolation
- ✅ Compose `t()` calls — `t()` inside `t()` for localised variable parts
- ✅ Derive `text_align` from `locale.rtl` and apply it uniformly across the tree
- ✅ Keep `view` free of language-conditional logic — only data and `t()`

---

## Next steps

Try extending the example:

- 💡 Add a **fourth language** (e.g. Japanese `ja-JP`, LTR) — just add entries to `TRANSLATIONS` and `LOCALES`
- 💡 Load the catalogue from an **external JSON file** with `json.load()` to separate strings from code
- 💡 Explore the [settings-panel](./settings-panel.md) example to see how `SegmentedControl` is used for preference persistence
- 💡 Read [Execution modes](../tutorial/modes.md) to understand how Mode B sends RTL patches to the JS client without any change to the Python code
