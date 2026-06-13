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
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from tempestweb._core.style import Edge

from tempestweb._core import App, Style, Widget
from tempestweb._core.widgets import (
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
