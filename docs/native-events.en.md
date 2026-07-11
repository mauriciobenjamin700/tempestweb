# The native event channel 📡

Some capabilities don't answer **once** — they emit a **stream** of values over
time. This page shows how to consume that stream with `async for`, how it maps onto
the wire (subscribe → event → unsubscribe), and why leaving the loop is what cancels
the subscription. 🚀

## Single-shot isn't enough

Most capabilities are **single-shot**: one request, one result. You `await` and move
on:

```python
from tempestweb import native

pos = await native.geolocation.get()   # one fix, then done
```

But "where am I **now**" is different from "where am I **going**". A running app, a
map that follows the user, a speedometer — all need **continuous** readings. The
same goes for battery level, device orientation, network state, speech transcript.
Polling with `await` in a loop would be wasteful and would miss events between
calls.

That's what the **native event channel** is for (the roadmap's **T-EV** phase): a
typed stream from the client to Python, exposed as an **async iterator**.

## The `async for` pattern

Every streaming capability is a method you iterate with `async for`. Each turn of
the loop delivers the next typed value:

```python
from tempestweb import native
from tempest_core import App


async def follow_me(app: App[object]) -> None:
    """Follow the device position until the app stops consuming."""
    async for pos in native.geolocation.watch():
        app.set_state(lambda s: setattr(s, "here", (pos.latitude, pos.longitude)))
```

Read it slowly:

- `native.geolocation.watch()` **opens a subscription** and returns an async
  iterator.
- Each `pos` is a typed `Position` — the **same** type `geolocation.get()` returns
  in the single-shot shape.
- The loop runs **while events keep coming**. It doesn't "finish" on its own: you
  end it with `break`, by letting the function return, or by cancelling the task.

!!! tip "Streaming reuses the single-shot types"
    `watch()` delivers the **same** typed model as the `get()`/`state()` version.
    You learn the type once and use it in both shapes.

Today's streaming capabilities:

| Capability | Iterates |
|---|---|
| `geolocation.watch()` | `Position` as the device moves |
| `sensors.orientation()` / `sensors.motion()` | gyroscope/accelerometer readings |
| `network.watch()` | `NetworkState` on every connection change |
| `visibility.watch()` | `"visible"`/`"hidden"` on tab switch |
| `orientation.watch()` | `OrientationState` when the screen rotates |
| `battery.watch()` | `BatteryStatus` on every charge change |
| `speech.listen()` | `SpeechResult` (STT), interim and final |
| `idle.watch()` | `IdleState` when the user goes idle |
| `tabs.receive()` | messages broadcast by other tabs |
| `gamepad.watch()` | snapshots of connected controllers |
| `midi.messages()` | `MidiMessage` from any input port |

## How it travels on the wire

Under the hood, the async iterator exchanges three messages with the client. In
**Mode B** (server) they cross the WebSocket/SSE; in **Mode A** (WASM) the
`FFIBridge` resolves them in-process with exactly the same shape:

```json
// open the subscription
{ "kind": "native_subscribe", "sub_id": "s1", "capability": "geolocation.watch", "args": {"high_accuracy": true} }

// each event of the subscription (repeats)
{ "kind": "native_event", "sub_id": "s1", "event": { "latitude": -23.5, "longitude": -46.6, "accuracy": 5.0 } }

// terminal failure, OR normal end
{ "kind": "native_event", "sub_id": "s1", "error": "permission_denied", "message": "…" }
{ "kind": "native_event", "sub_id": "s1", "done": true }

// cancel the subscription
{ "kind": "native_unsubscribe", "sub_id": "s1" }
```

What `async for` does with each:

- **`native_subscribe`** — emitted when you enter the loop. The `sub_id` correlates
  the subscription and all its events (several can be in flight at once).
- **`native_event` with `event`** — becomes the next value delivered by `async for`.
- **`native_event` with `error`** — raises a `NativeError` **inside** your loop,
  ending the subscription. Handle it with `try/except`.
- **`native_event` with `done: true`** — ends the loop normally (the iterator is
  exhausted).
- **`native_unsubscribe`** — emitted **automatically** when you leave the loop.

The canonical shape of each field lives in
[`docs/contract.md`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/contract.md),
section "Canal de eventos nativo (streaming, T-EV)" — and the sibling single-shot
crossing is in the [wire contract](wire-contract.md#the-native-call-mode-b-proxy).

## Leaving the loop cancels the subscription

This is the most important point — and the most elegant. **You never call
`unsubscribe` by hand.** Leaving the `async for` does it for you:

```python
from tempestweb import native
from tempest_core import App


async def follow_until_close(app: App[object]) -> None:
    """Stop following as soon as the fix is accurate enough."""
    async for pos in native.geolocation.watch():
        app.set_state(lambda s: setattr(s, "here", pos))
        if pos.accuracy < 10.0:
            break   # ← this fires native_unsubscribe; the subscription closes
```

The `native_events()` behind every `watch()` wraps the loop in a `try/finally`:
whatever the reason you leave — `break`, returning from the function, a `raise`, or
the task being **cancelled** — the `finally` sends `native_unsubscribe`. No leaked
subscriptions, no dangling callbacks in the browser.

!!! check "Cancellation is cleanup"
    If you keep the task (`task = asyncio.create_task(follow_me(app))`) and later
    `task.cancel()`, the `async for` raises `CancelledError` at the `await` point,
    the `finally` runs, and the subscription is closed. Cancelling the task **is**
    the way to stop the stream.

## A stream needs someone consuming it

An `async for` only makes progress while **someone iterates it**. Creating the
coroutine and never `await`-ing it (nor scheduling it as a task) subscribes to
nothing — the generator just sits there.

!!! warning "Run the stream in a task, not inside a `view()`"
    Never put a streaming `async for` **inside** `view()`: `view()` must return the
    tree quickly and is called on every render. Instead, **start the consumption
    once** (in a handler, or at app bootstrap) and let it run in a dedicated task:

    ```python
    import asyncio

    from tempestweb import native
    from tempest_core import App


    async def start_following(app: App[object]) -> asyncio.Task[None]:
        """Start the position stream in a background task and keep it."""

        async def _loop() -> None:
            async for pos in native.geolocation.watch():
                app.set_state(lambda s: setattr(s, "here", pos))

        return asyncio.create_task(_loop())
    ```

    Keep the `Task` in your state so you can `cancel()` it when the screen goes
    away — closing the subscription cleanly.

## Recap

- **Streaming** capabilities deliver **many** events per subscription; you consume
  them with `async for`, not `await`.
- Each `watch()`/`listen()`/`messages()`/`receive()` returns a **typed async
  iterator** that reuses the single-shot types.
- On the wire, the loop becomes **subscribe → event\* → (error|done)**, with
  `sub_id` correlating everything — identical in Mode A (in-process) and Mode B
  (WS/SSE).
- **Leaving the loop** (`break`, return, `raise`, cancellation) fires
  `native_unsubscribe` automatically — you never clean up by hand.
- A stream **needs a consumer**: run it in a dedicated task, outside `view()`, and
  cancel the task to stop.

See the full list of streams in the
[Native capability reference](native-reference.md) and a live showcase in the
[Device panel](examples/device-panel.md). 🚀
