"""Native audio capability over the browser's HTMLAudioElement (N1).

The pythonic mirror of the React SDK's ``playAudio`` / ``useAudio``. Plays short
sounds (notification/success chimes), pairing with WebPush (P3). One player per
``channel`` so a new sound on the same channel replaces the previous one.

``client/native/audio.js`` owns the per-channel ``Audio`` elements. Browsers block
autoplay until the first user gesture — :func:`play` therefore resolves with a
:class:`PlayResult` whose ``blocked`` flag is ``True`` instead of raising, so the
UI degrades gracefully (it "unlocks" on the first click).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from tempestweb.native.dispatch import send_native_call

__all__ = ["PlayResult", "play", "stop"]


class PlayResult(BaseModel):
    """The outcome of a :func:`play` call.

    Attributes:
        played: Whether playback actually started.
        blocked: Whether the browser blocked autoplay (no user gesture yet). When
            ``True``, ``played`` is ``False`` and no error is raised.
        channel: The channel the sound was routed to.
    """

    model_config = ConfigDict(frozen=True)

    played: bool
    blocked: bool = False
    channel: str = "default"


async def play(
    src: str, *, volume: float = 1.0, channel: str = "default"
) -> PlayResult:
    """Play a short sound on a channel.

    Args:
        src: URL of the audio asset (e.g. ``"/audio/plim.wav"``).
        volume: Playback volume in ``[0.0, 1.0]``.
        channel: Player channel; a new sound on the same channel replaces the
            previous one.

    Returns:
        A :class:`PlayResult`. If the browser blocked autoplay, ``blocked`` is
        ``True`` and ``played`` is ``False`` — this is not an error.

    Raises:
        NativeError: If the asset cannot be loaded (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    clamped = max(0.0, min(1.0, volume))
    value = await send_native_call(
        "audio.play", {"src": src, "volume": clamped, "channel": channel}
    )
    return PlayResult.model_validate(value)


async def stop(channel: str = "default") -> None:
    """Stop and reset playback on a channel.

    Args:
        channel: The channel to stop. A channel with nothing playing is a no-op.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call("audio.stop", {"channel": channel})
