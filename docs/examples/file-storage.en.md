# Notes on Device Storage 📝

Build a complete notes CRUD app persisted to the **browser's IndexedDB** via `tempestweb.native.storage` — and learn how to inject native capabilities into state so your UI is 100 % testable without a browser.

---

## What you'll build

A note manager featuring:

- ✏️ **Composer** — title and body fields + "Save" and "Reload list" buttons
- 📋 **Note list** — one row per saved note with "Open" and "Delete" buttons
- 📖 **Viewer panel** — displays the title and content of the open note
- ⚠️ **Error strip** — text shown when an operation fails
- 🔄 **Progress indicator** — `Spinner` during save and reload operations

The four storage operations (`put` / `get` / `list_keys` / `remove`) are **injected into the app state** — you can replace them with test doubles without installing any real bridge.

!!! note "Theme — Native capabilities (Track N)"
    This example is part of the **Native capabilities** theme. Native capabilities are browser APIs (IndexedDB, geolocation, camera, etc.) exposed to Python as typed awaitables by `tempestweb.native`. The same Python call works in both execution modes — WASM or server.

---

## Prerequisites

Make sure tempestweb is installed:

```bash
pip install tempestweb
```

Recommended reading (optional, but helpful):

- [Basic tutorial](../tutorial/index.md) — first steps with `App`, `view`, and `set_state`
- [Managing state](../tutorial/state.md) — how `set_state` works
- [Execution modes](../tutorial/modes.md) — WASM vs. server
- [Native capabilities](../capabilities.md) — what bridges are and why they're needed

---

## Creating the project

```bash
mkdir -p examples/file-storage
touch examples/file-storage/app.py
```

---

## Step 1 — Why storage callables live in state

Before writing any widget, it's worth understanding the core design pattern of this example.

The functions `storage.put`, `storage.get`, etc. **only work with a native bridge installed**. During the initial render (the `build(view(app))` the framework calls at mount time) no I/O is performed — only the widget tree is built. The bridge does not need to be present at that point.

!!! warning "Native capabilities require a bridge"
    Calling `await storage.put(...)` (or any other native capability) **without an installed bridge** raises `BrowserUnavailableError`. The bridge is installed automatically by the runtime:

    - **Mode A (WASM):** the bootstrap installs an `FFIBridge` that dispatches to `client/native/*.js` via Pyodide FFI — no network round-trip.
    - **Mode B (server):** the server installs a `ProxyBridge` that serializes the call into a `native_call` envelope, sends it over the WebSocket, and awaits the `native_result` the browser sends back.

    In **unit tests** — no browser, no server — install a fake bridge with `install_bridge(fake)` before triggering async handlers, and remove it with `uninstall_bridge()` afterwards. The initial render (widget tree construction) never calls the callables — no bridge needed.

The solution is to place the callables as state fields with the real implementations as defaults. This means:

- The initial `build(view(app))` never touches I/O and works without a bridge.
- Async handlers read `app.state.put`, `app.state.get`, etc. — and in tests you overwrite those fields with fakes before triggering the handler.

```python
from collections.abc import Awaitable, Callable

from tempestweb.native import storage

Putter = Callable[[str, str], Awaitable[None]]
Getter = Callable[[str], Awaitable[str]]
Remover = Callable[[str], Awaitable[None]]
KeyLister = Callable[[], Awaitable[list[str]]]
```

!!! tip "Tip — type aliases for injected callables"
    Naming the callable types (`Putter`, `Getter`, etc.) serves two purposes: `mypy --strict` passes without complaints and the intent is documented right on the dataclass field.

---

