# Native capability reference 📇

This page catalogs **every** capability group in the `tempestweb.native` bridge —
one per section, with a motivating sentence and a complete, runnable snippet. It is
the pocket reference for **Track T** (web-platform parity); for the didactic
introduction ("one API, three paths"), start with [Capabilities](capabilities.md).

!!! info "One import for everything"
    Every example below starts with the same line:

    ```python
    from tempestweb import native
    ```

    From there you call `native.<group>.<verb>(...)`. The **signature is the same**
    in Mode A (WASM), Mode B (server), and Mode C (transpile) — the `--mode` only
    chooses how the call reaches the Web API.

## `await` vs `async for` — two shapes

There are **two** capability shapes, and you can tell which from how you consume it:

=== "Single-shot — `await`"

    One request, one result. The vast majority of capabilities. You `await` and get
    the typed value back.

    ```python
    from tempestweb import native

    online = await native.network.state()   # → NetworkState
    ```

=== "Streaming — `async for`"

    One subscription, **many** events over time. Consumed with `async for`; exiting
    the loop (end, `break`, cancellation) closes the subscription automatically.

    ```python
    from tempestweb import native

    async for pos in native.geolocation.watch():   # T-EV
        app.set_state(lambda s: setattr(s, "here", pos))
    ```

    Streaming capabilities run over the **native event channel (T-EV)** — see the
    [event-channel tutorial](native-events.md).

!!! warning "Secure context and Chromium-only"
    Many capabilities require **HTTPS** (or `localhost`) and some exist only in
    **Chromium** (Chrome/Edge). Each risky group exposes an `is_supported()` so you
    can degrade gracefully — treat "unsupported" as a normal flow, never a crash.

---

## Tier 1 — universal, cheap, high value

Widely supported across all modern browsers. These are the backbone of PWA parity.

### `vibration` — buzz the device

Give tactile feedback with a single burst or an on/off pattern.

```python
from tempestweb import native

async def on_success() -> None:
    await native.vibration.vibrate([100, 50, 100])   # ms: buzz, pause, buzz
```

### `badge` — count on the PWA icon

Mark the installed app's icon with an unread count (or a generic dot).

```python
from tempestweb import native

async def sync_badge(unread: int) -> None:
    if unread:
        await native.badge.set_badge(unread)   # 0 or None also clears
    else:
        await native.badge.clear()
```

### `wakelock` — keep the screen awake

Prevent the screen from sleeping during a read, recipe, or video. Keep the id that
`request()` returns to release it later.

```python
from tempestweb import native

async def start_reading() -> str:
    lock_id = await native.wakelock.request()
    return lock_id

async def stop_reading(lock_id: str) -> None:
    await native.wakelock.release(lock_id)
```

### `fullscreen` — fullscreen mode

Enter and exit fullscreen; read the current state. Each call returns whether
fullscreen is active afterward.

```python
from tempestweb import native

async def toggle_fullscreen() -> bool:
    if await native.fullscreen.state():
        await native.fullscreen.exit()
        return False
    return await native.fullscreen.enter()
```

### `network` — connection conditions

Read (`state`) or watch (`watch`, streaming) `onLine`, `effectiveType`, `downlink`,
`rtt`, and `saveData` — perfect for adapting the UI to slow networks.

```python
from tempestweb import native

async def read_network() -> None:
    net = await native.network.state()   # → NetworkState
    print(net.online, net.effective_type, net.save_data)

async def follow_network() -> None:
    async for net in native.network.watch():   # streaming (T-EV)
        app.set_state(lambda s: setattr(s, "online", net.online))
```

### `visibility` — tab focused or hidden

Know whether the page is `"visible"` or `"hidden"` — pause animations/polling when
the user switches tabs.

```python
from tempestweb import native

async def pause_when_hidden() -> None:
    async for vis in native.visibility.watch():   # streaming (T-EV)
        app.set_state(lambda s: setattr(s, "playing", vis == "visible"))
```

### `orientation` — screen orientation

Lock/unlock the orientation and read the current type/angle; watch rotations as a
stream.

```python
from tempestweb import native

async def lock_landscape() -> bool:
    return await native.orientation.lock("landscape")   # requires fullscreen

async def follow_rotation() -> None:
    async for o in native.orientation.watch():   # streaming (T-EV)
        app.set_state(lambda s: setattr(s, "angle", o.angle))
```

### `quota` — storage usage and persistence

Estimate the origin's usage/quota and ask for **persistent** storage (exempt from
eviction under pressure). Pairs with [`storage`/`offline`](pwa.md).

```python
from tempestweb import native

async def ensure_durable() -> None:
    est = await native.quota.estimate()   # → StorageEstimate(usage, quota)
    if not await native.quota.persisted():
        await native.quota.persist()
```

### `clipboard` (image) — copy/paste images

Beyond `read`/`write` for text, it now reads and writes **images** (base64 + MIME).

