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
    # An IconButton is a button — the core declares ``on_click`` on it — so the
    # ``div`` fallback made the static page carry an unfocusable, unnamed box.
    "IconButton": "button",
    "Input": "input",
    # The fields #142 gave the client and this renderer never got: a TextArea that
    # is a real one, and the two inputs the base sheet was already styling as
    # fields (a static page showed a CPF box nobody could type into either).
    "TextArea": "textarea",
    "MaskedInput": "input",
    "PinInput": "input",
    "Checkbox": "label",
    # The controls of #143. A Switch and the pickers wrap their control in the
    # keyed <label> (the caption names it natively); a Slider is a range input, a
    # Dropdown a real <select> with its options.
    "Switch": "label",
    "Slider": "input",
    "Dropdown": "select",
    "Autocomplete": "label",
    "DatePicker": "label",
    "TimePicker": "label",
    "FilePicker": "label",
    "Image": "img",
    "Canvas": "canvas",
    "ProgressBar": "div",
    "Spinner": "div",
}

# The native input ``type`` each picker renders. A port of ``PICKER_INPUT_TYPES``
# in ``client/dom.js``.
_PICKER_INPUT_TYPES: dict[str, str] = {
    "DatePicker": "date",
    "TimePicker": "time",
    "FilePicker": "file",
}

# Widget types the base stylesheet paints as progress indicators. A port of
# ``INDICATOR_TYPES`` in ``client/dom.js``.
_INDICATOR_TYPES: frozenset[str] = frozenset({"ProgressBar", "Spinner"})

# HTML void elements: they never have children and are written self-closing.
_VOID_ELEMENTS: frozenset[str] = frozenset({"img", "input", "br", "hr", "meta", "link"})

# An HTML attribute name must start with a letter and contain only letters,
# digits, and ``: _ -``. Any escape-hatch ``attrs`` key that fails this is
# rejected — an attribute-injection guard (a key like ``"onload x"`` or ``"a>b"``
# could otherwise inject markup or a new attribute despite value escaping).
_ATTR_KEY_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z][a-zA-Z0-9:_-]*$")

#: Inline event-handler attribute names (``onclick``, ``onerror``, ...), which the
#: ``attrs`` escape hatch refuses. ``attrs`` carries markup an app owns — ``id``,
#: ``class``, ``data-*``, ``hx-*`` — whereas an ``on*`` value is *code*: a widget
#: built from data the app did not write (a row label, a remote field) would ship
#: it into the page as a script. The DOM renderer refuses the same names, so a
#: tree behaves identically whichever renderer draws it.
_EVENT_HANDLER_ATTR_RE: re.Pattern[str] = re.compile(r"^on", re.IGNORECASE)

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
    if node.type in _INDICATOR_TYPES:
        css = f"{_indicator_css(node)}{css}"
    if not css:
        return []
    return [f'style="{escape_attr(css)}"']


