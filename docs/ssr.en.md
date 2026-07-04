# Static SSR — `render_to_html`

So far tempestweb ran the same widget tree two ways: in the browser (**Mode A**,
WASM) and on the server with a thin client (**Mode B**, WebSocket/SSE). Both are
**interactive** and depend on JavaScript.

Now there is a third target: **static HTML**. The same typed tree becomes an
**HTML string** on the server — no JavaScript, no DOM, no runtime. It is the "one
tree, N renderers" thesis taken to its end: HTML is just another leaf renderer,
alongside the DOM client. 🚀

!!! info "When to use SSR"
    Use `render_to_html` when you need **instant first paint**, **SEO**, HTML
    emails, or a page that works **without JS**. For rich interactive screens,
    stay on Modes A/B. The two coexist: you can render the shell on the server and
    hydrate with the client afterwards.

## A minimal, complete example

Write a typed tree and turn it into HTML:

```python
from tempest_core import Column, Text, Button, Style
from tempest_core.style import Edge
from tempestweb.html import render_to_html


def view() -> Column:
    """Build a tiny typed page."""
    return Column(
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            Text(content="Hello, world!"),
            Button(label="Click"),
        ],
    )


html: str = render_to_html(view())
print(html)
```

The result is an **HTML string** ready to serve:

```html
<div style="display: flex; flex-direction: column; gap: 8px; padding: 16px 16px 16px 16px"><span>Hello, world!</span><button>Click</button></div>
```

Notice: a `Column` became a `<div>` with `display: flex`, the `Text` became a
`<span>`, and the `Button` became a `<button>` — the **same** mapping the DOM
client does in `client/dom.js`, and the **same** CSS the client would generate
from the `Style`.

## A full page

`render_to_html` returns a **fragment**. For a whole `<!doctype html>` page, use
`render_document`:

```python
from tempest_core import Column, Text
from tempestweb.html import render_document


def view() -> Column:
    """Build the page body."""
    return Column(children=[Text(content="Server-rendered page")])


page: str = render_document(
    view(),
    title="My page",
    lang="en",
    htmx=True,          # injects the htmx <script>
    css_reset=True,     # injects a minimal CSS reset
)
```

You get a self-contained document with `<meta charset>`, an escaped `<title>`,
the optional reset, and — with `htmx=True` — the htmx script tag.

!!! note "htmx delivery"
    With `htmx=True` the page links htmx from a CDN (`unpkg.com`). A later cycle
    of the SDK will serve htmx locally; that is why the URL is just a
    parameter-driven string in the output, never a hard dependency here.

## Semantic HTML with `tag` and `attrs`

Since `tempest-core` 0.9.0, **every** `Widget` accepts two optional fields:

- `tag: str | None` — override the generated HTML tag (e.g. `<nav>` instead of
  `<div>`).
- `attrs: dict[str, str]` — arbitrary HTML attributes: `id`, `class`, `data-*`,
  `aria-*`, and of course htmx `hx-*`.

Both flow through `build()` and are honored by the HTML renderer:

```python
from tempest_core import Container, Column, Text
from tempestweb.html import render_to_html


def nav() -> Container:
    """Build a semantic <nav> with an htmx attribute."""
    return Container(
        tag="nav",
        attrs={"aria-label": "primary", "class": "topbar"},
        child=Column(
            tag="ul",
            children=[
                Container(tag="li", child=Text(tag="a", content="Home")),
                Container(tag="li", child=Text(tag="a", content="Docs")),
            ],
        ),
    )


print(render_to_html(nav()))
```

```html
<nav aria-label="primary" class="topbar"><ul style="display: flex; flex-direction: column"><li><a>Home</a></li><li><a>Docs</a></li></ul></nav>
```

!!! tip "`tag` changes the element, not the layout"
    The `<ul>` above is still a `Column`, so it keeps `display: flex` by nature —
    the `tag` swaps the HTML element, not the layout semantics.

## Security: everything is escaped

Text content and attribute values **always** pass through escaping:

```python
from tempest_core import Text
from tempestweb.html import render_to_html

render_to_html(Text(content="<script>alert(1)</script>"))
# -> "<span>&lt;script&gt;alert(1)&lt;/script&gt;</span>"
```

!!! danger "Attribute-injection guard"
    Beyond escaping **values**, the renderer validates `attrs` **keys** against
    `^[a-zA-Z][a-zA-Z0-9:_-]*$`. An invalid key (e.g. `"onload x"` or `"a>b"`)
    raises `ValueError` — so nobody can smuggle markup through a crafted key.

## Components work too

A `Component` is expanded by `build()` before rendering, so SSR works with your
high-level abstractions with zero changes:

```python
from tempest_core import Component, Container, Column, Text, Widget
from tempestweb.html import render_to_html


class NavBar(Component):
    """A composite that expands to a semantic nav tree."""

    items: list[str]

    def render(self) -> Widget:
        """Lower the nav into primitive widgets with semantic tags."""
        return Container(
            tag="nav",
            child=Column(
                tag="ul",
                children=[
                    Container(tag="li", child=Text(tag="a", content=item))
                    for item in self.items
                ],
            ),
        )


print(render_to_html(NavBar(items=["Home", "Docs"])))
```

## Known limitations

!!! warning "Icon and Canvas in static SSR"
    `Icon` needs JavaScript to inject its SVG glyph and `Canvas` is an imperative
    drawing surface — neither has a useful **static** form. In SSR they become
    empty placeholders (`<span data-tw-type="Icon"></span>` and
    `<canvas></canvas>`) rather than crashing. Use them in the interactive
    (A/B) modes.

## Recap

- `render_to_html(widget)` turns a typed tree into a static HTML **fragment**,
  reusing `tempest_core.build()`.
- `render_document(...)` wraps the tree in a full `<!doctype html>` **page**, with
  optional `title`, `lang`, extra `head`, CSS reset, and htmx.
- The CSS is **byte-identical** to the DOM client's (`style_to_css` is a faithful
  port of `client/style.js`), so server and client agree.
- `tag` and `attrs` (new in `tempest-core` 0.9.0) let you emit **semantic,
  htmx-ready HTML** from a typed tree.
- All text and attributes are **escaped**; invalid `attrs` keys raise
  `ValueError`.
- `Icon`/`Canvas` are placeholders in static SSR — a documented limitation, not a
  crash.
