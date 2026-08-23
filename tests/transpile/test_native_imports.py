"""Every Python spelling of a native capability lands on the same facade.

``from tempestweb import native``, ``from tempestweb.native import get_position``
and ``from tempestweb.native.geolocation import get_position`` are one import in
Python and were three different answers in Mode C: only the first compiled, and
the diagnostic for the other two listed ``tempestweb.native`` among the modules
it allowed. These tests fix the mapping, the refusals that teach, and the
manifest the mapping reads.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tempestweb.transpile import TranspileError, transpile_source
from tempestweb.transpile._native import (
    NATIVE_ENUMS,
    NATIVE_EXPORTS,
    NATIVE_FLAT,
    NATIVE_MEMBERS,
)
from tests.conformance import _transpile_native as native_gen

BARE = ""


def gen(source: str) -> str:
    """Transpile `source` with an empty banner, returning the JS body.

    Args:
        source: The Python module source.

    Returns:
        The generated JavaScript, stripped.
    """
    return transpile_source(source, banner=BARE).strip()


def test_the_native_manifest_matches_the_client_and_the_package() -> None:
    """The shipped manifest byte-matches a fresh render.

    The compiler maps an import onto the facade from this manifest, so a stale
    one either refuses a capability that exists or emits a call to a member the
    browser does not have.
    """
    if shutil.which("node") is None:
        pytest.skip("node is required to introspect the native facade")
    on_disk = native_gen.NATIVE_MODULE.read_text(encoding="utf-8")
    assert on_disk == native_gen.render_module_text(), (
        "tempestweb/transpile/_native.py is stale — regenerate with "
        "`python -m tests.conformance._transpile_native`"
    )


def test_the_manifest_only_claims_members_the_facade_has() -> None:
    """Every flat name resolves to a member of the group it names."""
    for name, path in NATIVE_FLAT.items():
        group, member = path.split(".")
        assert member in NATIVE_MEMBERS[group], f"{name} -> {path} is not served"


def test_both_import_forms_reach_the_same_facade_call() -> None:
    """The namespace form and the flat form emit the same capability call."""
    namespace = gen(
        "from tempestweb import native\n\n"
        "async def f():\n    return await native.geolocation.get_position()\n"
    )
    flat = gen(
        "from tempestweb.native import get_position\n\n"
        "async def f():\n    return await get_position()\n"
    )
    grouped = gen(
        "from tempestweb.native.geolocation import get_position\n\n"
        "async def f():\n    return await get_position()\n"
    )
    assert 'from "./native.js"' in namespace
    assert "native.geolocation.get_position()" in namespace
    for js in (flat, grouped):
        assert 'import { native as native$ } from "./native.js";' in js
        assert "native$.geolocation.get_position()" in js


def test_a_group_import_binds_the_namespace_object() -> None:
    """`from tempestweb.native import storage` binds the facade's group."""
    js = gen(
        "from tempestweb.native import storage\n\n"
        "async def f(key):\n    return await storage.get(key)\n"
    )
    assert "native$.storage.get(key)" in js


def test_an_aliased_import_keeps_the_local_name() -> None:
    """`as` renames the binding without losing the facade path."""
    js = gen(
        "from tempestweb.native.share import share as send\n\n"
        "async def f(payload):\n    return await send(payload)\n"
    )
    assert "native$.share.share(payload)" in js


def test_the_error_type_matches_by_the_name_it_carries() -> None:
    """Mode C dispatches `except` by class name, and the facade sets it."""
    js = gen(
        "from tempestweb.native import NativeError\n\n"
        "def f():\n"
        "    try:\n        g()\n"
        "    except NativeError as exc:\n        return str(exc)\n"
    )
    assert '_err.name === "NativeError"' in js


def test_a_renamed_error_type_still_matches_the_error_it_names() -> None:
    """An aliased import tested against its local name never fired.

    ``except NativeError as Failure`` compared ``_err.name === "Failure"``,
    and the facade's error carries ``"NativeError"`` — so the handler was dead
    code and the error escaped to the top level.
    """
    js = gen(
        "from tempestweb.native import NativeError as Failure\n\n"
        "def f():\n"
        "    try:\n        g()\n"
        "    except Failure as exc:\n        return str(exc)\n"
    )
    assert '_err.name === "NativeError"' in js
    assert '"Failure"' not in js


def test_a_string_enum_becomes_a_frozen_table() -> None:
    """The facade returns the raw value, so the enum is a comparison table."""
    js = gen(
        "from tempestweb.native.notifications import NotificationPermission\n\n"
        "def f(perm):\n    return perm is NotificationPermission.GRANTED\n"
    )
    assert "const NotificationPermission = Object.freeze({" in js
    assert '"granted"' in js


def test_an_unknown_member_is_refused_by_its_own_name() -> None:
    """The diagnostic names what was asked for, not the module it came from."""
    with pytest.raises(TranspileError) as excinfo:
        gen("from tempestweb.native import escape_html\n")
    assert "escape_html" in str(excinfo.value)

    with pytest.raises(TranspileError) as grouped:
        gen("from tempestweb.native.geolocation import triangulate\n")
    message = str(grouped.value)
    assert "geolocation.triangulate" in message
    assert "get_position" in message


def test_a_capability_the_facade_lacks_says_which_mode_has_it() -> None:
    """`camera.capture` is not a Mode C capability, and the refusal says so."""
    with pytest.raises(TranspileError) as excinfo:
        gen("from tempestweb.native import camera\n")
    message = str(excinfo.value)
    assert "camera" in message
    assert "Mode A" in message and "Mode B" in message


def test_the_plain_import_form_points_at_the_forms_that_work() -> None:
    """`import tempestweb.native` listed the stdlib modules it serves instead."""
    with pytest.raises(TranspileError) as excinfo:
        gen("import tempestweb.native\n")
    message = str(excinfo.value)
    assert "from tempestweb import native" in message
    assert "from tempestweb.native import get_position" in message


def test_a_field_named_get_is_an_attribute_and_not_a_dict_read() -> None:
    """A state carrying an injected `get` called it; Mode C indexed it instead.

    ``examples/file-storage`` injects ``storage.get`` into its state and reads a
    note with ``app.state.get(key)``. Mapped as a dict read, that compiled to
    ``app.state[key]`` — valid JS returning undefined, so the page loaded and no
    note ever opened.
    """
    js = gen(
        "from dataclasses import dataclass\n"
        "from tempestweb.native import storage\n\n"
        "@dataclass\nclass S:\n    get: object = storage.get\n\n"
        "async def f(app, key):\n    return await app.state.get(key)\n"
    )
    assert "app.state.get(key)" in js
    assert "app.state[key]" not in js


@pytest.mark.skipif(
    shutil.which("node") is None, reason="node parses the emitted module"
)
def test_the_native_examples_emit_a_module_node_can_parse(tmp_path: Path) -> None:
    """The examples this unblocked emit JS the browser can load."""
    root = Path(__file__).resolve().parents[2]
    from tempestweb.transpile import transpile_file

    for name in ("geo_demo", "file-storage", "weather-native", "clipboard-share"):
        js = transpile_file(root / "examples" / name / "app.py")
        module = tmp_path / f"{name}.mjs"
        module.write_text(js, encoding="utf-8")
        result = subprocess.run(
            ["node", "--check", str(module)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"{name}:\n{result.stderr}"


def test_the_facade_exports_are_what_the_compiler_routes() -> None:
    """The facade module exports the namespace and the error type."""
    assert {"native", "NativeError"} <= set(NATIVE_EXPORTS)
    assert set(NATIVE_ENUMS) == {"NotificationPermission", "ShareOutcome"}