## Step 2 — Application state

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class State:
    """Application state for the notes storage demo.

    Attributes:
        title_draft: The title currently typed in the title field.
        body_draft: The body currently typed in the body field.
        keys: The list of saved note keys fetched from storage.
        open_key: The key of the note currently open for reading, or ``""``.
        open_content: The content of the open note, or ``""``.
        saving: ``True`` while a save operation is in flight.
        loading: ``True`` while a list or open operation is in flight.
        error: Last error message, or ``""`` when there is no error.
        put: Injected callable matching :func:`~tempestweb.native.storage.put`.
        get: Injected callable matching :func:`~tempestweb.native.storage.get`.
        remove: Injected callable matching
            :func:`~tempestweb.native.storage.remove`.
        list_keys: Injected callable matching
            :func:`~tempestweb.native.storage.list_keys`.
    """

    title_draft: str = ""
    body_draft: str = ""
    keys: list[str] = field(default_factory=list)
    open_key: str = ""
    open_content: str = ""
    saving: bool = False
    loading: bool = False
    error: str = ""
    # Injected capabilities — real implementations by default; only called
    # inside async handlers, never during the initial mount/build.
    put: Putter = field(default=storage.put)
    get: Getter = field(default=storage.get)
    remove: Remover = field(default=storage.remove)
    list_keys: KeyLister = field(default=storage.list_keys)


def make_state() -> State:
    """Return the initial, blank application state.

    Returns:
        A fresh :class:`State` ready for the first render.
    """
    return State()
```

!!! info "Note — `field(default=storage.put)` vs. `field(default_factory=...)`"
    Since `storage.put` is a function (not a mutable object like a list), we can use it directly as `default=` rather than `default_factory=`. The dataclass will store a reference to the function — which is exactly the desired behavior.

---

## Step 3 — The save handler

Inside `view()` we define handlers as nested functions. The save handler is async because it calls `await app.state.put(...)`:

```python
async def save_note() -> None:
    """Persist the current draft to storage under ``title_draft``."""
    title = app.state.title_draft.strip()
    body = app.state.body_draft
    if not title:
        return
    app.set_state(lambda s: setattr(s, "saving", True))
    try:
        await app.state.put(title, body)

        def _on_saved(s: State) -> None:
            s.saving = False
            s.title_draft = ""
            s.body_draft = ""
            s.error = ""

        app.set_state(_on_saved)
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)

        def _on_save_error(s: State) -> None:
            s.saving = False
            s.error = msg

        app.set_state(_on_save_error)
```

!!! tip "Tip — optimism + rollback"
    The handler sets `saving=True` before the `await` for immediate feedback. Both branches (`_on_saved` and `_on_save_error`) then set `saving=False`. This "optimistic + rollback" pattern prevents the UI from getting stuck if the await is cancelled before completing.

!!! warning "Warning — `except Exception as exc` inside handlers"
    Native capabilities raise `NativeError` (quota exceeded, `not_found`, etc.) and `BrowserUnavailableError` (bridge not installed). Catching generic `Exception` here is intentional: the UI should show the error to the user instead of crashing. The `# noqa: BLE001` comment suppresses ruff's broad-exception-caught warning.

---

## Step 4 — The list handler

```python
async def refresh_list() -> None:
    """Fetch all stored note keys and update the list."""
    app.set_state(lambda s: setattr(s, "loading", True))
    try:
        keys = await app.state.list_keys()

        def _on_keys(s: State) -> None:
            s.loading = False
            s.keys = keys
            s.error = ""

        app.set_state(_on_keys)
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)

        def _on_list_error(s: State) -> None:
            s.loading = False
            s.error = msg

        app.set_state(_on_list_error)
```

!!! info "Note — `list_keys` never raises NotFoundError"
    `storage.list_keys()` returns `[]` when storage is empty — it never raises a "not found" exception. This follows the framework convention: 404 is for single-resource lookups only; collections return `[]`.

---

## Step 5 — Open and delete handlers

Since Open and Delete need to know *which* note they're operating on, they use the **handler factory** pattern: a synchronous function takes the key and returns a parameterless async callable suitable for `Button.on_click`.

