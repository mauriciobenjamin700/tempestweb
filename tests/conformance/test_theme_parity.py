"""The same view under the same ``THEME`` renders the same in all three modes.

An app declares its palette once, as a module-level ``THEME``. Mode A reads it at
``bootstrap``, Mode B at ``create_app``, and Mode C read nothing at all — so the
same screen was legible on the server and unreadable transpiled: a breadcrumb at
1.20:1, a section title at 1.02:1 (tempestweb#206).

The defect has two halves that fail independently, and both are pinned here:

* the **attribute** — ``data-tw-theme`` on the document, which is what the base
  stylesheet keys the page background, a field's surface and every hover/focus
  state on. A first ``light`` is deliberately not reported: the sheet's own
  tokens *are* the light palette.
* the **colours** — every widget carries its fill inline, resolved from the
  theme at build time, so the IR itself is the evidence.

``tests/fixtures/transpile_theme_samples.json`` holds both, built from the real
core. This module holds Modes A and B to it; ``tests/client/transpile-theme.test.js``
holds Mode C to the same file. Three readers, one golden.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from tempest_core import Theme
from tempestweb.runtime import AppSession, WasmRuntime
from tests.conformance import _transpile_theme as theme_gen

FIXTURE: Path = (
    Path(__file__).resolve().parents[1] / "fixtures" / "transpile_theme_samples.json"
)


class ThemeRecordingTransport:
    """A :class:`~tempestweb.transports.base.PatchTransport` double that records.

    Only two sinks matter to this suite: the patch batches (the initial one
    carries the whole tree) and the theme modes. Everything else is a no-op.
    """

    def __init__(self) -> None:
        """Start with empty logs."""
        self.patches: list[list[dict[str, Any]]] = []
        self.modes: list[str] = []

    async def send_patches(self, patches: list[dict[str, Any]]) -> None:
        """Record one patch batch.

        Args:
            patches: The wire patches for this tick.
        """
        self.patches.append(patches)

    async def send_navigate(self, path: str) -> None:
        """Ignore a navigation.

        Args:
            path: The new top-route path.
        """
        return None

    async def send_theme(self, mode: str) -> None:
        """Record a resolved theme mode.

        Args:
            mode: ``"light"`` or ``"dark"``.
        """
        self.modes.append(mode)

    async def send_native_call(
        self, call_id: str, capability: str, args: dict[str, Any]
    ) -> None:
        """Ignore a native call.

        Args:
            call_id: Correlation id.
            capability: Capability name.
            args: Capability arguments.
        """
        return None

    async def send_native_subscribe(
        self, sub_id: str, capability: str, args: dict[str, Any]
    ) -> None:
        """Ignore a native subscription.

        Args:
            sub_id: Subscription id.
            capability: Capability name.
            args: Capability arguments.
        """
        return None

    async def send_native_unsubscribe(self, sub_id: str) -> None:
        """Ignore a native unsubscription.

        Args:
            sub_id: Subscription id.
        """
        return None

    async def recv_event(self) -> dict[str, Any]:
        """Never deliver an event.

        Returns:
            Never returns: the suite only exercises the mount.
        """
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    def on_event(self, handler: Any) -> None:  # noqa: ANN401 — test double sink
        """Ignore the event sink.

        Args:
            handler: The sink.
        """
        return None

    def on_native_result(self, handler: Any) -> None:  # noqa: ANN401 — test double sink
        """Ignore the native-result sink.

        Args:
            handler: The sink.
        """
        return None

    def on_native_event(self, handler: Any) -> None:  # noqa: ANN401 — test double sink
        """Ignore the native-event sink.

        Args:
            handler: The sink.
        """
        return None

    async def close(self) -> None:
        """Closing is a no-op for this double."""
        return None


def _attribute(modes: list[str]) -> str | None:
    """The ``data-tw-theme`` the document ends up with, given what was reported.

    The client applies each reported mode in turn; nothing reported leaves the
    document unmarked.

    Args:
        modes: The theme modes the mode reported at mount, in order.

    Returns:
        The resulting attribute value, or ``None``.
    """
    return modes[-1] if modes else None


def _pruned(node: dict[str, Any]) -> dict[str, Any]:
    """Apply Mode B's wire pruning to a golden node.

    The wire encoder omits a falsy ``tag`` and a falsy ``attrs``: they are the
    SSR renderer's props, inert on the DOM wire, and dropping them keeps the
    payload byte-identical to what it was before the core grew them. That is an
    encoder decision, not a theme one, so the golden is normalized here instead
    of being stored twice.

    Args:
        node: A golden node in the full ``serialize_node`` shape.

    Returns:
        The same node in Mode B's wire shape.
    """
    props = {
        name: value
        for name, value in node["props"].items()
        if not (name in ("tag", "attrs") and not value)
    }
    return {
        "type": node["type"],
        "key": node["key"],
        "props": props,
        "children": [_pruned(child) for child in node["children"]],
    }


async def _settle() -> None:
    """Let a session's spawned sends run.

    The session ships every frame as a tracked task, so a test has to yield
    before reading what the transport received.
    """
    for _ in range(3):
        await asyncio.sleep(0)


def test_the_fixture_is_what_the_live_core_builds() -> None:
    """The golden is regenerable, so a core change shows up as a failure.

    Nothing else in this suite means anything if the fixture has drifted from the
    core it claims to be derived from.
    """
    on_disk = FIXTURE.read_text(encoding="utf-8")
    assert on_disk == theme_gen.render_fixture_text(), (
        "tests/fixtures/transpile_theme_samples.json is stale — regenerate with "
        "`python -m tests.conformance._transpile_theme`"
    )


@pytest.mark.parametrize("case", sorted(theme_gen.CASES))
def test_mode_a_matches_the_golden(case: str) -> None:
    """Mode A marks the same attribute and resolves the same colours.

    Args:
        case: The fixture case name (which ``THEME`` the app declares).
    """
    expected = _samples()[case]
    theme: Theme | None = theme_gen.CASES[case]
    modes: list[str] = []
    runtime: WasmRuntime[theme_gen.ThemeState] = WasmRuntime(
        theme_gen.make_state(),
        theme_gen.view,
        ThemeRecordingTransport(),  # type: ignore[arg-type]
        theme=theme,
        on_theme=modes.append,
    )
    node = runtime.start()
    assert _attribute(modes) == expected["attribute"]
    assert node == expected["node"]


@pytest.mark.parametrize("case", sorted(theme_gen.CASES))
def test_mode_b_matches_the_golden(case: str) -> None:
    """Mode B marks the same attribute and resolves the same colours.

    Args:
        case: The fixture case name (which ``THEME`` the app declares).
    """
    expected = _samples()[case]
    theme: Theme | None = theme_gen.CASES[case]
    transport = ThemeRecordingTransport()
    session: AppSession[theme_gen.ThemeState] = AppSession(
        state_factory=theme_gen.make_state,
        view=theme_gen.view,
        transport=transport,  # type: ignore[arg-type]
        theme=theme,
    )

    async def _run() -> None:
        """Mount the session and let its sends settle."""
        await session.start()
        await _settle()

    asyncio.run(_run())
    assert _attribute(transport.modes) == expected["attribute"]
    assert transport.patches[0][0]["node"] == _pruned(expected["node"])


def test_the_golden_would_notice_a_mode_that_ignored_the_theme() -> None:
    """The dark case differs from the light one, and ``no_theme`` equals light.

    Without the first assertion every mode passes by resolving light forever —
    which is exactly the bug. The second is the regression guard: reading the
    theme must not move an app that declares none.
    """
    samples = _samples()
    assert samples["dark"]["node"] != samples["light"]["node"]
    assert samples["no_theme"]["node"] == samples["light"]["node"]
    assert samples["dark"]["attribute"] == "dark"
    assert samples["no_theme"]["attribute"] is None


def _samples() -> dict[str, Any]:
    """The committed three-mode theme golden.

    Returns:
        The case name → ``{"attribute", "node"}`` map.
    """
    return dict(json.loads(FIXTURE.read_text(encoding="utf-8")))
