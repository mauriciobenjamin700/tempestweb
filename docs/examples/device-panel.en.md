# Device panel — Tier 1 capabilities 📱

A small control panel wiring **four** native capabilities from
[Track T](../native-reference.md) to buttons: buzz the device, keep the screen
awake, go fullscreen, and read the connection state. One screen, four Web APIs, the
**same** Python in both modes. 🚀

## What you'll build

- 🔵 **Buzz** button — vibrates in a pattern (`native.vibration`)
- 🟢 **Keep awake** button — holds/releases a screen wake lock (`native.wakelock`)
- 🟣 **Fullscreen** button — enters fullscreen (`native.fullscreen`)
- 🟠 **Network** button — reads the connection type and online status (`native.network`)
- 💬 Two status lines reflecting the last action and the network summary

!!! info "A Tier 1 showcase"
    Track T's Tier 1 is the set of **universal** capabilities — widely supported,
    cheap, high value. This example picks four of them and shows that each is just an
    `await native.<group>.<verb>()` inside a handler. No JavaScript.

## The full app

Here is `examples/device-panel/app.py` in full, ready to copy:

```python
"""Device panel — Tier-1 web-platform capabilities in one screen.

The same ``view`` runs unchanged in both interactive modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

A small control panel wiring several of the new ``native`` capabilities to
buttons: buzz the device (``vibration``), keep the screen awake
(``wakelock``), go fullscreen (``fullscreen``), and read the connection and
storage-quota state (``network`` / ``quota``). Each is a typed Python awaitable
that resolves the same way in Mode A (in-process) and Mode B (proxied to the
browser and back) — the app code never knows the difference.

The initial mount only reads state, so ``build(view(app))`` is green with no
native bridge installed; the async handlers call the capabilities, and the test
drives them through a scripted bridge.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import Button, Column, Row, Text
from tempestweb import native


@dataclass
class PanelState:
    """State for the device panel.

    Attributes:
        status: A short human-readable line describing the last action.
        awake: Whether a screen wake lock is currently held.
        network: The last connection summary read from ``network.state``.
    """

    status: str = "ready"
    awake: bool = False
    network: str = ""


def make_state() -> PanelState:
    """Build the initial state.

    Returns:
        A fresh :class:`PanelState`.
    """
    return PanelState()


def view(app: App[PanelState]) -> Widget:
    """Render the panel and wire each button to a native capability.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    async def buzz() -> None:
        await native.vibration.vibrate([100, 50, 100])
        app.set_state(lambda s: setattr(s, "status", "buzzed"))

    async def toggle_awake() -> None:
        if app.state.awake:
            app.set_state(lambda s: setattr(s, "status", "screen released"))
            app.set_state(lambda s: setattr(s, "awake", False))
        else:
            await native.wakelock.request()
            app.set_state(lambda s: setattr(s, "status", "screen kept awake"))
            app.set_state(lambda s: setattr(s, "awake", True))

    async def go_fullscreen() -> None:
        active = await native.fullscreen.enter()
        app.set_state(lambda s: setattr(s, "status", f"fullscreen={active}"))

    async def read_network() -> None:
        state = await native.network.state()
        summary = f"{state.effective_type} · online={state.online}"
        app.set_state(lambda s: setattr(s, "network", summary))
        app.set_state(lambda s: setattr(s, "status", "network read"))

    return Column(
        style=Style(gap=10.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Status: {app.state.status}", key="status"),
            Text(content=f"Network: {app.state.network or '—'}", key="network"),
            Row(
                style=Style(gap=6.0),
                children=[
                    Button(label="Buzz", on_click=buzz, key="buzz"),
                    Button(label="Keep awake", on_click=toggle_awake, key="awake"),
                    Button(label="Fullscreen", on_click=go_fullscreen, key="fs"),
                    Button(label="Network", on_click=read_network, key="net"),
                ],
            ),
        ],
    )
```

## Piece by piece

### The state

```python
@dataclass
class PanelState:
    status: str = "ready"
    awake: bool = False
    network: str = ""
```

Three simple fields: a `status` line, an `awake` boolean to remember whether the
wake lock is held, and a `network` summary from the last read. The initial render
only **reads** these fields — it never calls a capability — so `build(view(app))` is
green **with no bridge installed**. This is the same discipline as the other native
examples: the mount doesn't depend on a browser.

### The handlers — one `await` per capability

Each button wires to an `async` handler defined **inside** `view()` (to capture
`app`). Notice how each is just one capability line + `set_state`:

```python
async def buzz() -> None:
    await native.vibration.vibrate([100, 50, 100])
    app.set_state(lambda s: setattr(s, "status", "buzzed"))
```

