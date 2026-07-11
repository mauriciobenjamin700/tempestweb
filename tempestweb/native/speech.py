"""Native text-to-speech capability over the Web Speech (SpeechSynthesis) API.

:func:`speak` sends a ``speech.speak`` ``native_call``, :func:`cancel` a
``speech.cancel``, and :func:`voices` a ``speech.voices``;
``client/native/speech.js`` drives ``window.speechSynthesis`` and
``SpeechSynthesisUtterance``. Speech recognition (STT) is a continuous stream and
is deferred to the event channel rather than modeled as a request/response call.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from tempestweb.native.dispatch import native_events, send_native_call

__all__ = ["SpeechResult", "Voice", "cancel", "listen", "speak", "voices"]


class SpeechResult(BaseModel):
    """A speech-recognition (STT) result from the Web Speech API.

    Attributes:
        transcript: The recognized text for this result.
        is_final: Whether this is a finalized result (``True``) or an interim,
            still-changing hypothesis (``False``).
        confidence: The recognizer's confidence in the transcript, ``0.0``-``1.0``.
    """

    model_config = ConfigDict(frozen=True)

    transcript: str
    is_final: bool
    confidence: float


@dataclass(frozen=True)
class Voice:
    """A speech-synthesis voice available in the browser.

    Attributes:
        name: The human-readable voice name (e.g. ``"Google US English"``).
        lang: The BCP-47 language tag the voice speaks (e.g. ``"en-US"``).
        default: Whether this is the browser's default voice.
    """

    name: str
    lang: str
    default: bool


async def speak(
    text: str,
    *,
    lang: str = "",
    rate: float = 1.0,
    pitch: float = 1.0,
    volume: float = 1.0,
) -> None:
    """Speak text aloud using the browser's speech synthesizer.

    Args:
        text: The text to speak.
        lang: The BCP-47 language tag to speak in; the browser default when empty.
        rate: The speaking rate (``0.1``–``10``, ``1.0`` is normal).
        pitch: The speaking pitch (``0``–``2``, ``1.0`` is normal).
        volume: The speaking volume (``0``–``1``, ``1.0`` is loudest).

    Raises:
        NativeError: If speech synthesis is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call(
        "speech.speak",
        {
            "text": text,
            "lang": lang,
            "rate": rate,
            "pitch": pitch,
            "volume": volume,
        },
    )


async def cancel() -> None:
    """Cancel any in-progress and queued speech.

    Raises:
        NativeError: If speech synthesis is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call("speech.cancel", {})


async def voices() -> list[Voice]:
    """List the speech-synthesis voices the browser offers.

    Returns:
        The available voices (an empty list when none are installed).

    Raises:
        NativeError: If speech synthesis is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("speech.voices", {})
    return [
        Voice(
            name=str(v.get("name", "")),
            lang=str(v.get("lang", "")),
            default=bool(v.get("default", False)),
        )
        for v in value.get("voices", [])
    ]


async def listen(lang: str = "", interim: bool = True) -> AsyncIterator[SpeechResult]:
    """Stream speech-recognition results from the browser (event channel / T-EV).

    Opens a ``SpeechRecognition`` session and yields a fresh :class:`SpeechResult`
    for every interim and final result until the ``async for`` loop is exited
    (which stops recognition). Consume it with::

        async for result in native.speech.listen(lang="en-US"):
            if result.is_final:
                app.set_state(lambda s: setattr(s, "said", result.transcript))

    Args:
        lang: The BCP-47 language tag to recognize; the browser default when empty.
        interim: Whether to emit interim (non-final) results as they change.

    Yields:
        Each :class:`SpeechResult`.

    Raises:
        NativeError: If the browser reports the subscription failed (e.g.
            ``permission_denied`` or ``unavailable``).
        BrowserUnavailableError: If no bridge is installed, or the installed bridge
            does not support the event channel.
    """
    args = {"lang": lang, "interim": interim}
    async for value in native_events("speech.listen", args):
        yield SpeechResult.model_validate(value)