```python
def open_note_handler(note_key: str) -> Callable[[], Awaitable[None]]:
    """Return an async click handler that opens *note_key*.

    Args:
        note_key: The storage key to open.

    Returns:
        A parameterless async callable suitable for ``Button.on_click``.
    """

    async def _open() -> None:
        app.set_state(lambda s: setattr(s, "loading", True))
        try:
            content = await app.state.get(note_key)

            def _on_open(s: State) -> None:
                s.loading = False
                s.open_key = note_key
                s.open_content = content
                s.error = ""

            app.set_state(_on_open)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)

            def _on_open_error(s: State) -> None:
                s.loading = False
                s.error = msg

            app.set_state(_on_open_error)

    return _open


def delete_note_handler(note_key: str) -> Callable[[], Awaitable[None]]:
    """Return an async click handler that deletes *note_key*.

    Args:
        note_key: The storage key to delete.

    Returns:
        A parameterless async callable suitable for ``Button.on_click``.
    """

    async def _delete() -> None:
        try:
            await app.state.remove(note_key)

            # Also remove from local list immediately for a snappy UI.
            def _on_delete(s: State) -> None:
                s.keys = [k for k in s.keys if k != note_key]
                if s.open_key == note_key:
                    s.open_key = ""
                    s.open_content = ""
                s.error = ""

            app.set_state(_on_delete)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            app.set_state(lambda s: setattr(s, "error", msg))

    return _delete
```

!!! tip "Tip — optimistic local list removal in `_delete`"
    After `await app.state.remove(note_key)` returns successfully, the handler filters `app.state.keys` immediately — without a new `list_keys` round-trip. This keeps the UI responsive: the item disappears instantly. A subsequent "Reload list" will sync with the real state of IndexedDB.

!!! tip "Tip — handler factory vs. `lambda _k=key: ...`"
    You could use `lambda _k=note_key: _open_impl(_k)` inside the loop to capture the current value, but the `open_note_handler(key)` factory is more readable and allows annotating the return type precisely — which `mypy --strict` requires.

---

## Step 6 — The close handler

```python
def close_note() -> None:
    """Clear the open-note panel."""

    def _close(s: State) -> None:
        s.open_key = ""
        s.open_content = ""

    app.set_state(_close)
```

This handler is **synchronous** — it doesn't access storage, it just clears two state fields.

---

## Step 7 — Assembling the UI

The `view` assembles three sections into columns stacked in the root. Let's look at each section:

### Composer

```python
composer_children: list[Widget] = [
    Text(content="New note", key="composer-title"),
    Input(
        value=app.state.title_draft,
        placeholder="Title",
        key="title-input",
        on_change=lambda e: app.set_state(
            lambda s: setattr(s, "title_draft", e.value)
        ),
    ),
    TextArea(
        value=app.state.body_draft,
        placeholder="Write your note here…",
        key="body-input",
        on_change=lambda e: app.set_state(
            lambda s: setattr(s, "body_draft", e.value)
        ),
    ),
    Row(
        style=Style(gap=8.0),
        key="composer-actions",
        children=[
            Button(
                label="Save" if not app.state.saving else "Saving…",
                on_click=save_note,
                key="save-btn",
            ),
            Button(label="Reload list", on_click=refresh_list, key="reload-btn"),
        ],
    ),
]

if app.state.saving:
    composer_children.append(Spinner(key="save-spinner"))
```

!!! tip "Tip — conditional label on the button"
    `label="Save" if not app.state.saving else "Saving…"` is the idiomatic way to provide visual feedback during an async operation without changing the tree structure — the same button node with `key="save-btn"` is updated, not replaced.

### Note list

```python
list_children: list[Widget] = [
    Text(content="Saved notes", key="list-title"),
]

if app.state.loading:
    list_children.append(Spinner(key="list-spinner"))
elif not app.state.keys:
    list_children.append(
        Text(
            content="No notes yet — type a title and hit Save.",
            key="empty-hint",
        )
    )
else:
    for key in app.state.keys:
        list_children.append(
            Row(
                style=Style(gap=8.0),
                key=f"row-{key}",
                children=[
                    Text(content=key, key=f"key-{key}"),
                    Button(
                        label="Open",
                        on_click=open_note_handler(key),
                        key=f"open-{key}",
                    ),
                    Button(
                        label="Delete",
                        on_click=delete_note_handler(key),
                        key=f"delete-{key}",
                    ),
                ],
            )
        )
```

!!! info "Note — three states of the list"
    | Condition | What is rendered |
    |---|---|
    | `app.state.loading` is `True` | `Spinner` |
    | `app.state.keys` is `[]` | Hint text "No notes yet" |
    | Keys exist | One `Row` per note with Open and Delete |

