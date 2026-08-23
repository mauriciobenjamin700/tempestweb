# When it goes wrong

!!! abstract "How to use this page"
    Every entry starts with the **literal message** you see in the terminal or
    the console, or with the **symptom** when there is no message at all. If you
    arrived here with an error on screen, paste part of it into the site search
    (the magnifier at the top) — the right entry comes up.

    The messages on this page are checked against the source by an automated
    test, so they do not go stale in silence.

---

## An extra is missing

By far the most common category, and the easiest to fix: tempestweb installs
**lean**. Every heavy capability lives in an extra, and the message always says
which one.

| Message contains | Install |
|---|---|
| `serving Mode B needs the 'server' extra (FastAPI + uvicorn)` | `pip install "tempestweb[server]"` |
| `the dev server needs the 'server' extra` | `pip install "tempestweb[server]"` |
| `the dev watcher needs watchfiles` | `pip install "tempestweb[cli]"` |
| `tomlkit is required for` `tempestweb sync` | `pip install "tempestweb[cli]"` |
| `PyJWT is required for verify_jwt` | `pip install "tempestweb[auth]"` |
| `redis is required for RedisSessionRouter` | `pip install "tempestweb[server]"` + redis |
| `pywebpush is required to send WebPush` | `pip install "tempestweb[webpush]"` |
| `cryptography is required to generate VAPID keys` | `pip install "tempestweb[webpush]"` |
| `FastAPI is required for webpush_router` | `pip install "tempestweb[server]"` |

!!! tip "When in doubt, read the message itself"
    Every message in this family ends with the exact command. They were written
    to be the documentation — you do not have to look anything up.

---

## Native capabilities

### `no native bridge installed (off-platform, or bootstrap incomplete)`

```text
no native bridge installed (off-platform, or bootstrap incomplete)
```

An `await native.<capability>()` ran where there is no browser on the far side
of the bridge. Three causes, most frequent first:

1. **You are in a test or a script**, outside a session. There is no browser —
   inject a double, or move the call inside a handler.
2. **Mode A's bootstrap did not complete.** The generated `bootstrap.js`
   installs the bridge before calling Python's `bootstrap()`; if the page broke
   before that, the error shows up on the first interaction.
3. **The Mode B session was closed** and a handler still in flight tried to use
   the bridge.

Reference: [Native capabilities](advanced/capabilities.md).

### `the installed native bridge does not support the event channel`

```text
the installed native bridge does not support the event channel
```

You called a `watch()` / `listen()` (continuous geolocation, network, sensors)
on a bridge that only resolves one-shot calls. In Mode A this happens when
`bootstrap()` was given `dispatch` but not `subscribe`/`unsubscribe`, which
produces the more specific variant:

```text
mode A native event channel is not wired (no subscribe callable)
```

The `bootstrap.js` that `tempestweb build` generates passes all three. If you
assemble the bootstrap by hand, pass the two streaming ones too.

Reference: [Native event channel](advanced/native-events.md).

---

## Session and handlers

### The interface froze — no button responds

No error at all, the screen just stops. A session dispatches **one event at a
time**: while a handler runs, nothing else is read. A slow `await` inside the
handler — model inference, a slow external API, a large file — freezes that
user's whole connection, and not even a "Cancel" helps (the click queues up
**behind** the work it was supposed to interrupt).

Move the work out of the handler with `spawn`:

```python
from tempestweb.runtime import spawn


async def analyse(app: App[State]) -> None:
    app.set_state(lambda s: setattr(s, "status", "processing…"))

    async def work() -> None:
        result = await something_slow()
        app.set_state(lambda s: setattr(s, "result", result))

    spawn(work())
```

