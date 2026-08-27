"""What the user's machine is, for an app that adapts quality to it (R5).

tempestweb knows how to measure the **server** (:mod:`tempestweb.observability`)
and how to measure itself in CI (``benchmarks/perf_gate.py``). It knew nothing
about the machine the app is actually running on — and that is what decides
whether to compress a photo harder, cache less, or give up on running an ONNX
model locally.

This family is deliberately **only hardware**. Connection type and storage usage
are not here, because they already exist and duplicating them would give the
same fact two names in the wire contract:

| You want | Ask |
| --- | --- |
| memory, cores, JS heap | :func:`profile` |
| connection, ``save_data``, downlink, RTT | :func:`tempestweb.native.network.state` |
| bytes used and quota | :func:`tempestweb.native.quota.estimate` |

Example:
    ```python
    from tempestweb import native


    async def choose_quality() -> int:
        profile = await native.device.profile()
        if profile.memory_gb is not None and profile.memory_gb <= 2:
            return 60
        network = await native.network.state()
        if network.save_data or network.effective_type in {"slow-2g", "2g", "3g"}:
            return 70
        return 85
    ```

!!! danger "Every field is optional, and `None` does not mean 'weak'"
    ``navigator.deviceMemory`` and ``performance.memory`` are Chromium-only. On
    Safari and Firefox this call succeeds and answers ``None`` for most of it.
    An app that reads ``None`` as "weak device" degrades **every iPhone** to its
    worst quality tier — which is the opposite of what adapting was for. Branch
    on a known value, and let the unknown fall through to your default.

!!! warning "This is for adapting quality, not for identifying anyone"
    Memory, core count and heap are coarse on purpose and are exposed here to
    pick a compression level, not to build a fingerprint. Do not send this
    anywhere as an identifier.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tempestweb.native.dispatch import send_native_call

__all__ = [
    "DeviceProfile",
    "profile",
]


@dataclass(frozen=True)
class DeviceProfile:
    """A coarse description of the machine the app is running on.

    Attributes:
        memory_gb: Approximate device RAM in gigabytes, from
            ``navigator.deviceMemory``. Quantized to a power of two, and the
            browser may cap it — measured at 32 on Chrome 150, while older
            Chromium capped at 8. So compare with ``<=`` against a low threshold
            rather than testing for an exact figure. ``None`` outside Chromium.
        cores: Logical processors, from ``navigator.hardwareConcurrency``. The
            most widely available of the three.
        heap_used_mb: JS heap currently used, from ``performance.memory``.
            Chromium-only, and only a hint — it says nothing about what the tab
            is allowed to grow to.
        heap_limit_mb: The heap ceiling the browser will enforce, same source.
            The pair is what tells an app it is near the edge, rather than
            merely large.
    """

    memory_gb: float | None = None
    cores: int | None = None
    heap_used_mb: float | None = None
    heap_limit_mb: float | None = None


async def profile() -> DeviceProfile:
    """Read what the browser will say about this machine.

    Never raises for missing APIs: a browser that exposes none of them answers a
    profile of all ``None``. That is a working answer — "I do not know" — and an
    app that adapts quality has a default to fall back to. Raising would make the
    common case on Safari an error path.

    Returns:
        The :class:`DeviceProfile`, with ``None`` wherever the browser declined
        to say.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("device.profile", {})
    return DeviceProfile(
        memory_gb=_number(value.get("memory_gb")),
        cores=_count(value.get("cores")),
        heap_used_mb=_number(value.get("heap_used_mb")),
        heap_limit_mb=_number(value.get("heap_limit_mb")),
    )


def _number(value: Any) -> float | None:  # noqa: ANN401 — a browser payload is any JSON value
    """Read an optional number out of a browser payload.

    Args:
        value: The raw value.

    Returns:
        The number, or ``None`` when the browser omitted it or sent something
        that is not one. ``bool`` is rejected explicitly: it is an ``int`` in
        Python, and a ``memory_gb`` of ``True`` would become 1 GB.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _count(value: Any) -> int | None:  # noqa: ANN401 — a browser payload is any JSON value
    """Read an optional whole count out of a browser payload.

    Args:
        value: The raw value.

    Returns:
        The count, or ``None`` when absent or not a number.
    """
    number = _number(value)
    return None if number is None else int(number)