### Viewer panel

```python
viewer_children: list[Widget] = []
if app.state.open_key:
    viewer_children = [
        Text(content=f"Note: {app.state.open_key}", key="viewer-title"),
        Text(content=app.state.open_content, key="viewer-body"),
        Button(label="Close", on_click=close_note, key="close-btn"),
    ]
```

The panel only appears when `open_key` is non-empty — the entire viewer is added conditionally to the `all_sections` list.

### Final assembly

```python
all_sections: list[Widget] = [
    Column(
        style=Style(gap=8.0, padding=Edge.all(8)),
        key="composer",
        children=composer_children,
    ),
    Column(
        style=Style(gap=6.0, padding=Edge.all(8)),
        key="note-list",
        children=list_children,
    ),
]

if viewer_children:
    all_sections.append(
        Column(
            style=Style(gap=6.0, padding=Edge.all(8)),
            key="viewer",
            children=viewer_children,
        )
    )

if app.state.error:
    all_sections.append(
        Text(content=f"Error: {app.state.error}", key="error-strip")
    )

return Column(
    style=Style(gap=16.0, padding=Edge.all(16)),
    key="root",
    children=all_sections,
)
```

---

## The complete app

Full file, ready to copy:

```python
"""Notes CRUD — persisted via the device storage capability (N3).

A genuinely useful demo of ``tempestweb.native.storage``: the user types a note
title and body, saves it to IndexedDB via ``storage.put``, lists all saved keys,
opens any note, and deletes it.  The four storage callables
(:func:`~tempestweb.native.storage.put`, :func:`~tempestweb.native.storage.get`,
:func:`~tempestweb.native.storage.list_keys`,
:func:`~tempestweb.native.storage.remove`) are **injected into** :class:`State`
so the example is deterministic under test and ``build(view(app))`` is green with
no bridge installed.

The demo runs identically in both execution modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb run --mode server   # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import (
    Button,
    Column,
    Input,
    Row,
    Spinner,
    Text,
    TextArea,
)
from tempestweb.native import storage

# ---------------------------------------------------------------------------
# Callable type aliases for the injected storage capabilities.
# ---------------------------------------------------------------------------

Putter = Callable[[str, str], Awaitable[None]]
Getter = Callable[[str], Awaitable[str]]
Remover = Callable[[str], Awaitable[None]]
KeyLister = Callable[[], Awaitable[list[str]]]


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class State:
    """Application state for the notes storage demo.

    Attributes:
        title_draft: The title currently typed in the title field.
        body_draft: The body currently typed in the body field.
        keys: The list of saved note keys fetched from storage.
        open_key: The key of the note currently open for reading, or ``""``.
        open_content: The content of the open note, or ``""``.
        saving: ``True`` while a save operation is in flight.
        loading: ``True`` while a list or open operation is in flight.
        error: Last error message, or ``""`` when there is no error.
        put: Injected callable matching :func:`~tempestweb.native.storage.put`.
        get: Injected callable matching :func:`~tempestweb.native.storage.get`.
        remove: Injected callable matching
            :func:`~tempestweb.native.storage.remove`.
        list_keys: Injected callable matching
            :func:`~tempestweb.native.storage.list_keys`.
    """

    title_draft: str = ""
    body_draft: str = ""
    keys: list[str] = field(default_factory=list)
    open_key: str = ""
    open_content: str = ""
    saving: bool = False
    loading: bool = False
    error: str = ""
    # Injected capabilities — real implementations by default; only called
    # inside async handlers, never during the initial mount/build.
    put: Putter = field(default=storage.put)
    get: Getter = field(default=storage.get)
    remove: Remover = field(default=storage.remove)
    list_keys: KeyLister = field(default=storage.list_keys)


def make_state() -> State:
    """Return the initial, blank application state.

    Returns:
        A fresh :class:`State` ready for the first render.
    """
    return State()


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[State]) -> Widget:
    """Render the notes CRUD UI from the current state.

    Layout:

    * **Composer** — title + body inputs + Save / Reload buttons.
    * **Note list** — scrollable column of (key, Open, Delete) rows.
    * **Note viewer** — title + content shown when a note is open.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The full widget tree for the current state.
    """

    # ------------------------------------------------------------------ handlers

    async def save_note() -> None:
        """Persist the current draft to storage under ``title_draft``."""
        title = app.state.title_draft.strip()
        body = app.state.body_draft
        if not title:
            return
        app.set_state(lambda s: setattr(s, "saving", True))
        try:
            await app.state.put(title, body)

            def _on_saved(s: State) -> None:
                s.saving = False
                s.title_draft = ""
                s.body_draft = ""
                s.error = ""

            app.set_state(_on_saved)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)

            def _on_save_error(s: State) -> None:
                s.saving = False
                s.error = msg

            app.set_state(_on_save_error)

    async def refresh_list() -> None:
        """Fetch all stored note keys and update the list."""
        app.set_state(lambda s: setattr(s, "loading", True))
        try:
            keys = await app.state.list_keys()

            def _on_keys(s: State) -> None:
                s.loading = False
                s.keys = keys
                s.error = ""

            app.set_state(_on_keys)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)

            def _on_list_error(s: State) -> None:
                s.loading = False
                s.error = msg

            app.set_state(_on_list_error)

    def open_note_handler(note_key: str) -> Callable[[], Awaitable[None]]:
        """Return an async click handler that opens *note_key*.

        Args:
            note_key: The storage key to open.

        Returns:
            A parameterless async callable suitable for ``Button.on_click``.
        """

        async def _open() -> None:
            app.set_state(lambda s: setattr(s, "loading", True))
            try:
                content = await app.state.get(note_key)

                def _on_open(s: State) -> None:
                    s.loading = False
                    s.open_key = note_key
                    s.open_content = content
                    s.error = ""

                app.set_state(_on_open)
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)

                def _on_open_error(s: State) -> None:
                    s.loading = False
                    s.error = msg

                app.set_state(_on_open_error)

        return _open

    def delete_note_handler(note_key: str) -> Callable[[], Awaitable[None]]:
        """Return an async click handler that deletes *note_key*.

        Args:
            note_key: The storage key to delete.

        Returns:
            A parameterless async callable suitable for ``Button.on_click``.
        """

        async def _delete() -> None:
            try:
                await app.state.remove(note_key)

                # Also remove from local list immediately for a snappy UI.
                def _on_delete(s: State) -> None:
                    s.keys = [k for k in s.keys if k != note_key]
                    if s.open_key == note_key:
                        s.open_key = ""
                        s.open_content = ""
                    s.error = ""

                app.set_state(_on_delete)
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                app.set_state(lambda s: setattr(s, "error", msg))

        return _delete

    def close_note() -> None:
        """Clear the open-note panel."""

        def _close(s: State) -> None:
            s.open_key = ""
            s.open_content = ""

        app.set_state(_close)

    # ---------------------------------------------------------- composer section

    composer_children: list[Widget] = [
        Text(content="New note", key="composer-title"),
        Input(
            value=app.state.title_draft,
            placeholder="Title",
            key="title-input",
            on_change=lambda e: app.set_state(
                lambda s: setattr(s, "title_draft", e.value)
            ),
        ),
        TextArea(
            value=app.state.body_draft,
            placeholder="Write your note here…",
            key="body-input",
            on_change=lambda e: app.set_state(
                lambda s: setattr(s, "body_draft", e.value)
            ),
        ),
        Row(
            style=Style(gap=8.0),
            key="composer-actions",
            children=[
                Button(
                    label="Save" if not app.state.saving else "Saving…",
                    on_click=save_note,
                    key="save-btn",
                ),
                Button(label="Reload list", on_click=refresh_list, key="reload-btn"),
            ],
        ),
    ]

    if app.state.saving:
        composer_children.append(Spinner(key="save-spinner"))

    # ----------------------------------------------------------------- note list

    list_children: list[Widget] = [
        Text(content="Saved notes", key="list-title"),
    ]

    if app.state.loading:
        list_children.append(Spinner(key="list-spinner"))
    elif not app.state.keys:
        list_children.append(
            Text(
                content="No notes yet — type a title and hit Save.",
                key="empty-hint",
            )
        )
    else:
        for key in app.state.keys:
            list_children.append(
                Row(
                    style=Style(gap=8.0),
                    key=f"row-{key}",
                    children=[
                        Text(content=key, key=f"key-{key}"),
                        Button(
                            label="Open",
                            on_click=open_note_handler(key),
                            key=f"open-{key}",
                        ),
                        Button(
                            label="Delete",
                            on_click=delete_note_handler(key),
                            key=f"delete-{key}",
                        ),
                    ],
                )
            )

    # --------------------------------------------------------------- note viewer

    viewer_children: list[Widget] = []
    if app.state.open_key:
        viewer_children = [
            Text(content=f"Note: {app.state.open_key}", key="viewer-title"),
            Text(content=app.state.open_content, key="viewer-body"),
            Button(label="Close", on_click=close_note, key="close-btn"),
        ]

    # --------------------------------------------------------------- error strip

    all_sections: list[Widget] = [
        Column(
            style=Style(gap=8.0, padding=Edge.all(8)),
            key="composer",
            children=composer_children,
        ),
        Column(
            style=Style(gap=6.0, padding=Edge.all(8)),
            key="note-list",
            children=list_children,
        ),
    ]

    if viewer_children:
        all_sections.append(
            Column(
                style=Style(gap=6.0, padding=Edge.all(8)),
                key="viewer",
                children=viewer_children,
            )
        )

    if app.state.error:
        all_sections.append(
            Text(content=f"Error: {app.state.error}", key="error-strip")
        )

    return Column(
        style=Style(gap=16.0, padding=Edge.all(16)),
        key="root",
        children=all_sections,
    )
```