```python
from tempestweb import native

async def paste_image() -> None:
    img = await native.clipboard.read_image()   # → ClipboardImage
    app.set_state(lambda s: setattr(s, "png_b64", img.data_base64))

async def copy_image(png_b64: str) -> None:
    await native.clipboard.write_image(png_b64, mime_type="image/png")
```

### `battery` — level and charge (streaming)

Watch level, charging state, and estimated times. Streaming only — every change
emits a fresh `BatteryStatus`.

```python
from tempestweb import native

async def follow_battery() -> None:
    async for b in native.battery.watch():   # streaming (T-EV)
        app.set_state(lambda s: setattr(s, "battery", b.level))
```

### `sensors` — orientation and motion (streaming)

Continuous accelerometer/gyroscope readings via Device Orientation / Motion.

```python
from tempestweb import native

async def follow_tilt() -> None:
    async for o in native.sensors.orientation():   # streaming (T-EV)
        app.set_state(lambda s: setattr(s, "beta", o.beta))

async def follow_motion() -> None:
    async for m in native.sensors.motion():   # streaming (T-EV)
        app.set_state(lambda s: setattr(s, "accel", m.acceleration))
```

!!! warning "Permission on iOS"
    On Safari iOS, `deviceorientation`/`devicemotion` require explicit permission
    granted from a user gesture. The subscription raises `NativeError`
    (`permission_denied`) when refused — treat it as a normal flow.

---

## Tier 2 — widely used

Well supported in most browsers; some ask for permission.

### `speech` — synthesis (TTS) and recognition (STT)

Speak text aloud (single-shot) and list voices; recognize speech as a stream.

```python
from tempestweb import native

async def announce(text: str) -> None:
    await native.speech.speak(text, lang="en-US", rate=1.0)

async def dictate() -> None:
    async for r in native.speech.listen(lang="en-US"):   # streaming (T-EV)
        if r.is_final:
            app.set_state(lambda s: setattr(s, "said", r.transcript))
```

### `recorder` — record audio, video, or the screen

Start recording from the microphone or the screen; `stop` returns the bytes as
base64.

```python
from tempestweb import native

async def record_clip() -> None:
    rec_id = await native.recorder.start(source="microphone")
    # … user speaks …
    recording = await native.recorder.stop(rec_id)   # → Recording
    app.set_state(lambda s: setattr(s, "clip_b64", recording.data_base64))
```

### `filesystem` — read and write files with live handles

Open files through the system picker (with a reusable handle to write back), or
create a new file with the save picker.

```python
from tempestweb import native

async def open_and_edit() -> None:
    files = await native.filesystem.open_file(accept=".txt", multiple=False)
    if files:
        handle = files[0]                       # → FileHandle
        await native.filesystem.write_file(handle.id, handle.data_base64)

async def save_new(data_b64: str) -> None:
    await native.filesystem.save_file("export.bin", data_b64)
```

### `bgsync` — Background Sync + Periodic Sync

Register work the service worker replays when connectivity returns (or on a
periodic interval) — the engine behind the real offline-queue replay.

```python
from tempestweb import native

async def queue_sync() -> None:
    await native.bgsync.register("outbox")
    await native.bgsync.register_periodic("refresh", min_interval_ms=3_600_000)
```

### `tabs` — sync across tabs

Broadcast messages between tabs (BroadcastChannel) and coordinate with named locks
(Web Locks). Receiving messages is streaming.

```python
from tempestweb import native

async def broadcast_theme(theme: str) -> None:
    await native.tabs.broadcast("prefs", {"theme": theme})

async def follow_prefs() -> None:
    async for msg in native.tabs.receive("prefs"):   # streaming (T-EV)
        app.set_state(lambda s: setattr(s, "theme", msg["theme"]))
```

### `idle` — idle detection (streaming)

Know when the user goes idle or the screen locks.

```python
from tempestweb import native

async def follow_idle() -> None:
    async for state in native.idle.watch(threshold_seconds=120):   # streaming (T-EV)
        app.set_state(lambda s: setattr(s, "away", state.user == "idle"))
```

---

## Tier 3 — niche, secure-context, mostly Chromium-only

Powerful but narrowly supported. **Always** check `is_supported()` first and keep a
fallback.

!!! warning "Chromium-only + secure context"
    The groups below (with rare exceptions) exist only in Chromium (Chrome/Edge),
    require **HTTPS**, and most open a system picker that needs a user gesture.
    Firefox/Safari usually return `is_supported() == False`.

### `bluetooth` — Web Bluetooth (GATT)

Pair a BLE device and read/write GATT characteristics.

```python
from tempestweb import native

async def read_heart_rate() -> str:
    if not await native.bluetooth.is_supported():
        return ""
    device = await native.bluetooth.request(
        optional_services=["heart_rate"],
    )                                            # → BluetoothDevice
    return await native.bluetooth.read(device.id, "heart_rate", "heart_rate_measurement")
```

### `usb` — WebUSB

Request access to a USB device through the browser chooser.

