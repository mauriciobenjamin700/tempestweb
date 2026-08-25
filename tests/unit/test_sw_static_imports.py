"""The service worker may not use a dynamic ``import()`` — the spec forbids it.

``replayFromSync`` (``client/sw/sw.js``) drains the offline outbox on a Background
or Periodic Sync, which is the only path that empties the queue **with the tab
closed**. It used to reach its queue modules with ``await import(...)``, and no
service worker may do that: the HTML spec forbids ``import()`` on
``ServiceWorkerGlobalScope`` (w3c/ServiceWorker#1356), so every sync threw and
fell into the fallback that pings open clients — of which there are none when the
tab is closed. The queue silently stayed put.

Measured in Chrome (tempestweb#118), same procedure on two origins: with the old
worker, two mutations queued offline stayed in IndexedDB and **zero** requests
reached the server after the tab closed and connectivity returned; with static
imports, both replayed 1.01 s after the tab closed, 3 ms after reconnect, with no
page of that origin open.

The node suite cannot catch this — ``import()`` works there — so these guards read
the source and the emitted artifact instead.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tempestweb.cli import build_artifact, scaffold_project

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
SW_SOURCE: Path = REPO_ROOT / "client" / "sw" / "sw.js"

#: A dynamic import, ignoring the ones inside comments and JSDoc, which name the
#: forbidden call on purpose.
_DYNAMIC_IMPORT = re.compile(
    r"^\s*(?!//|\*)(?:[^\n]*?[^\w.])?import\s*\(", re.MULTILINE
)


def test_the_worker_source_uses_no_dynamic_import() -> None:
    """``client/sw/sw.js`` reaches its modules statically, or not at all."""
    source = SW_SOURCE.read_text(encoding="utf-8")
    offenders = [
        line
        for line in source.splitlines()
        if _DYNAMIC_IMPORT.match(line) and not line.lstrip().startswith(("//", "*"))
    ]
    assert not offenders, (
        "a service worker may not use import() — the spec forbids it on "
        f"ServiceWorkerGlobalScope, so this throws at runtime: {offenders}"
    )


def test_the_worker_source_imports_its_queue_modules_statically() -> None:
    """The drain path has the store and the queue in scope before it runs."""
    source = SW_SOURCE.read_text(encoding="utf-8")
    assert 'import { createOfflineStore } from "../offline/store.js";' in source
    assert 'import { OfflineQueue } from "../offline/sync.js";' in source


@pytest.mark.parametrize("mode", ["wasm", "transpile"])
def test_the_emitted_worker_points_at_the_artifact_layout(
    tmp_path: Path, mode: str
) -> None:
    """The build rewrites the specifiers, and ships what they point at.

    The source imports its siblings repo-relatively (``../offline/store.js``) so
    the node tests load it unchanged, but the emitted worker sits at the artifact
    root with the client under ``./client/``. An unrewritten specifier 404s at
    runtime, and a rewritten one that points at a file the build never copied does
    too — so both halves are asserted.
    """
    root = scaffold_project("swimports", parent=tmp_path).root
    out = build_artifact(root, mode=mode).out_dir
    worker = (out / "sw.js").read_text(encoding="utf-8")

    assert 'from "./client/offline/store.js"' in worker
    assert 'from "./client/offline/sync.js"' in worker
    assert 'from "../offline/' not in worker
    assert (out / "client" / "offline" / "store.js").is_file()
    assert (out / "client" / "offline" / "sync.js").is_file()
