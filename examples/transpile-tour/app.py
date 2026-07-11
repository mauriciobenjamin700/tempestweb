"""Mode C tour — one transpiled app exercising the core in native JS.

State + methods, navigation (Route/URL), i18n, theme + responsiveness, a validated
form (native validator), and an animated box (AnimationController). Build it with::

    tempestweb build --mode transpile examples/transpile-tour
    tempestweb dev   --mode transpile examples/transpile-tour   # livereload

It runs with zero Python in the browser — the whole app is transcribed to native
JavaScript. The same ``view`` also runs under Modes A/B unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import (
    App,
    Button,
    Column,
    Container,
    Locale,
    Route,
    Row,
    Style,
    Text,
    Theme,
    ThemeMode,
    Widget,
    t,
)
from tempest_core.animation import AnimationController, Tween
from tempest_core.style import Color, Curve, Edge
from tempest_core.validators import validate_email
from tempest_core.widgets import Input
from tempestweb import native

MESSAGES = {
    "pt": {"title": "Tour do Modo C", "home": "Início", "form": "Formulário"},
    "en": {"title": "Mode C tour", "home": "Home", "form": "Form"},
}


@dataclass
class TourState:
    """State for the tour."""

    lang: str = "pt"
    email: str = ""
    email_error: str = ""
    install: str = ""
    box: object = field(default=None)

    def set_email(self, value: str) -> None:
        """Store the email and its validation result."""
        self.email = value
        self.email_error = validate_email(value) or "ok"


def make_state() -> TourState:
    """Build the initial state with an animation controller."""
    state = TourState()
    state.box = AnimationController(0.5, curve=Curve.EASE_OUT)
    return state


def view(app: App[TourState]) -> Widget:
    """Render the tour, branching on the current route."""
    loc = Locale(language=app.state.lang)
    dark = app.theme.is_dark(platform_dark_mode=app.media.platform_dark_mode)
    wide = app.media.width >= 600.0

    def toggle_lang() -> None:
        app.set_state(lambda s: setattr(s, "lang", "en" if s.lang == "pt" else "pt"))

    def toggle_theme() -> None:
        app.set_theme(Theme(mode=ThemeMode.LIGHT if dark else ThemeMode.DARK))

    def go_form() -> None:
        app.push(Route(name="/form"))

    def go_home() -> None:
        app.pop()

    def on_email(event: object) -> None:
        value = event.payload["value"]
        app.set_state(lambda s: s.set_email(value))

    def grow() -> None:
        app.state.box.forward()
        app.register_animation(app.state.box)

    async def do_install() -> None:
        outcome = await native.install.prompt()
        app.set_state(lambda s: setattr(s, "install", outcome))

    header = Row(
        style=Style(gap=8.0),
        children=[
            Text(content=t("title", locale=loc, translations=MESSAGES), key="title"),
            Text(content=("dark" if dark else "light"), key="scheme"),
            Text(content=("wide" if wide else "narrow"), key="layout"),
        ],
    )
    controls = Row(
        style=Style(gap=8.0),
        children=[
            Button(label="lang", on_click=toggle_lang, key="lang"),
            Button(label="theme", on_click=toggle_theme, key="theme"),
        ],
    )

    if app.nav.top.name == "/form":
        body = Column(
            style=Style(gap=10.0),
            children=[
                Text(content=t("form", locale=loc, translations=MESSAGES), key="fh"),
                Input(
                    value=app.state.email,
                    placeholder="email",
                    on_change=on_email,
                    key="email",
                ),
                Text(content=app.state.email_error, key="err"),
                Button(
                    label=t("home", locale=loc, translations=MESSAGES),
                    on_click=go_home,
                    key="back",
                ),
            ],
        )
    else:
        width = Tween(begin=120.0, end=320.0).at(app.state.box.value)
        body = Column(
            style=Style(gap=10.0),
            children=[
                Container(
                    key="box",
                    style=Style(
                        width=width,
                        height=48.0,
                        background=Color(r=103, g=80, b=164, a=1.0),
                        radius=8.0,
                        transition=None,
                    ),
                    children=[],
                ),
                Button(label="grow", on_click=grow, key="grow"),
                Button(label="install", on_click=do_install, key="install"),
                Text(content=app.state.install, key="installout"),
                Button(
                    label=t("form", locale=loc, translations=MESSAGES),
                    on_click=go_form,
                    key="toform",
                ),
            ],
        )

    return Column(
        style=Style(gap=16.0, padding=Edge.all(24)),
        children=[header, controls, body],
    )
