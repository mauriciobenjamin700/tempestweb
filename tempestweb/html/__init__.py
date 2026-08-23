"""tempestweb.html — static server-side HTML renderer (a leaf renderer).

Turns a typed :class:`~tempest_core.widgets.base.Widget` tree into a static HTML
string, reusing :func:`tempest_core.build`. It is a sibling of the DOM-JS client
(``client/dom.js``): the same declarative tree renders to interactive DOM in the
browser and to plain HTML on the server ("one tree, N renderers").

- :func:`render_to_html` — a widget tree to an HTML fragment.
- :func:`render_document` — a widget tree to a full ``<!doctype html>`` page.
- :func:`style_to_css` — a Style dump to a CSS declaration body (a Python port of
  ``client/style.js``).
- :func:`theme_css` — an app's :class:`~tempest_core.Theme` as the ``--tw-*``
  custom properties the base stylesheet reads (light plus dark).
- :func:`escape_text` / :func:`escape_attr` — the HTML-escaping choke points.

See ``docs/ssr.md`` for the tutorial.
"""

from __future__ import annotations

from tempestweb.html.css import style_to_css as style_to_css
from tempestweb.html.escape import escape_attr as escape_attr
from tempestweb.html.escape import escape_text as escape_text
from tempestweb.html.renderer import render_document as render_document
from tempestweb.html.renderer import render_to_html as render_to_html
from tempestweb.html.theme import ROLE_BY_VARIABLE as ROLE_BY_VARIABLE
from tempestweb.html.theme import THEME_MODE_ATTR as THEME_MODE_ATTR
from tempestweb.html.theme import theme_css as theme_css

__all__: list[str] = [
    "escape_attr",
    "escape_text",
    "render_document",
    "render_to_html",
    "style_to_css",
    "THEME_MODE_ATTR",
    "theme_css",
    "ROLE_BY_VARIABLE",
]