Reference: [Long work: dispatch is serial](tutorial/best-practices.md#long-work-dispatch-is-serial).

### `spawn() needs a running tempestweb session`

```text
spawn() needs a running tempestweb session; call it from an event handler, or await the coroutine directly
```

`spawn` hangs the task off the session in the current context, and there is no
session in the context you called from — typically a test, a script, or module
code running at import. Inside a handler there always is one. Outside, just
`await` the coroutine directly.

### The handler runs, but the screen does not change

No error. Almost always a state mutation **outside** a `set_state`:

```python
# ❌ the state changes, but nothing rebuilds the tree
async def mark(app: App[State]) -> None:
    app.state.done = True

# ✅
async def mark(app: App[State]) -> None:
    app.set_state(lambda s: setattr(s, "done", True))
```

The repaint is scheduled by `set_state`, not by the object changing.

---

## Build and Mode C

### `TranspileError` with a `file:line`

The Mode C compiler accepts a subset of typed Python, and refuses early with the
exact line. The most frequent ones:

```text
is not available in Mode C
```

`import x` works for the modules Mode C serves (`re`, `json`, `math`, `base64`,
`asyncio`) and nothing else — and a refused module's message **says what to do
instead** (`datetime` → format it in your state and pass the string).

```text
variadic parameters (*args / **kwargs) are not supported
```

```text
function decorators are not supported
```

And the one you meet most when porting an existing app:

```text
is not supported (only tempest_core, `tempestweb.components` and `tempestweb.native`)
```

Mode C sees `tempest_core`, `tempestweb.components` and `tempestweb.native`
— the last one in all three forms: `from tempestweb import native`,
`from tempestweb.native import storage` and
`from tempestweb.native.geolocation import get_position`. Plain `import
tempestweb.native` is not one of them: the message says which form to write.
Annotation-only stdlib imports (`collections.abc`, `typing`) pass too: the name
exists for the type checker and costs no JS import — but using one as a **value**
is an error (`'Any' is a type-only name`), because nothing would import it.

Outside that list, `tempestweb.presets` and `tempestweb.observability` are out of
reach: screens built from presets run in Modes A and B, not in C.

A native capability Mode C does not have in-process (`camera`) is refused
saying **which mode has it**:

```text
`camera` is not served in Mode C: the facade in `native.js` has no `camera`,
so the capability needs Mode A (Pyodide) or Mode B (server)
```

A legal name in a legal module can still be missing from the client — then the
error names the **name**, not the module:

```text
is not available in Mode C (the transpile client exports no such name)
```

Reference: [Mode C — transpile](advanced/transpile.md).

### The virtualized list went empty and will not come back

A window slid deep into a list that then **shrinks** — a pull-to-refresh back to
the first page, a filter that narrows the result, a bulk delete — resolved to
nothing: the core's `_resolve_window` clamps the start to the item count, so
`[45, 75)` against 25 items becomes `[25, 25)`, zero rows. With no rows there is
no scroll, and with no scroll no event can reposition the window: the list is
stuck empty with its data loaded.

Since 0.97.0 the virtualization controller recovers: after each patch batch, a
list **with** items that materialized none (or whose window starts past the last
page) asks for the **last page** — the end of the list when it is still longer
than the window, and the top when the whole list fits.

```bash
uv add "tempestweb>=0.97.0"
```

!!! note "The resolution rule still lives in the core"
    This is a safety net, not a fix to the rule: `_resolve_window` still clamps
    the start to the count. Making a shrunken window **resolve** to the last page
    instead of nothing has to happen there — and then all three modes change at
    once.

---

### The handler receives the event instead of the value it captured

The classic loop-capture idiom — a parameter with a default, to escape Python's
late binding — received the event object instead of the index:

```python
for index, item in enumerate(items):
    def toggle(i: int = index) -> None:   # the idiom
        select(i)
    Accordion(..., on_toggle=toggle)
```

The calling convention was decided by the parameter's **kind**, never by whether
it had a default — and a parameter with a default is not something the caller has
to supply. Measured in `examples/faq-accordion`: `open_index` became a
`ClickEvent` and the accordion stopped responding for good.

Fixed in 0.96.0 across all **three** modes: a handler receives the event only
when it declares a parameter with no default (or `*args`). In Mode C the question
is the same and comes free — `fn.length` counts the parameters before the first
default.

Along with it, Mode C started **emitting** the default: `def toggle(i=index)` came
out as `(i) => …`, so the capture vanished and the closure answered `undefined`.

```bash
uv add "tempestweb>=0.96.0"
```

---

### The field will not take typing, or the grid renders one column

Three declared widgets the renderer drew as an anonymous `div` — in **all three
modes**, since `client/dom.js` is shared:

- **`TextArea`** became a `div` shaped like a field (the base sheet styles by
  `[data-tw-type]`) with nothing to focus. Fixed in 0.94.0: it is a `<textarea>`,
  with `rows` and `maxlength`.
- **`MaskedInput`** became a dead rectangle — CPF, phone and postcode did not
  exist. It is an `<input>` now, formatted as you type (`9` digit, `A` letter,
  everything else a literal), with the caret left where the reader put it.
- **`LazyGrid.columns`** was declared and never read: a three-column gallery
  rendered one item per row. It is `display: grid` +
  `grid-template-columns: repeat(N, minmax(0, 1fr))` now, and the virtualizer
  reserves space by **row** instead of by item.

With them came the reason a masked field still swallowed everything after
becoming an `<input>`: the Mode C builder mapped those widgets' `on_change` to
**`click`**. The list of "real form controls" was hand-written next to the
generator and drifts silently; it is derived from the renderer's tag table now.
That also fixes `PinInput`, which had the same defect.

If you see this, update:

```bash
uv add "tempestweb>=0.94.0"
```

---

### The switch will not toggle, the slider will not drag, the date picker will not open

The same defect as above, in the **eleven** widgets that were left — the audit
#130 asked for, done in #143. `Switch`, `Slider`, `RangeSlider`, `Dropdown`,
`Autocomplete`, `DatePicker`, `TimePicker`, `FilePicker` and `TabBar` rendered as
an anonymous `div`: no control to operate and no event to report, in all three
modes.

Fixed in 0.98.0 — each becomes the equivalent native control (see
[Controls](tutorial/controls.md)). Three details came in the same package:

- **`Checkbox` already existed and its `on_change` arrived as a raw dict.** The
  client reported `{"value": "on"}`, which does not validate as
  `ToggleEvent(checked)` — `event.checked` was an `AttributeError` waiting for the
  first click. The payload now has the widget's shape.
- **`TabView` and `RouteDrawer` stay a `div`, by decision.** Both hold an IR
  child, and a renderer-owned child is only legal inside an IR leaf. The tab strip
  is a `TabBar` beside them; a `RouteDrawer`'s `open` became `data-tw-open`, which
  the base sheet uses to slide the drawer.
- **The `Switch` was a square and the `Slider` 4px tall.** The Style the core
  resolves for these widgets describes the **parts** a hand-drawing renderer
  paints (the box, the knob, the track), and an inline style beats the base sheet.
  The part geometry is now dropped and the resolved colour becomes `accent-color`.

```bash
uv add "tempestweb>=0.98.0"
```

### Dark mode changes nothing in Mode C

The app calls `app.set_theme(Theme(mode=ThemeMode.DARK))`, Mode B goes dark, and
the same transpiled artifact stays light. Two causes, both fixed in 0.99.0:

- **The generated style tables had no mode axis.** Mode C has no Python, so each
  widget's resolved style travels as a generated table — and it was generated
  with the default theme. Since an inline style beats the stylesheet, the half
  with precedence was the half rendering light.
- **The builder refused the `theme` kwarg.** There was no way to even *ask* for
  dark: `Button(theme=app.theme)` compiled to a builder that did not name
  `theme`, so Mode C dropped it while Modes A/B resolved correctly — the same
  `view`, two results.

```bash
uv add "tempestweb>=0.99.0"
```

!!! note "Pass the theme to the widget"
    The theme is a **field on the widget**, not ambient: `Button(label="x",
    theme=app.theme)`. Without it the widget resolves the light palette in all
    three modes — that is the core's rule, not a Mode C detail. See
    [Theming](tutorial/theming.md#dark-mode-pass-the-theme-to-the-widget).

!!! warning "The base sheet is still light"
    An `Input`'s background, the page background and the hover/focus states come
    from the `--tw-*` tokens, which have no mode axis — in a dark app the field
    shows up white. Tracked in
    [#148](https://github.com/mauriciobenjamin700/tempestweb/issues/148).

---

### `setattr is not defined` (Mode C)

`setattr(obj, name, value)` was only ported in the
`lambda s: setattr(s, "field", v)` shape with a **constant** name. With a computed
name — inside a `def mutate(...)` — it emitted a call to a `setattr` that does not
exist. Measured in `examples/br-cadastro`, whose whole address block was inert.
Fixed in 0.94.0, along with `getattr`.

---

### `object is not iterable` or `X.pop is not a function` (Mode C)

A click dies in the console and the screen does not change. It is a **dict**
being treated as a list.

- **`dict(other)`** compiled to `Object.fromEntries(other)`, which needs an
  iterable of pairs and blows up on a mapping. The compiler cannot tell which one
  you hold — `dict(pairs)` is legitimate too — so since 0.93.0 the decision is
  made at runtime.
- **`d.pop(key, default)`** fell through to the array `pop`, which an object does
  not have.

Both measured in `examples/form`, whose submit died six times per click with the
page rendered and the form inert.

---

### `_pattern.match is not a function` (Mode C)

A validator using `re.compile(...)` dies, while the same code with an unannotated
assignment works.

The compiler tracks which name holds a compiled pattern — that is what lets
`.match()` become the right helper without hijacking someone else's `.match()` —
but it only tracked the form **without** an annotation.
`_pattern: re.Pattern[str] = re.compile(…)`, the spelling this repo's style rules
ask for, lost the tracking and emitted a raw `.match` on a `RegExp`, which has no
such method. Fixed in 0.93.0; it holds for `form: Form = Form(…)` too.

---

### `c.isupper is not a function` (Mode C)

Mode C's `str` predicate table had `isdigit`/`isalpha`/`isalnum`/`isspace` and
was missing the case ones. Added in 0.93.0, with Python's semantics: at least one
cased character is required, so `"1".isupper()` is `False`.

---

### `Theme.from_seed is not a function` (Mode C)

A blank page, a single console error, and a build that passed.

`_served.py` answers "does the client export this name?" — it does not answer
"does that name have this method?". `Theme` **is** served (Mode C's carries the
mode), but the seeded Material 3 palette is not ported: the base stylesheet is
what paints the tokens.

Since 0.92.0 that is a **compile error** with `file:line`:

```text
the client's own object carries no such member
```

The member manifest (`tempestweb/transpile/_members.py`) is generated by
introspecting the client in Node, the only honest source — the JS is what the
browser loads. `Color.from_hex`, `Edge.all` and `Edge.symmetric` still compile,
because those the client really carries.

---

### `Invalid left-hand side in assignment` (Mode C)

A click does nothing and the console says this. It is `xs[:] = [...]`.

A slice *reads* as `.slice(...)`, so the assignment came out as
`xs.slice(0) = [...]` — which *parses*, which is why the build's `node --check`
passed. Fixed in 0.92.0: it becomes `xs.splice(0, xs.length, ...next)`, the
in-place replacement Python performs. A partial slice (`xs[1:3] = …`) is refused
at build time, because it can grow or shrink the list.

---

### The component's `on_change` never fires (Mode C)

The component renders, the text you type stays in the box, and the handler never
runs — clicking "Sign in" does nothing at all.

Widget props travel as `camelCase` in the generated builder (`on_submit` becomes
`onSubmit`), and the rename was decided by resolving the name on `tempest_core`.
A component that only exists on the facade — `LoginForm`, `SignupForm`,
`TextField`, `EmailField`, `PasswordField` — did not resolve there, so its props
kept the wire's `snake_case` and the builder, which destructures `camelCase`,
dropped **every handler in silence**.

Fixed in 0.90.0 — the name is looked up on `tempest_core` and then on
`tempestweb.components`. As a welcome side effect, an unknown kwarg is refused at
build time again: `LoginForm(subtitle="x")` now fails with `file:line`.

```bash
uv add "tempestweb>=0.90.0"
```

---

### `Color.from_hex is not a function` / `Class constructor X cannot be invoked without 'new'`

A blank page, a single console error, and a build that passed.

- **`Color.from_hex`**: in the core `Color` is a model with a `from_hex`
  classmethod — how you write a literal color (65 calls across the examples).
  Mode C exported only the factory, so the call compiled and died at mount.
  Ported in 0.90.0.
- **`field(default_factory=OtherDataclass)`**: a dataclass compiles to a JS
  class, and calling a class without `new` is a hard `TypeError`. The nested
  default came out as `(Address)()` and the app died on the first `makeState()`.
  Fixed in 0.90.0.

Both are the family of the `Edge` that was not callable (0.86.0): a core value
whose helper was missing from the client. The build guard runs `node --check`,
which *parses* without executing — which is why they got through.

---

### The field with an error message is not red (Mode C)

The `Input` shows the message underneath, but its border and text stay the
normal color — in Mode A or B the same code paints both red.

A field with `error` set is **invalid**, and the core repaints its border and
text in the `error` role **while building it**. That rule lives in the built
style, not in the stylesheet, so the Mode C builder — a passthrough — dropped it
silently: the field compiled, mounted and lied.

Fixed in 0.88.0 — `Input` resolves through `resolveFieldStyle`, which applies the
core's rule (a 1px border in the `error` role, a bottom-only `SideBorder` when
`field_variant` is `flushed`, and the caller's `style` still winning last).

If you see this, update the package:

```bash
uv add "tempestweb>=0.88.0"
```

---

### The app loads with the **old** version of the code

No error, no warning: you rebuilt, you reloaded, and the fix is not there. It is
the **service worker**.

By design the worker does not call `skipWaiting` — the page owns the update, via
a prompt to the user. The consequence in development is that after a `build` the
new worker installs but sits **waiting**, and the old one keeps serving the
app-shell from its own cache. A plain F5 does not swap it: the tab stays
controlled by the old worker.

Diagnosis and fix, in Chrome DevTools → **Application** → **Service Workers**:

1. If a worker shows up labelled **waiting to activate**, that is it.
2. Tick **Update on reload** while you are developing — each reload then
   activates the new worker.
3. To clear it for good: **Unregister**, then **Application → Storage → Clear
   site data**, and reload.

In production the path is the other one: the page detects the waiting worker and
offers the update prompt, which posts `{type:"SKIP_WAITING"}`.

Reference: [PWA & offline](advanced/pwa.md).

---

## Connection (Mode B)

### `websocket disconnected` / `sse transport is closed`

```text
websocket disconnected
```

```text
sse transport is closed
```

The client went away (tab closed, network dropped, proxy cut it) and something
tried to write to the transport afterwards. As a server-side error it is
expected and needs no action. If it happens constantly in production with active
users, look at the **reverse proxy**: a short idle timeout or a missing
WebSocket upgrade tears down healthy connections.

If your infrastructure simply does not let WebSocket through, swap the shell for
SSE — see [Deploy](advanced/deploy.md#infrastructure-blocking-websocket-swap-the-shell-for-sse).

### The editor does not complete anything from `tempestweb`

mypy treats everything as `Any` and autocomplete suggests nothing. That is the
symptom of a version **before 0.64.0**, which did not ship the `py.typed`
marker — without it, PEP 561 tells the checker to ignore the types, however
thoroughly annotated the package is.

```bash
pip install --upgrade tempestweb
```

---

## Developing tempestweb itself

### `MODULE_NOT_FOUND` when running the client tests

The directory form breaks on Node 24+:

```bash
node --test tests/client/        # ❌ MODULE_NOT_FOUND
node --test "tests/client/*.test.js"   # ✅
```

Always use the glob, quoted so the shell does not expand it first.

---

## Recap

- **A missing-extra message** already contains the command — read it before
  searching here.
- **A missing native bridge** means "there is no browser on this side": a test,
  a script, or an incomplete bootstrap.
- **A frozen interface with no error** is the serial dispatch; the answer is
  `spawn`.
- **A screen that does not change** is a mutation without `set_state`.
- **Old code after a build** is the service worker waiting; turn on *Update on
  reload* while developing.
- **Not here?** Try the [FAQ](faq.md) or
  [open an issue](https://github.com/mauriciobenjamin700/tempestweb/issues).
