"""Native Web Audio capabilities: a beep, a whole phrase, and a level meter (T24).

Three shapes, in increasing order of what they can say:

* :func:`tone` — the one-shot beep from N1. One frequency, one duration, its own
  ``AudioContext``. Unchanged: an app that only needs a click keeps paying for
  nothing more.
* :func:`sequence` — a **phrase** scheduled in one call. Every :class:`Step` gets
  its own oscillator and gain on a shared master bus, starting at ``start_ms``
  from now, with an attack/release envelope. Steps may overlap, which is how a
  chord is written.
* :func:`watch_levels` — an ``AnalyserNode`` streaming :class:`Level` frames
  (``rms``, ``peak``, and a coarse spectrum) from either the shared bus
  (``"output"``) or the microphone (``"mic"``).

**Why a phrase and not a node graph.** In Mode B every capability call is a
round-trip, so an API shaped like Web Audio's own node graph would put the
network between an oscillator and its gain. What an app needs from "beyond a
single tone" is *scheduling* and *shaping*, and both are per-phrase — so the
phrase is the unit that crosses the wire.

Metering ``"output"`` needs no microphone and no permission prompt: the analyser
taps the same bus the synthesis writes to, so a VU meter over the app's own audio
works everywhere the Web Audio API does.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from pydantic import BaseModel, ConfigDict, Field

from tempestweb.native.dispatch import native_events, send_native_call

__all__ = [
    "Level",
    "SequenceResult",
    "Step",
    "sequence",
    "stop",
    "tone",
    "watch_levels",
]


class Step(BaseModel):
    """One note in a phrase.

    Attributes:
        frequency: The pitch in hertz.
        duration_ms: How long the note sounds.
        start_ms: How long after the call the note starts — overlap two steps by
            giving them the same ``start_ms``, which is how a chord is written.
        type: The oscillator waveform (``"sine"``, ``"square"``, ``"sawtooth"``,
            ``"triangle"``).
        gain: The note's peak gain, from ``0.0`` (silent) to ``1.0`` (full).
        attack_ms: Ramp-up from silence to ``gain``. A note that jumps straight to
            full amplitude clicks, because the waveform starts mid-cycle.
        release_ms: Ramp-down back to silence, for the same reason.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    frequency: float = Field(default=440.0, gt=0.0)
    duration_ms: int = Field(default=200, ge=0)
    start_ms: int = Field(default=0, ge=0)
    type: str = "sine"
    gain: float = Field(default=0.5, ge=0.0, le=1.0)
    attack_ms: int = Field(default=5, ge=0)
    release_ms: int = Field(default=40, ge=0)


class SequenceResult(BaseModel):
    """What the client scheduled.

    Attributes:
        scheduled: How many steps were scheduled.
        ends_in_ms: When the last step ends, measured from the call.
        blocked: Whether the audio context is still suspended — the browser blocks
            audio until the first user gesture, and the phrase stays scheduled
            rather than raising, mirroring ``audio.play``.
    """

    model_config = ConfigDict(frozen=True)

    scheduled: int = 0
    ends_in_ms: int = 0
    blocked: bool = False


class Level(BaseModel):
    """One analysis frame.

    Attributes:
        rms: Loudness over the frame's samples, ``0.0``–``1.0``.
        peak: The loudest single sample in the frame, ``0.0``–``1.0``.
        bands: The frequency bins averaged into buckets, each ``0.0``–``1.0``,
            low frequencies first.
    """

    model_config = ConfigDict(frozen=True)

    rms: float = 0.0
    peak: float = 0.0
    bands: list[float] = Field(default_factory=list)


async def tone(
    frequency: float = 440.0,
    duration_ms: int = 200,
    type: str = "sine",
    volume: float = 0.5,
) -> None:
    """Play a single synthesized tone.

    Args:
        frequency: The tone frequency in hertz (defaults to 440 Hz, concert A).
        duration_ms: How long the tone plays, in milliseconds.
        type: The oscillator waveform (``"sine"``, ``"square"``, ``"sawtooth"``,
            ``"triangle"``).
        volume: The gain, from ``0.0`` (silent) to ``1.0`` (full).

    Raises:
        NativeError: If the Web Audio API is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call(
        "webaudio.tone",
        {
            "frequency": frequency,
            "duration_ms": duration_ms,
            "type": type,
            "volume": volume,
        },
    )


async def sequence(steps: Sequence[Step]) -> SequenceResult:
    """Schedule a phrase — every step in a single call.

    Args:
        steps: The notes to schedule. An empty sequence is a no-op that still
            reports what it scheduled (zero), so a caller driving this from state
            needs no special case.

    Returns:
        The :class:`SequenceResult` the client reports.

    Raises:
        NativeError: If the Web Audio API is unavailable (``unavailable``) or the
            scheduling itself fails (``failed``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call(
        "webaudio.sequence",
        {"steps": [step.model_dump() for step in steps]},
    )
    return SequenceResult.model_validate(value or {})


async def stop() -> int:
    """Stop every step still scheduled or sounding.

    The shared context stays open — a closed ``AudioContext`` cannot be reopened,
    and the next phrase would pay for a new one.

    Returns:
        How many oscillators were stopped.

    Raises:
        NativeError: If the Web Audio API is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("webaudio.stop", {})
    return int((value or {}).get("stopped", 0))


async def watch_levels(
    source: str = "output",
    interval_ms: int = 100,
    bands: int = 8,
) -> AsyncIterator[Level]:
    """Stream loudness and a coarse spectrum (event channel / T-EV).

    Consume it like any other watch::

        async for level in webaudio.watch_levels():
            app.set_state(lambda s: setattr(s, "vu", level.rms))

    Args:
        source: ``"output"`` taps the shared synthesis bus — no microphone, no
            permission prompt; ``"mic"`` opens ``getUserMedia({audio: true})``.
        interval_ms: How often a frame is emitted (floored at one animation frame,
            ~16 ms, by the client).
        bands: How many buckets the frequency bins are averaged into.

    Yields:
        Each :class:`Level` frame.

    Raises:
        NativeError: If the Web Audio API is unavailable (``unavailable``), or the
            microphone is refused (``permission_denied``).
        BrowserUnavailableError: If no bridge is installed, or the installed bridge
            does not support the event channel.
    """
    args = {"source": source, "interval_ms": interval_ms, "bands": bands}
    async for value in native_events("webaudio.levels", args):
        yield Level.model_validate(value)