```python
from tempestweb import native

async def pick_usb() -> None:
    if await native.usb.is_supported():
        device = await native.usb.request(filters=[{"vendorId": 0x2341}])
        print(device.product_name, device.vendor_id)
```

### `serial` — Web Serial

Open a serial port (Arduino, readers, etc.); returns an opaque port id.

```python
from tempestweb import native

async def pick_serial() -> str:
    if not await native.serial.is_supported():
        return ""
    return await native.serial.request(filters=[])
```

### `hid` — WebHID

Request access to HID devices (exotic gamepads, special keyboards).

```python
from tempestweb import native

async def pick_hid() -> list[dict[str, object]]:
    if not await native.hid.is_supported():
        return []
    return await native.hid.request(filters=[])
```

### `nfc` — Web NFC (write)

Write NDEF records to a nearby NFC tag.

```python
from tempestweb import native

async def write_tag(url: str) -> None:
    if await native.nfc.is_supported():
        await native.nfc.write([{"recordType": "url", "data": url}])
```

!!! tip "NFC read (`scan`) — streaming (T-EV)"
    Beyond writing, tag **scanning** is a continuous stream over the event channel:

    ```python
    async for msg in native.nfc.scan():
        print(msg.serial_number, msg.records)
    ```

    Each `NdefMessage` carries `serial_number` + decoded `records`; exiting the loop
    aborts the scan. See [Native event channel](native-events.md).

### `contacts` — Contact Picker

Let the user pick contacts through the system picker (Android/Chrome).

```python
from tempestweb import native

async def pick_contact() -> list[dict[str, object]]:
    if not await native.contacts.is_supported():
        return []
    return await native.contacts.select(properties=["name", "tel"], multiple=False)
```

### `payment` — Payment Request API

Show the browser's native payment sheet.

```python
from tempestweb import native

async def checkout() -> dict[str, object]:
    if not await native.payment.is_supported():
        return {}
    return await native.payment.request(
        methods=[{"supportedMethods": "https://example.com/pay"}],
        details={"total": {"label": "Total", "amount": {"currency": "USD", "value": "9.90"}}},
    )
```

### `pip` — Picture-in-Picture

Pop a `<video>` into a floating window.

```python
from tempestweb import native

async def pop_video() -> bool:
    return await native.pip.request(selector="video#player")

async def close_pip() -> None:
    await native.pip.exit()
```

### `eyedropper` — color eyedropper

Let the user pick a color from anywhere on screen.

```python
from tempestweb import native

async def pick_color() -> str:
    return await native.eyedropper.open()   # → "#3366ff" (or "" if cancelled)
```

### `pointerlock` — lock the pointer

Capture the mouse (games, 3D viewers), hiding the cursor.

```python
from tempestweb import native

async def start_game() -> None:
    await native.pointerlock.request(selector="#canvas")

async def end_game() -> None:
    await native.pointerlock.exit()
```

### `gamepad` — Gamepad API

Read a snapshot (`state`) or watch the controls as a stream (`watch`).

```python
from tempestweb import native

async def read_pads() -> list[dict[str, object]]:
    return await native.gamepad.state()

async def follow_pads() -> None:
    async for pads in native.gamepad.watch():   # streaming (T-EV)
        app.set_state(lambda s: setattr(s, "pads", pads))
```

### `midi` — Web MIDI

Enumerate ports, send messages, and listen to incoming messages as a stream.

```python
from tempestweb import native

async def play_note() -> None:
    if not await native.midi.is_supported():
        return
    ports = await native.midi.request_access()   # → MidiPorts
    if ports.outputs:
        await native.midi.send(ports.outputs[0]["id"], [0x90, 60, 0x7F])

async def follow_midi() -> None:
    async for msg in native.midi.messages():   # streaming (T-EV)
        app.set_state(lambda s: s.notes.append(msg.data))
```

### `webaudio` — synthesized tone

Play a "beep" without needing an audio asset (unlike `audio.play`).

```python
from tempestweb import native

async def beep() -> None:
    await native.webaudio.tone(frequency=880.0, duration_ms=150, type="sine")
```

---

## Recap

- **One import** (`from tempestweb import native`) and the same signature across the
  three modes.
- **Two shapes:** single-shot with `await`, streaming with `async for` (over the
  [T-EV event channel](native-events.md)).
- **Tier 1** is universal; **Tier 2** is widely used; **Tier 3** is Chromium-only/
  secure-context and always ships `is_supported()` + a fallback.
- Streams (`geolocation.watch`, `sensors.*`, `network.watch`, `visibility.watch`,
  `orientation.watch`, `battery.watch`, `speech.listen`, `idle.watch`,
  `tabs.receive`, `gamepad.watch`, `midi.messages`, `nfc.scan`) close the
  subscription when the loop exits.
- Track T is **complete**, with no known capability gaps.

See the bridge in action in the [Device panel](examples/device-panel.md) and the
call wire format in
[`docs/contract.md`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/contract.md). 🚀
