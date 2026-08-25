"""Web Audio demo — a phrase scheduled in one call, metered by an analyser (T24).

Two capabilities, and the second one measures the first:

* ``native.webaudio.sequence([...])`` schedules a whole phrase — every note with
  its own envelope, notes sharing a ``start_ms`` sounding as a chord. One call,
  whatever the mode: in Mode B each capability call is a round-trip, so the phrase
  is the unit that crosses the wire, not the oscillator.
* ``native.webaudio.watch_levels()`` streams ``rms``/``peak``/``bands`` from the
  **shared synthesis bus** — no microphone, no permission prompt. The meter moves
  because the app itself is playing.

    tempestweb run --mode server --path examples/webaudio_demo
    tempestweb run --mode wasm --path examples/webaudio_demo

!!! check "Medido nos Modos A e B"
    Acorde reporta `3 notas juntas, 700 ms` e o medidor lê `rms 0.374 · peak 0.766`
    enquanto ele soa; `stop` devolve `parado: 2 osciladores`. O Modo C não compila
    `async for` para stream nenhuma (`statement AsyncFor is not supported`), então
    lá o medidor fica fora — `sequence` e `stop` compilam.

!!! note
    Browsers block audio until the first user gesture, so the first phrase may
    come back ``blocked=True``: the notes are scheduled, the context is suspended,
    and the next tap resumes it. The screen says which happened instead of
    pretending it played.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from tempest_core import (
    AlignItems,
    App,
    Button,
    Column,
    Edge,
    FontWeight,
    Row,
    Style,
    Text,
    Widget,
)
from tempestweb import native
from tempestweb.runtime import spawn

#: A C-major triad, in hertz.
CHORD: tuple[float, ...] = (261.63, 329.63, 392.00)

#: A short rising arpeggio, in hertz.
ARPEGGIO: tuple[float, ...] = (261.63, 329.63, 392.00, 523.25)


@dataclass
class AudioState:
    """What the screen holds.

    Attributes:
        status: What the last capability call reported.
        rms: The most recent loudness frame, ``0.0``–``1.0``.
        peak: The most recent peak frame.
        bands: The most recent coarse spectrum.
        metering: Whether the analyser subscription is open.
    """

    status: str = "idle"
    rms: float = 0.0
    peak: float = 0.0
    bands: list[float] = field(default_factory=list)
    metering: bool = False


def _absorber(level: native.webaudio.Level) -> Callable[[AudioState], None]:
    """Build the mutation that folds one analysis frame into the state.

    A factory rather than a closure over the loop variable: a lambda written
    inside the ``async for`` would capture the *name*, and every deferred mutation
    would read whichever frame arrived last.

    Args:
        level: The frame the analyser emitted.

    Returns:
        The mutation ``set_state`` applies.
    """

    def mutate(state: AudioState) -> None:
        state.rms = level.rms
        state.peak = level.peak
        state.bands = level.bands

    return mutate


def make_state() -> AudioState:
    """Build the initial state.

    Returns:
        A fresh :class:`AudioState`.
    """
    return AudioState()


def view(app: App[AudioState]) -> Widget:
    """Render the demo screen.

    Args:
        app: The application handle.

    Returns:
        The widget tree for the current state.
    """

    def report(text: str) -> None:
        """Show what the last call reported.

        Args:
            text: The line to display.
        """
        app.set_state(lambda state: setattr(state, "status", text))

    async def play_arpeggio() -> None:
        """Schedule four rising notes, 120 ms apart."""
        result = await native.webaudio.sequence(
            [
                native.webaudio.Step(
                    frequency=frequency,
                    duration_ms=180,
                    start_ms=index * 120,
                    gain=0.4,
                )
                for index, frequency in enumerate(ARPEGGIO)
            ]
        )
        report(
            f"arpeggio: {result.scheduled} notas, acaba em {result.ends_in_ms} ms"
            + (" (bloqueado até o próximo toque)" if result.blocked else "")
        )

    async def play_chord() -> None:
        """Schedule three notes at once — same ``start_ms`` is a chord."""
        result = await native.webaudio.sequence(
            [
                native.webaudio.Step(
                    frequency=frequency,
                    duration_ms=700,
                    start_ms=0,
                    gain=0.3,
                    attack_ms=30,
                    release_ms=250,
                )
                for frequency in CHORD
            ]
        )
        report(f"acorde: {result.scheduled} notas juntas, {result.ends_in_ms} ms")

    async def hush() -> None:
        """Cut everything still sounding."""
        stopped = await native.webaudio.stop()
        report(f"parado: {stopped} osciladores")

    async def meter() -> None:
        """Meter the synthesis bus for as long as the subscription lives.

        The handler *is* the task: an async handler that loops keeps the
        subscription open, which is the documented streaming idiom and the one the
        Mode C compiler understands — it maps the ``async for`` onto the facade's
        own teardown-returning ``watch_levels``.
        """
        app.set_state(lambda state: setattr(state, "metering", True))
        try:
            async for level in native.webaudio.watch_levels(interval_ms=100, bands=8):
                app.set_state(_absorber(level))
        finally:
            app.set_state(lambda state: setattr(state, "metering", False))

    def start_meter() -> None:
        """Hand the subscription to the session, instead of holding the dispatch.

        Both modes read events **in series**, so an ``async for`` awaited inline in
        a handler starves every later event — measured in Mode A: after clicking
        this, no further click reported anything. ``spawn`` is the documented way
        out, and the session owns the task, so it dies with the page.
        """
        spawn(meter())

    bars = Row(
        key="bars",
        style=Style(gap=4.0, align=AlignItems.END),
        children=[
            Text(
                content="▇",
                key=f"band-{index}",
                style=Style(font_size=8.0 + value * 28.0),
            )
            for index, value in enumerate(app.state.bands or [0.0] * 8)
        ],
    )

    return Column(
        key="body",
        style=Style(gap=16.0, padding=Edge.all(20.0)),
        children=[
            Text(
                content="Web Audio: uma frase por chamada, medida pelo analisador",
                key="title",
                style=Style(font_size=18.0, font_weight=FontWeight.BOLD),
            ),
            Row(
                key="controls",
                style=Style(gap=8.0),
                children=[
                    Button(label="Arpejo", key="arpeggio", on_click=play_arpeggio),
                    Button(label="Acorde", key="chord", on_click=play_chord),
                    Button(label="Parar", key="hush", on_click=hush),
                    Button(
                        label="Medir a saída" if not app.state.metering else "Medindo…",
                        key="meter",
                        on_click=start_meter,
                    ),
                ],
            ),
            Text(content=app.state.status, key="status"),
            Text(
                content=f"rms {app.state.rms:.3f} · peak {app.state.peak:.3f}",
                key="levels",
            ),
            bars,
        ],
    )