def _indicator_css(node: Node) -> str:
    """Build the inline CSS that makes an indicator visible with no stylesheet.

    This is where the SSR renderer parts company with the client. In the DOM the
    look comes from the base theme, which an app rebrands through its
    ``--tw-*`` tokens; a server-rendered page ships no stylesheet at all — only
    a reset — so a bar that relied on one would be the empty zero-height div
    this whole thing exists to fix. The inline rules are therefore
    palette-agnostic: the track is a translucent black, the fill is
    ``currentColor``, so the bar takes the colour of the text around it and
    looks deliberate on any background.

    A caller's own ``style`` is appended after these and wins, since the later
    declaration in a CSS body is the one that applies.

    Args:
        node: The ``ProgressBar`` or ``Spinner`` node.

    Returns:
        The CSS body, ending in ``;`` so a caller's style can follow it.
    """
    if node.type == "Spinner":
        size = float(node.props.get("size") or 20)
        return (
            f"display: inline-block; box-sizing: border-box; width: {size:g}px; "
            f"height: {size:g}px; border: 2px solid rgba(0, 0, 0, 0.12); "
            "border-top-color: currentColor; border-radius: 9999px;"
        )
    return (
        "display: block; width: 100%; height: 4px; overflow: hidden; "
        "border-radius: 9999px; background: rgba(0, 0, 0, 0.12);"
    )


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
    if node.type == "Slider":
        attributes.append('type="range"')
        attributes.extend(_range_attributes(props, value=props.get("value")))
    elif node.type == "MaskedInput":
        attributes.append('type="text"')
        if "value" in props:
            attributes.append(f'value="{escape_attr(props.get("value"))}"')
        if props.get("placeholder") is not None:
            attributes.append(f'placeholder="{escape_attr(props["placeholder"])}"')
        if props.get("mask") is not None:
            attributes.append(f'data-tw-mask="{escape_attr(props["mask"])}"')
    elif node.type == "PinInput":
        secure = bool(props.get("secure"))
        attributes.append(f'type="{"password" if secure else "text"}"')
        attributes.append('inputmode="numeric"')
        attributes.append('autocomplete="one-time-code"')
        if props.get("length") is not None:
            length = max(1, int(props["length"]))
            attributes.append(f'maxlength="{length}"')
            attributes.append(f'data-tw-length="{length}"')
        if "value" in props:
            attributes.append(f'value="{escape_attr(props.get("value"))}"')
    elif node.type == "TextArea":
        if props.get("placeholder") is not None:
            attributes.append(f'placeholder="{escape_attr(props["placeholder"])}"')
        if props.get("rows") is not None:
            attributes.append(f'rows="{escape_attr(props["rows"])}"')
        if props.get("max_length") is not None:
            attributes.append(f'maxlength="{escape_attr(props["max_length"])}"')
    elif node.type == "FilePicker" and props.get("value"):
        attributes.append(f'data-tw-value="{escape_attr(props["value"])}"')
    elif node.type == "TabBar":
        attributes.append('role="tablist"')
        attributes.append(f'data-tw-active="{escape_attr(props.get("active", 0))}"')
    elif node.type == "TabView":
        attributes.append('role="tabpanel"')
        attributes.append(f'data-tw-active="{escape_attr(props.get("active", 0))}"')
        tabs = props.get("tabs")
        active = int(props.get("active", 0) or 0)
        if isinstance(tabs, list) and 0 <= active < len(tabs):
            attributes.append(f'aria-label="{escape_attr(tabs[active])}"')
    elif node.type == "RouteDrawer":
        open_ = bool(props.get("open"))
        if open_:
            attributes.append('data-tw-open=""')
        else:
            # `aria-expanded` is not allowed on a role-less div (axe:
            # aria-allowed-attr). "Expanded" describes the control that toggles the
            # drawer — the app's button. What this element can say is that it is
            # hidden.
            attributes.append('aria-hidden="true"')
    elif node.type == "Input":
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
    elif node.type in _INDICATOR_TYPES:
        attributes.extend(_indicator_attributes(node))
    return attributes


#: The accessible name of one RangeSlider thumb: ``(suffix, standalone)`` — the
#: suffix qualifies the widget's own name, the standalone form is used when the
#: widget has none. Mirrors ``RANGE_THUMB_NAMES`` in ``client/dom.js``.
_RANGE_THUMB_NAMES: dict[str, tuple[str, str]] = {
    "low": ("minimum", "Minimum"),
    "high": ("maximum", "Maximum"),
}


def _range_thumb_name(dumped: dict[str, Any], part: str) -> str:
    """Return the accessible name for one RangeSlider thumb.

    The wrapper is a role-less ``<div>``, so its ``aria-label`` names nothing a
    reader can reach: the reader lands on the two range inputs, and an unnamed
    range input is a critical axe violation (rule ``label``). Each thumb is named
    after the widget **plus the end it moves**, because two controls announced by
    the same name are the same defect wearing a name.

    Args:
        dumped: The node's props, as the wire carries them.
        part: Which end the thumb is: ``"low"`` or ``"high"``.

    Returns:
        The name to put on the thumb's ``aria-label``.
    """
    suffix, alone = _RANGE_THUMB_NAMES[part]
    semantics = _dump(dumped.get("semantics"))
    label = semantics.get("label") if isinstance(semantics, dict) else None
    if label is None or str(label) == "":
        return alone
    return f"{label} ({suffix})"


def _range_attributes(props: dict[str, Any], value: Any) -> list[str]:  # noqa: ANN401 — wire-shaped prop value
    """Build a range input's bounds and current value.

    Args:
        props: The node's props, read for ``min_value``/``max_value``/``step``.
        value: The value this particular input holds (a Slider's ``value``, or one
            of a RangeSlider's two ends).

    Returns:
        The attribute strings, bounds before value — the order the client applies
        them in, because a range input clamps to the bounds it has at the time.
    """
    attributes: list[str] = []
    bounds = (("min_value", "min"), ("max_value", "max"), ("step", "step"))
    for prop, attribute in bounds:
        if props.get(prop) is not None:
            attributes.append(f'{attribute}="{escape_attr(props[prop])}"')
    if value is not None:
        attributes.append(f'value="{escape_attr(value)}"')
    return attributes


