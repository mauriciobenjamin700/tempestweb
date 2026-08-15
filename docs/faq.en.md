# Frequently asked questions

!!! abstract "What is here"
    **Decision** questions — the ones that come up before you write code, or when
    you have to pick a path. Each answer is short and points at the page that
    develops it. If your problem is an **error message**, the place is
    [When it goes wrong](troubleshooting.md).

## Which mode do I pick?

You do not decide this in code — the same `view()` runs in all three. You decide
at `build --mode`:

- **A public site or PWA** that needs SEO and a fast first paint, with no server
  → **Mode C (transpile)**.
- **Logic or state on the server** — live data, secrets, a database → **Mode B**.
- **Live Python in the browser**, to prototype or run Python libraries
  client-side → **Mode A (WASM)**.

An internal panel or a signed-in app is almost always **Mode B**. See
[Running the modes](tutorial/modes.md).

## Do I need to know CSS or front-end?

Not if your screen is an archetype. The
[ready-made screens (presets)](tutorial/presets.md) build a panel, dashboard,
listing, form and login from typed data, and come out responsive. A whole panel
takes ~260 lines with no hand-written `Style` — the
[Admin Console](examples/admin-console.md) is the full example.

For screens specific to your product you do assemble widgets, and the styling is
a typed `Style` object — not a cascading stylesheet.

## Can I use any Python library?

Depends on the mode:

- **Mode B** — yes. It is Python on the server: use whatever you like, from
  SQLAlchemy to pandas.
- **Mode A** — whatever Pyodide can install. Pure-Python packages usually work;
  packages with C extensions need a WASM build.
- **Mode C** — no. Only `tempest_core` and `tempestweb.native` cross the
  transpiler; the app layer becomes JavaScript.

## Why does my app not transpile to Mode C?

Because it uses something outside the supported subset, and the compiler tells
you what and where, with `file:line`. The most common reasons are an `import`
from outside `tempest_core`/`tempestweb.native` (which includes `presets` and
`components`), `*args`/`**kwargs`, and function decorators. The full list and
what to do about each is in [Mode C — transpile](advanced/transpile.md).

## Do I need sticky sessions in Mode B?

For **WebSocket**, no: it is a single connection carrying the whole session. For
**SSE**, yes by default — the stream goes out over one connection and events
come back over another (`POST /sse/{id}`), and both must land on the same
replica. If that is a problem for your infrastructure, `RedisSessionRouter`
routes the inbound leg over pub/sub and removes the affinity requirement. See
[Horizontal scale](advanced/deploy.md#horizontal-scale-s4).

## Can I use my own stylesheet?

The framework's styling is **typed inline** (`Style`), not a cascade — a design
decision, so the same tree can render to the DOM and to native screens. But
nothing stops a stylesheet of yours: presets emit `data-tw-layout` markers and
every widget accepts `attrs`, so you have stable selectors to aim at. See
[Theming](tutorial/theming.md).

## How does this compare to Streamlit, Reflex or PyScript?

One sentence each:

- **Streamlit** re-runs the whole script on every interaction and is great for
  data apps; tempestweb has a declarative tree with reconciliation, so state and
  focus survive the interaction.
- **Reflex** compiles to React and brings the React ecosystem with it;
  tempestweb has no JS framework at all — the client is plain JavaScript with no
  build step.
- **PyScript** is the closest relative of **Mode A**, but it is only that mode;
  here the same app also runs on the server and also becomes a static bundle.

What none of the three offers is the same `view()` holding across three modes
without changing a line.

## Is it good for a public, SEO-indexed site?

Yes, in **Mode C**: the app becomes native JavaScript and a static bundle any CDN
serves, with a good first paint. For content indexable in the HTML itself, there
is [static SSR](advanced/ssr.md).

Mode A is not for that — loading Pyodide is expensive on a first visit.

## Is it production-ready?

All three modes work and the gate covers all of them. It is still `0.x`, so a
minor release can carry a behaviour change — documented in the CHANGELOG. What is
public and what is private is defined in [Stability](stability.md).

## Recap

- The **mode** is a build choice, not a code choice.
- **Presets** cover the path for people who are not front-end developers.
- **Mode C** is the most restricted and the fastest; **Mode B** is the freest.
- Error on screen? [When it goes wrong](troubleshooting.md).
