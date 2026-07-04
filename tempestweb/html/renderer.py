"""Static server-side renderer: an IR tree to an HTML string.

This is a **leaf renderer** for the tempestweb IR, a sibling of the DOM-JS client
(``client/dom.js``). It takes a typed :class:`~tempest_core.widgets.base.Widget`
tree, builds it with :func:`tempest_core.build`, and walks the resulting
:class:`~tempest_core.Node` tree into a static HTML string — no JavaScript, no
DOM, no runtime. This is the "one tree, N renderers" thesis: the same declarative
tree that drives the interactive DOM client also renders to plain HTML on the
server.

The Node → element algorithm mirrors ``client/dom.js`` (``TAG_BY_TYPE``,
``applyControlProps``, ``applyA11yProps``) and the Style → CSS algorithm reuses
:func:`tempestweb.html.css.style_to_css`, a faithful port of ``client/style.js``,
so the server-rendered markup matches what the client would produce.

!!! warning "Known limitation — Icon and Canvas"
    ``Icon`` needs client-side JavaScript to inject its SVG glyph and ``Canvas``
    is an imperative 2D drawing surface; neither has a meaningful *static* HTML
    form. They render as empty placeholder elements (``<span
    data-tw-type="Icon"></span>`` and ``<canvas></canvas>``) rather than
    crashing. Use them only in the interactive (WASM/server) modes.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from tempest_core import Node, Widget, build
from tempestweb.html.css import style_to_css
from tempestweb.html.escape import escape_attr, escape_text

__all__: list[str] = [
    "render_document",
    "render_to_html",
]

# Each widget type maps to one HTML tag. A port of ``TAG_BY_TYPE`` in
# ``client/dom.js``. Container-like widgets are ``<div>``; Text is an inline
# ``<span>``; Button is a real ``<button>``. Unknown types fall back to ``<div>``
# so a new core widget renders (as a generic box) rather than throwing.
_TAG_BY_TYPE: dict[str, str] = {
    "Column": "div",
    "Row": "div",
    "Container": "div",
    "Stack": "div",
    "Text": "span",
    "Button": "button",
    "Input": "input",
    "Checkbox": "label",
    "Image": "img",
    "Canvas": "canvas",
}

# HTML void elements: they never have children and are written self-closing.
_VOID_ELEMENTS: frozenset[str] = frozenset({"img", "input", "br", "hr", "meta", "link"})

# An HTML attribute name must start with a letter and contain only letters,
# digits, and ``: _ -``. Any escape-hatch ``attrs`` key that fails this is
# rejected — an attribute-injection guard (a key like ``"onload x"`` or ``"a>b"``
# could otherwise inject markup or a new attribute despite value escaping).
_ATTR_KEY_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z][a-zA-Z0-9:_-]*$")

# A minimal CSS reset injected by ``render_document`` when ``css_reset`` is set:
# box-sizing + zeroed body margin, so the rendered fragment fills the viewport
# predictably regardless of the browser's UA stylesheet.
_CSS_RESET: str = "*,*::before,*::after{box-sizing:border-box}body{margin:0}"

# The htmx runtime script tag injected by ``render_document`` when ``htmx`` is set.
_HTMX_SCRIPT: str = '<script src="https://unpkg.com/htmx.org@2"></script>'


def _dump(value: Any) -> Any:  # noqa: ANN401 — accepts any IR prop value
    """Lower a prop value to a plain JSON-able structure.

    A built node carries **live** Pydantic models in its props (a ``Style``, a
    ``Semantics``); dumping them yields the same dict shape the client's
    ``model_dump(mode="json")`` wire carries, which :func:`style_to_css` and the
    a11y mapping consume. Non-model values pass through unchanged.

    Args:
        value: A prop value drawn from a node's ``props``.

    Returns:
        The dumped value: Pydantic models become dicts; everything else is
        returned as-is.
    """
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def _style_attribute(node: Node) -> list[str]:
    """Build the ``style="..."`` attribute for a node (empty when there is none).

    Mirrors ``applyProps``/``styleToCss`` in the client: the ``style`` prop is
    translated to a CSS body, and a ``Row``/``Column`` becomes a flex container by
    type even without an explicit style. Emits nothing when the CSS body is empty.

    Args:
        node: The IR node whose ``style`` prop to translate.

    Returns:
        A one-element list ``['style="..."']`` or an empty list.
    """
    style = _dump(node.props.get("style"))
    css = style_to_css(style, node.type)
    if not css:
        return []
    return [f'style="{escape_attr(css)}"']


def _a11y_attributes(node: Node) -> list[str]:
    """Build the accessibility attributes for a node (semantics + focus).

    Maps the core's renderer-agnostic a11y model to ARIA/DOM exactly as
    ``applyA11yProps`` does in the client: ``semantics.label`` → ``aria-label``,
    ``semantics.role`` → ``role``, ``semantics.hint`` → ``aria-description``;
    ``focus_order`` sets an explicit ``tabindex`` and ``focusable`` toggles a
    default one (``0`` to include, ``-1`` to exclude).

    Args:
        node: The IR node whose a11y props to map.

    Returns:
        The ARIA/tabindex attribute strings, in the client's order.
    """
    attributes: list[str] = []
    semantics = _dump(node.props.get("semantics"))
    if isinstance(semantics, dict):
        label = semantics.get("label")
        role = semantics.get("role")
        hint = semantics.get("hint")
        if label is not None:
            attributes.append(f'aria-label="{escape_attr(label)}"')
        if role is not None:
            attributes.append(f'role="{escape_attr(role)}"')
        if hint is not None:
            attributes.append(f'aria-description="{escape_attr(hint)}"')

    focus_order = node.props.get("focus_order")
    focusable = node.props.get("focusable")
    if focus_order is not None:
        attributes.append(f'tabindex="{escape_attr(focus_order)}"')
    elif focusable is True:
        attributes.append('tabindex="0"')
    elif focusable is False:
        attributes.append('tabindex="-1"')
    return attributes


def _control_attributes(node: Node) -> list[str]:
    """Build the form-control / media attributes for a node.

    Maps a widget's typed props onto the DOM attributes that make it a real
    control, mirroring ``applyControlProps`` in the client: an ``Input`` carries
    ``type``/``value``/``placeholder``/``maxlength`` and an ``Image`` carries
    ``src``/``alt``. Checkbox state is handled by :func:`_inner_html` (the nested
    input), and other types add nothing here.

    Args:
        node: The IR node whose control props to map.

    Returns:
        The control attribute strings, in the client's order.
    """
    props = node.props
    attributes: list[str] = []
    if node.type == "Input":
        attributes.append(f'type="{"password" if props.get("secure") else "text"}"')
        if "value" in props:
            attributes.append(f'value="{escape_attr(props.get("value"))}"')
        if props.get("placeholder") is not None:
            attributes.append(f'placeholder="{escape_attr(props["placeholder"])}"')
        if props.get("max_length") is not None:
            attributes.append(f'maxlength="{escape_attr(props["max_length"])}"')
    elif node.type == "Image":
        if props.get("src") is not None:
            attributes.append(f'src="{escape_attr(props["src"])}"')
        if props.get("alt") is not None:
            attributes.append(f'alt="{escape_attr(props["alt"])}"')
    return attributes


def _escape_hatch_attributes(node: Node) -> list[str]:
    """Build the arbitrary ``attrs`` escape-hatch attributes for a node.

    The core's ``attrs`` dict (``hx-*``, ``id``, ``class``, ``data-*``,
    ``aria-*``, ...) is emitted verbatim, every value escaped. Each key is
    validated against :data:`_ATTR_KEY_RE`; an invalid key raises — an
    attribute-injection guard, since a crafted key could otherwise smuggle markup
    past value escaping.

    Args:
        node: The IR node whose ``attrs`` prop to emit.

    Returns:
        The escaped attribute strings, in insertion order.

    Raises:
        ValueError: If any ``attrs`` key is not a valid HTML attribute name.
    """
    attrs = node.props.get("attrs") or {}
    attributes: list[str] = []
    for key, value in attrs.items():
        if not _ATTR_KEY_RE.match(key):
            raise ValueError(
                f"tempestweb.html: invalid HTML attribute name {key!r} in attrs "
                "(must match ^[a-zA-Z][a-zA-Z0-9:_-]*$)"
            )
        attributes.append(f'{key}="{escape_attr(value)}"')
    return attributes


def _attributes(node: Node) -> str:
    """Assemble the full attribute string for a node's opening tag.

    Order: an ``Icon`` type marker, then ``style``, accessibility, control props,
    and finally the ``attrs`` escape hatch. All values are escaped.

    Args:
        node: The IR node to render attributes for.

    Returns:
        The attribute string, leading-space-prefixed (``""`` when there are none).
    """
    parts: list[str] = []
    if node.type == "Icon":
        parts.append('data-tw-type="Icon"')
    parts.extend(_style_attribute(node))
    parts.extend(_a11y_attributes(node))
    parts.extend(_control_attributes(node))
    parts.extend(_escape_hatch_attributes(node))
    return (" " + " ".join(parts)) if parts else ""


def _inner_html(node: Node) -> str:
    """Render a node's inner HTML (text, checkbox structure, or children).

    Mirrors the client: ``Text.content`` and ``Button.label`` become escaped
    text; a ``Checkbox`` wraps a real ``<input type="checkbox">`` plus its escaped
    caption; ``Icon``/``Canvas`` have no static inner content; every other type
    recurses into its children.

    Args:
        node: The IR node to render the inner HTML for.

    Returns:
        The inner HTML string.
    """
    if node.type == "Text":
        return escape_text(node.props.get("content"))
    if node.type == "Button":
        return escape_text(node.props.get("label"))
    if node.type == "Checkbox":
        checked = " checked" if node.props.get("checked") else ""
        caption = escape_text(node.props.get("label"))
        return f'<input type="checkbox"{checked}>{caption}'
    if node.type in ("Icon", "Canvas"):
        return ""
    return "".join(_node_to_html(child) for child in node.children)


def _node_to_html(node: Node) -> str:
    """Render one IR node (and its subtree) into an HTML string.

    Resolves the tag from the node's ``tag`` override or :data:`_TAG_BY_TYPE`
    (``Icon`` defaults to ``<span>``, everything unknown to ``<div>``), assembles
    the escaped attributes, and either self-closes (void elements) or wraps the
    inner HTML.

    Args:
        node: The IR node to render.

    Returns:
        The HTML string for the node and its descendants.
    """
    override = node.props.get("tag")
    if node.type == "Icon":
        tag = override or "span"
    else:
        tag = override or _TAG_BY_TYPE.get(node.type, "div")
    attributes = _attributes(node)
    if tag in _VOID_ELEMENTS:
        return f"<{tag}{attributes} />"
    return f"<{tag}{attributes}>{_inner_html(node)}</{tag}>"


def render_to_html(widget: Widget) -> str:
    """Render a widget tree to a static HTML fragment string.

    Builds the widget with :func:`tempest_core.build` and walks the resulting IR
    into HTML. The output is a fragment (no ``<html>``/``<body>`` wrapper); use
    :func:`render_document` for a full page.

    Args:
        widget: The typed widget tree to render.

    Returns:
        The static HTML fragment.

    Raises:
        ValueError: If any widget carries an ``attrs`` key that is not a valid
            HTML attribute name.
    """
    return _node_to_html(build(widget))


def render_document(
    widget: Widget,
    *,
    title: str,
    lang: str = "pt-BR",
    head: str = "",
    htmx: bool = False,
    css_reset: bool = True,
) -> str:
    """Render a widget tree to a complete, self-contained HTML document.

    Wraps :func:`render_to_html` in a ``<!doctype html>`` shell with a charset
    meta, an escaped ``<title>``, an optional CSS reset, any extra ``head``
    markup, and — when ``htmx`` is set — the htmx runtime script tag.

    !!! info "htmx delivery"
        With ``htmx=True`` the document currently links htmx from a public CDN
        (``unpkg.com``). A later cycle's SDK will serve htmx locally; the URL is
        kept parameter-driven (a plain string in the output) so that change is a
        one-line swap and never a hard dependency here.

    Args:
        widget: The typed widget tree to render as the document body.
        title: The page title (escaped into ``<title>``).
        lang: The document language for ``<html lang="...">``. Defaults to
            ``"pt-BR"``.
        head: Extra raw markup to inject into ``<head>`` verbatim (the caller owns
            its safety). Defaults to ``""``.
        htmx: When ``True``, inject the htmx runtime ``<script>`` tag. Defaults to
            ``False``.
        css_reset: When ``True``, inject a minimal CSS reset. Defaults to
            ``True``.

    Returns:
        A complete HTML document string.

    Raises:
        ValueError: If any widget carries an ``attrs`` key that is not a valid
            HTML attribute name.
    """
    body = render_to_html(widget)
    reset = f"<style>{_CSS_RESET}</style>" if css_reset else ""
    script = _HTMX_SCRIPT if htmx else ""
    return (
        "<!doctype html>"
        f'<html lang="{escape_attr(lang)}">'
        "<head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape_text(title)}</title>"
        f"{reset}{head}{script}"
        "</head>"
        f"<body>{body}</body>"
        "</html>"
    )
