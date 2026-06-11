"""Guard the Mode A bootstrap's static contracts in CI (no Pyodide needed).

``public/index.html`` is a no-build-step bootstrap: it cannot be type-checked or
imported by the gate, so two of its load-bearing assumptions are only validated
here.

#. The committed ``public/manifest.json`` must list **exactly** the files
   ``gen_manifest.collect()`` walks. If it drifts, the bootstrap fails to write a
   module into Pyodide's FS and crashes at import time in the browser — invisible
   to the rest of the suite. This is the regression that shipped a manifest
   missing ``tempestweb/runtime/wasm_main.py``.
#. The Python symbols ``index.html`` reaches for must exist with the shape it
   expects: the app module exposes ``make_state``/``view`` and the bootstrap
   returns a handle exposing ``initial_node_json``/``push_event_json``/``close``.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path
from types import ModuleType
from typing import Any

#: Repo root (``tests/unit/`` is two levels below it).
ROOT = Path(__file__).resolve().parent.parent.parent


def _load_gen_manifest() -> ModuleType:
    """Import ``public/gen_manifest.py`` as a module by file path.

    ``public/`` is not an importable package (it has no ``__init__.py`` and is
    not on ``sys.path``), so the generator is loaded directly from its file.

    Returns:
        The imported ``gen_manifest`` module.

    Raises:
        ImportError: If the module spec cannot be built or executed.
    """
    path = ROOT / "public" / "gen_manifest.py"
    spec = importlib.util.spec_from_file_location("gen_manifest", path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load gen_manifest from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_manifest_matches_collect() -> None:
    """The committed manifest equals ``gen_manifest.collect()`` exactly.

    Catches the drift class that shipped a manifest missing
    ``tempestweb/runtime/wasm_main.py``: if this fails, run
    ``python public/gen_manifest.py`` and commit the result.
    """
    gen_manifest = _load_gen_manifest()
    expected: list[str] = gen_manifest.collect()
    committed: list[str] = json.loads((ROOT / "public" / "manifest.json").read_text())
    assert committed == expected


def test_app_module_exposes_bootstrap_entrypoints() -> None:
    """``examples.counter.app`` exposes ``make_state``/``view`` as ``index.html`` calls.

    The bootstrap runs ``app_mod.make_state()`` and passes ``app_mod.view`` into
    ``bootstrap``; both must be callables on the module.
    """
    import examples.counter.app as app_mod

    assert callable(app_mod.make_state)
    assert callable(app_mod.view)
    # The bootstrap calls make_state() with no args and feeds view a single arg.
    assert inspect.signature(app_mod.make_state).parameters == {}
    state: Any = app_mod.make_state()
    assert state is not None


def test_wasm_app_handle_exposes_js_contract() -> None:
    """``WasmAppHandle`` exposes the methods ``index.html`` drives over the FFI.

    JS reads ``initial_node_json()``, feeds events via ``push_event_json`` and
    tears down with ``close``. Guard their presence so a rename breaks the gate
    rather than only the live browser path.
    """
    from tempestweb.runtime import WasmAppHandle, bootstrap

    for name in ("initial_node_json", "push_event_json", "close"):
        assert callable(getattr(WasmAppHandle, name)), name
    assert callable(bootstrap)
    # index.html calls handle(on_patches, window.__tempestweb_native__), so the
    # bootstrap must accept the optional native ``dispatch`` arg as its 4th param.
    params = list(inspect.signature(bootstrap).parameters)
    assert params[:4] == ["state", "view", "on_patches", "dispatch"]
    assert inspect.signature(bootstrap).parameters["dispatch"].default is None