---

## Running the example ▶

### Mode A — Python in the browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm --path examples/file-storage
```

Python runs **inside the browser** via Pyodide. The `FFIBridge` is installed automatically. Calls to `storage.put/get/list_keys/remove` go directly to `client/native/storage.js`, which uses the browser's IndexedDB.

### Mode B — Python on the server (FastAPI + WebSocket)

```bash
tempestweb run --mode server --path examples/file-storage
```

Python runs on the server; the `ProxyBridge` is installed automatically. Each native call serializes a `native_call` envelope over the WebSocket, the browser executes IndexedDB, and returns a `native_result` envelope.

!!! check "Verification"
    In either mode, you should see:

    1. "New note" section with a title field, a body field, and "Save" + "Reload list" buttons
    2. "Saved notes" section with the text *"No notes yet — type a title and hit Save."*
    3. Type a title, a body, and click **Save** → fields clear; "Saving…" appears briefly
    4. Click **Reload list** → the note appears in the list with **Open** and **Delete** buttons
    5. Click **Open** → viewer panel appears with title and content
    6. Click **Close** → panel closes
    7. Click **Delete** → row disappears immediately; reload to confirm

---

## Automated verification ✅

Run all five checks before committing:

```bash
# Lint
ruff check .

# Formatting
ruff format --check .

