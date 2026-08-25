"""``on_complete`` and ``on_validate`` fire from the client's new events.

Both were declared by the core and unreachable. A ``PinInput`` rendered as an
empty div, so nothing could be typed into it and neither of its handlers could
run; a ``FormField``'s ``name`` never reached the DOM, so the client had nothing
to report and validation could only happen on submit.

These pin the Python halves: ``complete`` resolves ``on_complete`` and coerces to
a ``SubmitEvent``, ``validate`` resolves ``on_validate`` and coerces to a
``ValidationEvent``, in both Python-side runtimes.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest

from tempest_core import (
    App,
    Column,
    FormField,
    Input,
    PinInput,
    SubmitEvent,
    ValidationEvent,
    Widget,
)
from tempestweb.runtime import AppSession, WasmRuntime
from tempestweb.transports import WasmTransport
from tempestweb.transports.base import Event, Patch, TransportClosedError

CODE_LENGTH: int = 4


@dataclass
class _State:
    """State for the form views.

    Attributes:
        code: What has been typed into the pin field.
        email: The email field's current value.
        error: The message the last validation produced ("" when the field is
            fine — the core types this as a plain ``str``).
        log: One entry per handler call.
    """

    code: str = ""
    email: str = ""
    error: str = ""
    log: list[str] = field(default_factory=list)


def _pin_view(app: App[_State]) -> Widget:
    """Render a pin field that submits itself once it is full.

    Args:
        app: The application handle.

    Returns:
        The widget tree for the current state.
    """

    def completed(event: SubmitEvent) -> None:
        app.state.log.append(f"complete:{event.values.get('value', '')}")

    return PinInput(
        key="code",
        length=CODE_LENGTH,
        value=app.state.code,
        on_complete=completed,
    )


def _field_view(app: App[_State]) -> Widget:
    """Render a field that validates when the reader leaves it.

    Args:
        app: The application handle.

    Returns:
        The widget tree for the current state.
    """

    def validate(event: ValidationEvent) -> None:
        message = "" if "@" in event.value else "E-mail inválido"

        def mutate(state: _State) -> None:
            state.email = event.value
            state.error = message
            state.log.append(f"validate:{event.field}")

        app.set_state(mutate)

    return Column(
        key="root",
        children=[
            FormField(
                key="f-email",
                name="email",
                label="E-mail",
                error=app.state.error,
                child=Input(key="email-in", value=app.state.email),
                on_validate=validate,
            )
        ],
    )


class _StubTransport:
    """The narrowest ``PatchTransport`` a session needs to dispatch one event.

    Attributes:
        sent: Every patch batch the session pushed, in order.
    """

    def __init__(self) -> None:
        """Initialize the transport with an empty patch log."""
        self.sent: list[list[Patch]] = []

    async def send_patches(self, patches: list[Patch]) -> None:
        """Record a patch batch.

        Args:
            patches: The batch the session produced.
        """
        self.sent.append(patches)

    async def send_navigate(self, path: str) -> None:
        """Ignore navigation.

        Args:
            path: The new path.
        """

    async def send_theme(self, mode: str) -> None:
        """Mark the theme mode — unused by this harness.

        Args:
            mode: The resolved theme mode (ignored).
        """
        return None

    async def send_native_call(
        self, call_id: str, capability: str, args: dict[str, Any]
    ) -> None:
        """Ignore native calls.

        Args:
            call_id: The correlation id.
            capability: The capability name.
            args: The capability arguments.
        """

    async def send_native_subscribe(
        self, sub_id: str, capability: str, args: dict[str, Any]
    ) -> None:
        """Ignore native subscriptions.

        Args:
            sub_id: The subscription id.
            capability: The capability name.
            args: The capability arguments.
        """

    async def send_native_unsubscribe(self, sub_id: str) -> None:
        """Ignore native unsubscriptions.

        Args:
            sub_id: The subscription id.
        """

    def on_native_result(self, handler: Any) -> None:  # noqa: ANN401 — test double
        """Ignore the native-result sink the session registers.

        Args:
            handler: The sink the session registers.
        """

    def on_native_event(self, handler: Any) -> None:  # noqa: ANN401 — test double
        """Ignore the native-event sink the session registers.

        Args:
            handler: The sink the session registers.
        """

    async def recv_event(self) -> Event:
        """Report no further events.

        Raises:
            TransportClosedError: Always — these tests dispatch directly.
        """
        raise TransportClosedError("no scripted events")

    async def close(self) -> None:
        """Ignore close."""


def _complete(key: str, value: str) -> Event:
    """Build the wire event a filled-in pin field produces.

    Args:
        key: The field's widget key.
        value: The code that was typed.

    Returns:
        The wire event.
    """
    return {"type": "complete", "key": key, "payload": {"values": {"value": value}}}


def _validate(key: str, name: str, value: str) -> Event:
    """Build the wire event leaving a form field produces.

    Args:
        key: The field's widget key.
        name: The field's declared name.
        value: The control's current value.

    Returns:
        The wire event.
    """
    return {"type": "validate", "key": key, "payload": {"field": name, "value": value}}


@pytest.mark.asyncio
async def test_mode_b_complete_runs_the_handler() -> None:
    """A full code runs ``on_complete`` with the code in the typed event."""
    state = _State()
    session: AppSession[_State] = AppSession(lambda: state, _pin_view, _StubTransport())
    await session.start()

    await session.dispatch(_complete("code", "1234"))

    assert state.log == ["complete:1234"]
    await session.close()


@pytest.mark.asyncio
async def test_mode_a_complete_runs_the_handler() -> None:
    """Mode A resolves ``on_complete`` off its own registry."""
    state = _State()
    runtime: WasmRuntime[_State] = WasmRuntime(
        state, _pin_view, WasmTransport(lambda _patches: None)
    )
    runtime.start()

    await runtime.dispatch_event(_complete("code", "9999"))

    assert state.log == ["complete:9999"]


@pytest.mark.asyncio
async def test_complete_payload_coerces_to_a_submit_event() -> None:
    """The handler reads ``event.values``, not the raw payload dict."""
    seen: list[object] = []

    def view(app: App[_State]) -> Widget:
        def completed(event: SubmitEvent) -> None:
            seen.append(event)

        return PinInput(key="code", length=CODE_LENGTH, on_complete=completed)

    runtime: WasmRuntime[_State] = WasmRuntime(
        _State(), view, WasmTransport(lambda _patches: None)
    )
    runtime.start()
    await runtime.dispatch_event(_complete("code", "4321"))

    assert len(seen) == 1
    assert isinstance(seen[0], SubmitEvent)
    assert seen[0].values == {"value": "4321"}


@pytest.mark.asyncio
async def test_mode_b_validate_runs_the_validators_and_shows_the_error() -> None:
    """Leaving a field validates it, and the message lands on the field."""
    state = _State()
    session: AppSession[_State] = AppSession(
        lambda: state, _field_view, _StubTransport()
    )
    await session.start()

    await session.dispatch(_validate("f-email", "email", "nope"))
    await asyncio.sleep(0)

    assert state.log == ["validate:email"]
    assert state.error == "E-mail inválido"
    scene = session.app.current_tree if session.app is not None else None
    assert scene is not None
    assert scene.root.children[0].props["error"] == "E-mail inválido"

    await session.dispatch(_validate("f-email", "email", "me@example.com"))
    await asyncio.sleep(0)
    assert state.error == "", "a valid value clears the message"
    await session.close()


@pytest.mark.asyncio
async def test_mode_a_validate_runs_the_handler() -> None:
    """Mode A routes ``validate`` the same way."""
    state = _State()
    runtime: WasmRuntime[_State] = WasmRuntime(
        state, _field_view, WasmTransport(lambda _patches: None)
    )
    runtime.start()

    await runtime.dispatch_event(_validate("f-email", "email", "bad"))
    await asyncio.sleep(0)

    assert state.error == "E-mail inválido"


@pytest.mark.asyncio
async def test_validate_payload_coerces_to_a_validation_event() -> None:
    """The handler reads ``event.field`` / ``event.value``, typed."""
    seen: list[object] = []

    def view(app: App[_State]) -> Widget:
        def validate(event: ValidationEvent) -> None:
            seen.append(event)

        return FormField(
            key="f",
            name="cpf",
            child=Input(key="in", value=""),
            on_validate=validate,
        )

    runtime: WasmRuntime[_State] = WasmRuntime(
        _State(), view, WasmTransport(lambda _patches: None)
    )
    runtime.start()
    await runtime.dispatch_event(_validate("f", "cpf", "123"))

    assert len(seen) == 1
    assert isinstance(seen[0], ValidationEvent)
    assert seen[0].field == "cpf"
    assert seen[0].value == "123"


@pytest.mark.asyncio
async def test_a_field_with_no_handler_ignores_the_event() -> None:
    """Reporting the occasion must not raise when nobody declared a handler."""
    session: AppSession[_State] = AppSession(
        lambda: _State(),
        lambda app: FormField(key="f", name="x", child=Input(key="in", value="")),
        _StubTransport(),
    )
    await session.start()

    await session.dispatch(_validate("f", "x", "anything"))
    await session.close()
