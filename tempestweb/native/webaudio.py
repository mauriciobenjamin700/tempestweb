"""Native Web Audio tone-generation capability over the Web Audio API.

:func:`tone` sends a ``webaudio.tone`` ``native_call``; ``client/native/
webaudio.js`` builds an ``OscillatorNode`` through an ``AudioContext`` and plays a
single tone of the given frequency, duration, waveform, and volume. It is the
lightweight "beep" primitive that does not require an audio asset (unlike
``audio.play``).
"""

from __future__ import annotations

from tempestweb.native.dispatch import send_native_call

__all__ = ["tone"]


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
