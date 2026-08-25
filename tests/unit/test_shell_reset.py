"""Every generated shell zeroes the body margin.

A user agent gives ``body`` an 8px margin. The SSR path always said otherwise
(``render_document`` ships a reset); the three shells the build emits did not, so
every built app carried 8px of dead space it never asked for — and an app that
bounds a frame to ``media.height`` carried worse: the frame fills the viewport,
the margin pushes the document 16px past it, and the bars a ``Scaffold`` holds
still drift with the page scroll instead. Measured on a real app before this,
``scrollHeight - clientHeight`` was exactly 16.

One test per mode, because the three templates are three strings: the one that
was fixed and the two that were not is exactly the shape this repo has shipped
before (the SSR renderer sat five widgets behind the client in 0.98.0).
"""

from __future__ import annotations

import pytest

from tempestweb.cli.commands.build import (
    _index_html,
    _index_html_server,
    _index_html_transpile,
)

RESET: str = "body{margin:0}"
"""The declaration whose absence is the defect."""


def test_the_server_shell_carries_the_reset() -> None:
    """Mode B: the shell the SDK serves for a bounded frame."""
    assert RESET in _index_html_server("demo")


@pytest.mark.parametrize("dev", [False, True])
def test_the_wasm_shell_carries_the_reset(dev: bool) -> None:
    """Mode A, in both its flavours.

    Args:
        dev: Whether the dev cache-kill switch is in the shell.
    """
    html = _index_html(
        "demo",
        theme_color="#1c4ab0",
        dev=dev,
        with_manifest=True,
        with_service_worker=True,
    )

    assert RESET in html


@pytest.mark.parametrize("dev", [False, True])
def test_the_transpile_shell_carries_the_reset(dev: bool) -> None:
    """Mode C, in both its flavours.

    Args:
        dev: Whether the dev cache-kill switch is in the shell.
    """
    html = _index_html_transpile(
        "demo",
        theme_color="#1c4ab0",
        dev=dev,
        with_manifest=True,
        with_service_worker=True,
    )

    assert RESET in html


def test_the_reset_is_in_the_head_before_the_app_paints() -> None:
    """A reset that lands after the first paint is a flash, not a reset."""
    html = _index_html_server("demo")

    assert html.index(RESET) < html.index("<body>")