def _options_html(options: Any, placeholder: str | None) -> str:  # noqa: ANN401 — wire-shaped prop value
    """Render an ``options`` list as ``<option>`` markup.

    Args:
        options: The option values, in order (anything else renders nothing).
        placeholder: A leading disabled option, or None for none.

    Returns:
        The options markup, placeholder first when there is one.
    """
    parts: list[str] = []
    if placeholder:
        parts.append(
            f'<option value="" disabled data-tw-part="placeholder">'
            f"{escape_text(placeholder)}</option>"
        )
    if isinstance(options, list):
        for option in options:
            value = escape_attr(option)
            parts.append(f'<option value="{value}">{escape_text(option)}</option>')
    return "".join(parts)


def _indicator_attributes(node: Node) -> list[str]:
    """Build the attributes that make a progress indicator visible and audible.

    Mirrors ``applyIndicatorProps`` in the client. The ``color_scheme`` family
    travels as ``data-tw-scheme``, which is what the base stylesheet keys the
    accent off, and the ARIA trio makes the bar a real ``progressbar`` to a
    screen reader. ``aria-valuenow`` is written only for a determinate bar: a
    number on work whose progress nobody is measuring would be read out as fact.

    Args:
        node: The ``ProgressBar`` or ``Spinner`` node.

    Returns:
        The attribute strings, in the client's order.
    """
    props = node.props
    attributes: list[str] = ['role="progressbar"']
    scheme = props.get("color_scheme")
    if scheme is not None:
        attributes.append(f'data-tw-scheme="{escape_attr(scheme)}"')
    if node.type == "Spinner":
        return attributes
    attributes.extend(('aria-valuemin="0"', 'aria-valuemax="1"'))
    if props.get("indeterminate"):
        attributes.append("data-tw-indeterminate")
        return attributes
    attributes.append(f'aria-valuenow="{escape_attr(_bar_value(node))}"')
    return attributes


def _bar_value(node: Node) -> float:
    """Read a determinate bar's fraction, clamped to what it can mean.

    Args:
        node: The ``ProgressBar`` node.

    Returns:
        The completed fraction, within ``[0, 1]``.
    """
    try:
        value = float(node.props.get("value", 0.0))
    except (TypeError, ValueError):
        return 0.0
    return min(max(value, 0.0), 1.0)


def _escape_hatch_attributes(node: Node) -> list[str]:
    """Build the arbitrary ``attrs`` escape-hatch attributes for a node.

    The core's ``attrs`` dict (``hx-*``, ``id``, ``class``, ``data-*``,
    ``aria-*``, ...) is emitted verbatim, every value escaped. Each key is
    validated against :data:`_ATTR_KEY_RE`; an invalid key raises — an
    attribute-injection guard, since a crafted key could otherwise smuggle markup
    past value escaping. An inline event-handler name (:data:`_EVENT_HANDLER_ATTR_RE`)
    raises as well: its value is script, which escaping cannot make safe.

    Args:
        node: The IR node whose ``attrs`` prop to emit.

    Returns:
        The escaped attribute strings, in insertion order.

    Raises:
        ValueError: If any ``attrs`` key is not a valid HTML attribute name, or
            names an inline event handler.
    """
    attrs = node.props.get("attrs") or {}
    attributes: list[str] = []
    for key, value in attrs.items():
        if not _ATTR_KEY_RE.match(key):
            raise ValueError(
                f"tempestweb.html: invalid HTML attribute name {key!r} in attrs "
                "(must match ^[a-zA-Z][a-zA-Z0-9:_-]*$)"
            )
        if _EVENT_HANDLER_ATTR_RE.match(key):
            raise ValueError(
                f"tempestweb.html: inline event-handler attribute {key!r} is not "
                "allowed in attrs (its value would be executed as script)"
            )
        attributes.append(f'{key}="{escape_attr(value)}"')
    return attributes


def _icon_button_name(node: Node) -> list[str]:
    """Name an ``IconButton`` from its ``label`` when semantics does not.

    On an icon-only control the ``label`` *is* the accessible name — the DOM
    renderer applies it the same way. An explicit ``semantics.label`` is emitted
    earlier and wins, so this only fills the gap.

    Args:
        node: The IR node to name.

    Returns:
        The ``aria-label`` attribute, or an empty list.
    """
    if node.type != "IconButton":
        return []
    semantics = _dump(node.props.get("semantics"))
    if isinstance(semantics, dict) and semantics.get("label") is not None:
        return []
    label = node.props.get("label")
    if label is None or str(label) == "":
        return []
    return [f'aria-label="{escape_attr(label)}"']


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
    if node.type == "IconButton":
        parts.append('data-tw-type="IconButton"')
        parts.append('type="button"')
    parts.extend(_style_attribute(node))
    parts.extend(_a11y_attributes(node))
    parts.extend(_icon_button_name(node))
    parts.extend(_control_attributes(node))
    parts.extend(_escape_hatch_attributes(node))
    return (" " + " ".join(parts)) if parts else ""