`vibration.vibrate` takes an on/off pattern in milliseconds — `[100, 50, 100]`
buzzes for 100 ms, pauses 50 ms, buzzes another 100 ms. It's fire-and-forget: no
return value.

```python
async def toggle_awake() -> None:
    if app.state.awake:
        app.set_state(lambda s: setattr(s, "status", "screen released"))
        app.set_state(lambda s: setattr(s, "awake", False))
    else:
        await native.wakelock.request()
        app.set_state(lambda s: setattr(s, "status", "screen kept awake"))
        app.set_state(lambda s: setattr(s, "awake", True))
```

`wakelock.request()` keeps the screen awake and returns an **opaque id** (which a
fuller version would keep to call `wakelock.release(id)`). Here, to keep the example
lean, the toggle just flips the visual state.

```python
async def go_fullscreen() -> None:
    active = await native.fullscreen.enter()
    app.set_state(lambda s: setattr(s, "status", f"fullscreen={active}"))
```

`fullscreen.enter()` returns a `bool` — whether the document is in fullscreen after
the call. Good habit: reflect the real result in state, don't assume success.

```python
async def read_network() -> None:
    state = await native.network.state()
    summary = f"{state.effective_type} · online={state.online}"
    app.set_state(lambda s: setattr(s, "network", summary))
    app.set_state(lambda s: setattr(s, "status", "network read"))
```

`network.state()` returns a typed `NetworkState` (`online`, `effective_type`,
`downlink`, `rtt`, `save_data`). Here we build a short summary from two fields.

!!! tip "The same line, two mechanisms"
    No handler names a transport. In Mode A each `await native.…` resolves
    **in-process** via `FFIBridge`; in Mode B it is **proxied** through a WebSocket
    round-trip (`ProxyBridge`). The code is identical — that's what Track T
    delivers.

### The widget tree

```python
return Column(
    style=Style(gap=10.0, padding=Edge.all(16)),
    children=[
        Text(content=f"Status: {app.state.status}", key="status"),
        Text(content=f"Network: {app.state.network or '—'}", key="network"),
        Row(
            style=Style(gap=6.0),
            children=[
                Button(label="Buzz", on_click=buzz, key="buzz"),
                Button(label="Keep awake", on_click=toggle_awake, key="awake"),
                Button(label="Fullscreen", on_click=go_fullscreen, key="fs"),
                Button(label="Network", on_click=read_network, key="net"),
            ],
        ),
    ],
)
```

Two `Text` lines derived from state, and a `Row` with the four buttons. Each
`Button` takes its `async` handler directly in `on_click`. Stable `key`s keep the
reconciler (and the tests) precise.

## Running the example ▶

This example runs in **Modes A/B** — the same `app.py`, without changing a line:

```bash
tempestweb dev --mode wasm    examples/device-panel   # Python in the browser (Pyodide)
tempestweb dev --mode server  examples/device-panel   # Python on the server (FastAPI + WS)
```

!!! warning "Secure context and user gesture"
    `fullscreen.enter()`, `wakelock.request()`, and `vibration.vibrate()` only work
    from a **real** user gesture (the button click counts) and, in production, under
    **HTTPS**. On `localhost` with the dev server it all works. Outside a secure
    context, the bridge returns a `NativeError` (`insecure_context` or
    `permission_denied`) — treat it as a normal flow.

!!! check "Verify"
    In either mode you should see two status lines and four buttons. Clicking:

    1. **Buzz** → the device vibrates (on capable hardware) and the status becomes `buzzed`.
    2. **Keep awake** → status `screen kept awake`; clicking again → `screen released`.
    3. **Fullscreen** → the page enters fullscreen; status `fullscreen=True`.
    4. **Network** → the Network line shows something like `4g · online=True`.

## Recap

- Four **Tier 1** capabilities (`vibration`, `wakelock`, `fullscreen`, `network`)
  wired to four buttons, each one an `await native.<group>.<verb>()`.
- The initial render only **reads** state, so `build(view(app))` is green **with no
  bridge** — the testable pattern of the native examples.
- **Reflect the real return** in state (`fullscreen.enter()` returns a `bool`)
  instead of assuming success.
- The **same** code runs in Mode A (in-process) and Mode B (proxied) — the handler
  never knows which bridge is installed.

## Next steps

- 💡 Keep the id from `wakelock.request()` in state and call `wakelock.release(id)`
  in the toggle, to actually release it.
- 💡 Add a button that **watches** the network as a stream with
  `native.network.watch()` — see the [native event channel](../native-events.md).
- 💡 Explore the full catalog in the
  [Native capability reference](../native-reference.md).
- 💡 Compare with [Copy & Share](clipboard-share.md), which injects the capabilities
  into state to test without a browser.
