"""The auth page: one card, centred at every viewport size."""

from __future__ import annotations

from collections.abc import Sequence

from tempest_core import Style, Widget
from tempest_core.components import Card
from tempest_core.widgets import Column
from tempestweb.presets import roles
from tempestweb.presets.layout import box, heading, muted

__all__ = ["auth_page"]


def auth_page(
    *,
    title: str,
    body: Widget,
    subtitle: str | None = None,
    brand: str | None = None,
    footer: Sequence[Widget] = (),
    key: str = "tw-auth",
) -> Widget:
    """Build a sign-in / sign-up screen around an existing form.

    The card is centred vertically and horizontally and capped at a readable
    width, so the same tree is right on a phone and on a 27" monitor without the
    form stretching across it.

    The form itself is yours — ``LoginForm``/``SignupForm`` from
    :mod:`tempestweb.components`, or any widget. This preset only places it.

    Args:
        title: The heading above the form ("Entrar").
        body: The form widget.
        subtitle: Optional line under the heading.
        brand: Optional product name above the heading.
        footer: Widgets under the card (a "Esqueci minha senha" link, a legal
            note).
        key: The key prefix for the page's widgets.

    Returns:
        The auth page.
    """
    head: list[Widget] = []
    if brand is not None:
        head.append(muted(brand, key=f"{key}-brand", size=12.0))
    head.append(heading(title, key=f"{key}-title", size=22.0))
    if subtitle is not None:
        head.append(muted(subtitle, key=f"{key}-subtitle"))

    card = Card(
        key=f"{key}-card-inner",
        children=[
            Column(key=f"{key}-head", style=Style(gap=4.0), children=head),
            body,
        ],
    )
    children: list[Widget] = [box(roles.AUTH_CARD, [card], key=f"{key}-card")]
    if footer:
        children.append(
            Column(key=f"{key}-footer", style=Style(gap=8.0), children=list(footer))
        )
    return box(roles.AUTH, children, key=key)