def _inner_html(node: Node) -> str:
    """Render a node's inner HTML (text, checkbox structure, or children).

    Mirrors the client: ``Text.content`` and ``Button.label`` become escaped
    text; a ``Checkbox`` wraps a real ``<input type="checkbox">`` plus its escaped
    caption; a ``ProgressBar`` owns one fill element sized by its value;
    ``Icon``/``Canvas``/``Spinner`` have no static inner content; every other
    type recurses into its children.

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
    if node.type == "Switch":
        checked = " checked" if node.props.get("checked") else ""
        caption = escape_text(node.props.get("label"))
        return f'<input type="checkbox" role="switch"{checked}>{caption}'
    if node.type == "TextArea":
        return escape_text(node.props.get("value"))
    if node.type == "Dropdown":
        return _options_html(node.props.get("options"), node.props.get("placeholder"))
    if node.type == "Autocomplete":
        list_id = f"tw-list-{node.key or 'anon'}"
        value = escape_attr(node.props.get("value"))
        placeholder = node.props.get("placeholder")
        hint = f' placeholder="{escape_attr(placeholder)}"' if placeholder else ""
        options = _options_html(node.props.get("options"), None)
        return (
            f'<input type="text" list="{escape_attr(list_id)}" value="{value}"{hint}>'
            f'<datalist id="{escape_attr(list_id)}">{options}</datalist>'
        )
    if node.type in _PICKER_INPUT_TYPES:
        input_type = _PICKER_INPUT_TYPES[node.type]
        caption = escape_text(node.props.get("label"))
        # A file input's value is unassignable — the renderer reflects it as the
        # attribute the base sheet prints instead (see _control_attributes).
        held = node.props.get("value")
        shown = (
            ""
            if node.type == "FilePicker" or held is None
            else f' value="{escape_attr(held)}"'
        )
        return f'<input type="{input_type}"{shown}>{caption}'
    if node.type == "RangeSlider":
        props = node.props
        low_attrs = " ".join(_range_attributes(props, props.get("low")))
        high_attrs = " ".join(_range_attributes(props, props.get("high")))
        low_name = _range_thumb_name(props, "low")
        high_name = _range_thumb_name(props, "high")
        return (
            f'<input type="range" data-tw-part="low" '
            f'aria-label="{escape_attr(low_name)}" {low_attrs}>'
            f'<input type="range" data-tw-part="high" '
            f'aria-label="{escape_attr(high_name)}" {high_attrs}>'
        )
    if node.type == "TabBar":
        tabs = node.props.get("tabs")
        active = int(node.props.get("active", 0) or 0)
        if not isinstance(tabs, list):
            return ""
        return "".join(
            _tab_html(index, label, active) for index, label in enumerate(tabs)
        )
    if node.type in ("Icon", "Canvas", "Spinner", "IconButton"):
        # The static renderer carries no icon path data (an ``Icon`` is an empty
        # ``<span>`` here too), so an IconButton is an empty, *named* button —
        # focusable and announced, with the glyph drawn once the client hydrates.
        return ""
    if node.type == "ProgressBar":
        fill = (
            "display: block; height: 100%; border-radius: inherit; "
            "background: currentColor;"
        )
        if node.props.get("indeterminate"):
            return f'<div data-tw-part="fill" style="{fill} width: 40%"></div>'
        width = _bar_value(node) * 100
        return f'<div data-tw-part="fill" style="{fill} width: {width:g}%"></div>'
    return "".join(_node_to_html(child) for child in node.children)


def _tab_html(index: int, label: Any, active: int) -> str:  # noqa: ANN401 — wire-shaped prop value
    """Render one `TabBar` tab as the button the client would draw.

    Args:
        index: The tab's position in the strip.
        label: Its caption.
        active: The index of the selected tab.

    Returns:
        The button markup, carrying its index and selected state.
    """
    selected = "true" if index == active else "false"
    focusable = "0" if index == active else "-1"
    return (
        f'<button type="button" role="tab" data-tw-part="tab"'
        f' data-tw-value="{index}" aria-selected="{selected}"'
        f' tabindex="{focusable}">{escape_text(label)}</button>'
    )


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
