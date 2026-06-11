"""Tests for the dev HTTP server — static serving + browser livereload (Mode A).

Covers :func:`~tempestweb.devserver.http.create_dev_app`: that a static-only app
serves the bundle untouched, that a livereload-enabled app injects the snippet
and serves it, and that the ``/__livereload`` SSE stream emits a ``reload`` event
when the shared signal is triggered. Drives the app with Starlette's
:class:`~starlette.testclient.TestClient` so no socket is opened.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from starlette.testclient import TestClient

from tempestweb.devserver import (
    ReloadSignal,
    create_dev_app,
    inject_livereload,
    livereload_frames,
)


def _bundle(tmp_path: Path) -> Path:
    """Write a minimal artifact dir (index.html + one asset) and return it."""
    out = tmp_path / "dist"
    out.mkdir()
    (out / "index.html").write_text(
        "<!doctype html><html><body><div id='app'></div></body></html>",
        encoding="utf-8",
    )
    (out / "app.js").write_text("export const x = 1;\n", encoding="utf-8")
    return out


def test_inject_livereload_inserts_tag_before_body_close() -> None:
    """The snippet tag lands immediately before the closing body tag."""
    html = "<html><body><p>hi</p></body></html>"
    out = inject_livereload(html)
    assert "/__livereload.js" in out
    assert out.index("/__livereload.js") < out.index("</body>")


def test_inject_livereload_appends_when_no_body() -> None:
    """A fragment with no body tag still gets the snippet appended."""
    out = inject_livereload("<div>fragment</div>")
    assert out.rstrip().endswith("</script>")


def test_static_only_app_serves_index_untouched(tmp_path: Path) -> None:
    """Without a signal the app is a plain static host — no injection."""
    out = _bundle(tmp_path)
    client = TestClient(create_dev_app(out))

    index = client.get("/")
    assert index.status_code == 200
    assert "/__livereload.js" not in index.text

    asset = client.get("/app.js")
    assert asset.status_code == 200
    assert "export const x" in asset.text

    # The livereload endpoints are not registered in static-only mode.
    assert client.get("/__livereload.js").status_code == 404


def test_dev_app_injects_and_serves_livereload(tmp_path: Path) -> None:
    """With a signal the index is injected and the snippet is served."""
    out = _bundle(tmp_path)
    signal = ReloadSignal()
    client = TestClient(create_dev_app(out, signal))

    index = client.get("/")
    assert index.status_code == 200
    assert "/__livereload.js" in index.text

    snippet = client.get("/__livereload.js")
    assert snippet.status_code == 200
    assert "EventSource" in snippet.text
    assert "application/javascript" in snippet.headers["content-type"]


def test_livereload_route_registered_only_in_dev(tmp_path: Path) -> None:
    """The ``/__livereload`` route exists with a signal, absent without one.

    The route's streaming behavior (open comment + a reload per trigger) is
    covered by :func:`test_livereload_frames_emits_reload_on_trigger` against the
    generator directly — consuming the never-ending HTTP stream would block the
    sync test client.
    """
    out = _bundle(tmp_path)

    def paths(app: object) -> set[str]:
        return {getattr(route, "path", "") for route in app.routes}  # type: ignore[attr-defined]

    dev_paths = paths(create_dev_app(out, ReloadSignal()))
    assert "/__livereload" in dev_paths
    assert "/__livereload.js" in dev_paths

    static_paths = paths(create_dev_app(out))
    assert "/__livereload" not in static_paths


async def test_livereload_frames_emits_reload_on_trigger() -> None:
    """The frame generator yields the open comment, then a reload per trigger.

    Drives the generator directly (no HTTP), so the ``signal.trigger`` runs on
    the same loop as the parked ``signal.wait`` — no cross-thread future hazard
    and no never-ending HTTP stream to time out on.
    """
    signal = ReloadSignal()
    frames = livereload_frames(signal)

    assert await anext(frames) == ": connected\n\n"

    # Park a consumer on the next frame, trigger, then read what it produced.
    pending = asyncio.ensure_future(anext(frames))
    await asyncio.sleep(0)  # let the generator reach `await signal.wait()`
    event = signal.trigger(paths=["app.py"])
    frame = await asyncio.wait_for(pending, 1.0)
    assert frame == f"event: reload\ndata: {event.generation}\n\n"

    await frames.aclose()