# Type checking
mypy --strict tempestweb

# Tests (7 tests, all green)
pytest -q
```

All should pass green. The `build(view(app))` no-bridge check is **Test 1** of the suite — it guarantees the initial render is deterministic even without a browser.

---

## Testing with native capabilities

The dependency-injection pattern you saw in state makes testing straightforward. Here is how the `FakeBridge` in the test suite works:

```python
from typing import Any

from tempestweb.native import install_bridge, uninstall_bridge


class FakeBridge:
    """In-memory storage bridge for testing native.storage calls.

    Backs ``storage.put`` / ``storage.get`` / ``storage.list`` /
    ``storage.remove`` with a plain Python ``dict``.  Any other capability
    returns ``ok: False`` so tests fail explicitly if something unexpected is
    invoked.

    Attributes:
        store: The backing dictionary (``{key: content}``).
        calls: Every envelope dispatched through the bridge (audit log).
    """

    def __init__(self) -> None:
        """Initialise with an empty store and empty call log."""
        self.store: dict[str, str] = {}
        self.calls: list[dict[str, Any]] = []

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a native call envelope to the in-memory store."""
        self.calls.append(envelope)
        cap: str = envelope.get("capability", "")
        args: dict[str, Any] = envelope.get("args", {})

        if cap == "storage.put":
            self.store[args["name"]] = args["content"]
            return {"ok": True, "value": {}}

        if cap == "storage.get":
            name = args["name"]
            if name not in self.store:
                return {"ok": False, "error": "not_found", "message": f"{name!r} not found"}
            return {"ok": True, "value": {"content": self.store[name]}}

        if cap == "storage.list":
            return {"ok": True, "value": {"keys": list(self.store.keys())}}

        if cap == "storage.remove":
            name = args["name"]
            if name not in self.store:
                return {"ok": False, "error": "not_found", "message": f"{name!r} not found"}
            del self.store[name]
            return {"ok": True, "value": {}}

        return {"ok": False, "error": "unavailable", "message": f"unknown cap {cap!r}"}
```

And the pytest fixture that installs and removes the fake automatically:

```python
import pytest

@pytest.fixture(autouse=True)
def _clean_bridge():
    """Install a fresh FakeBridge before each test; remove it after."""
    bridge = FakeBridge()
    install_bridge(bridge)
    yield bridge
    uninstall_bridge()
```

!!! tip "Tip — why `install_bridge` instead of just replacing state fields?"
    You could overwrite `app.state.put = fake_put` before each test — that also works. The advantage of installing a full `FakeBridge` is that it intercepts *any* native capability the code may call, not just the ones you anticipated. The `self.calls` log also lets you assert on the dispatched envelopes — useful for verifying the wire contract is correct.

---

## How it works under the hood

### The update cycle with async I/O

```
Click "Save"  (save_note)
      │
      ▼
app.set_state(saving=True)    ← immediate re-render: label changes to "Saving…"
      │
      ▼
await app.state.put(title, body)
      │  Mode A: FFI directly to IndexedDB (no network hop)
      │  Mode B: native_call → WebSocket → browser → native_result → here
      ▼
app.set_state(_on_saved)      ← re-render: fields cleared, saving=False
      │
      ▼
view(app) called again → new widget tree
      │
      ▼
reconciler computes diff (patches)
      │
      ▼
DOM updated — only the changed nodes
```

### Comparing the four storage functions

| Function | Returns | Raises on error |
|---|---|---|
| `storage.put(name, content)` | `None` | `NativeError("quota_exceeded")` |
| `storage.get(name)` | `str` | `NativeError("not_found")` |
| `storage.remove(name)` | `None` | `NativeError("not_found")` |
| `storage.list_keys()` | `list[str]` (may be `[]`) | never raises NotFoundError |

### Why `key=f"open-{key}"` and not `key=f"open-{index}"`?

If you used `key=f"open-{index}"`, deleting the note at index 0 would make the former index-1 note inherit key `"open-0"` — the reconciler would interpret that as an *update* to the existing node, not a *removal + insertion*. With `key=f"open-{key}"` (based on the note's own name), each row has stable identity and the reconciler handles the removal correctly.

---

## Recap

In this tutorial you learned:

- ✅ Use `tempestweb.native.storage` to persist data to IndexedDB in both execution modes
- ✅ Inject native capability callables into state so the initial render is bridge-free
- ✅ Write async handlers with the "optimism + rollback" pattern (`saving=True` before `await`)
- ✅ Use the **handler factory** pattern for closures with captured keys
- ✅ Implement optimistic local list removal without an extra round-trip
- ✅ Test native capabilities with an in-memory `FakeBridge` and `install_bridge`/`uninstall_bridge`
- ✅ Guarantee that `build(view(app))` without a bridge never raises an exception

---

## Next steps

Try extending the example:

- 💡 Add a `created_at` field to notes (serialize as JSON in `content`) and sort the list by date
- 💡 Implement note editing: click Open to load the draft into the fields, then save under the same key
- 💡 Add prefix-based search by filtering `app.state.keys` at render time — no extra round-trip
- 💡 Explore `tempestweb.native.clipboard` to copy note content with a button (see the [Clipboard & Share](./clipboard-share.en.md) example)
- 💡 Combine with [PWA Web Push](./notification-center.en.md) to notify the user when a note is saved on another device
