"""Run long work outside the event dispatch (issue #62).

A session dispatches its client's events **in series**: it awaits one handler
before reading the next event. That is the right default — two edits of the same
field arrive in the order the user made them — but it means a handler that takes
its time takes the whole application with it. Model inference, a report, a slow
upstream API: for as long as it runs, that user's app is frozen. Not just the
button they pressed; every button, every keystroke, and any "cancel" they might
reach for, which would queue behind the work it is meant to interrupt.

The fix inside a handler is to start the work and return::

    from tempestweb.runtime import spawn


    async def summarise(app: App[State]) -> None:
        app.set_state(lambda s: setattr(s, "status", "reading…"))

        async def work() -> None:
            summary = await slow_model.read(document)
            app.set_state(lambda s: setattr(s, "summary", summary))

        spawn(work())

:func:`spawn` is not ``asyncio.create_task``: the task is held by the session (a
bare ``create_task`` reference can be garbage-collected mid-flight) and cancelled
when the connection ends, so no orphan outlives the session it belonged to.

The spawner is context-local, the same mechanism the native bridge uses: each
session installs its own from its own task, so concurrent connections never see
each other's.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from contextvars import ContextVar
from typing import Any

__all__ = ["NoSessionError", "install_spawner", "spawn", "uninstall_spawner"]

#: Schedules a coroutine as a tracked task owned by the running session.
Spawner = Callable[[Coroutine[Any, Any, None]], None]

_spawner: ContextVar[Spawner | None] = ContextVar("tempestweb_spawner", default=None)


class NoSessionError(RuntimeError):
    """Raised by :func:`spawn` when no session owns the calling context."""


def install_spawner(spawner: Spawner) -> None:
    """Install the task spawner for the current context.

    Called by the runtime that owns the connection — a server session (Mode B) or
    the wasm runtime (Mode A) — from its own task, so the value is isolated per
    connection exactly like the native bridge.

    Args:
        spawner: Schedules a coroutine as a task the runtime tracks and cancels
            on teardown.
    """
    _spawner.set(spawner)


def uninstall_spawner() -> None:
    """Remove the installed spawner for the current context.

    Used by session teardown and by tests, so a stale spawner pointing at a dead
    session never leaks into the next one.
    """
    _spawner.set(None)


def spawn(coro: Coroutine[Any, Any, None]) -> None:
    """Run ``coro`` in the background, owned by the current session.

    Use it for anything that would otherwise hold the event dispatch: the handler
    returns immediately, the session keeps serving events, and the work updates
    the state through ``app.set_state`` when it finishes (each call schedules the
    usual coalesced rebuild, so progress can be shown as it goes).

    The task is tracked by the session and cancelled when the connection ends.

    Args:
        coro: The coroutine to run.

    Raises:
        NoSessionError: If no session owns the calling context — you are outside
            a handler, or in a plain ``asyncio.run`` with no runtime installed.
            Awaiting the coroutine directly is the fix there.
    """
    spawner = _spawner.get()
    if spawner is None:
        coro.close()
        raise NoSessionError(
            "spawn() needs a running tempestweb session; call it from an event "
            "handler, or await the coroutine directly"
        )
    spawner(coro)
