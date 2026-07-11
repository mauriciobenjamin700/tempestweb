"""Conformance tests for the native-capability contract (N-C4).

The contract (:mod:`tempestweb.native.contract`) is the single source of truth
for the set of native capabilities and which are exposed in Mode C. These tests
parse the JS surfaces and assert they match the contract, so a capability added
to one surface but not the others fails CI.
"""

from __future__ import annotations

import re
from pathlib import Path

from tempestweb import native
from tempestweb.native import capability_names, mode_c_capability_names
from tempestweb.native.contract import (
    single_shot_capability_names,
    streaming_capability_names,
)

ROOT = Path(__file__).resolve().parents[2]
INDEX_JS = ROOT / "client" / "native" / "index.js"
FACADE_JS = ROOT / "client" / "transpile" / "native.js"

# A dotted capability name in a JS string literal, e.g. "http.request".
_DOTTED = re.compile(r'"([a-z_]+\.[a-z_]+)"')


def _block(source: str, marker: str) -> str:
    """Return the object-literal block starting at ``marker`` up to its ``};``."""
    start = source.index(marker)
    return source[start : source.index("};", start)]


def _handler_keys() -> set[str]:
    """Return the dotted capability names registered in index.js ``HANDLERS``."""
    source = INDEX_JS.read_text(encoding="utf-8")
    return set(_DOTTED.findall(_block(source, "HANDLERS = {")))


def _event_handler_keys() -> set[str]:
    """Return the dotted streaming names registered in index.js ``EVENT_HANDLERS``."""
    source = INDEX_JS.read_text(encoding="utf-8")
    return set(_DOTTED.findall(_block(source, "EVENT_HANDLERS = {")))


def _facade_call_capabilities() -> set[str]:
    """Return the single-shot capabilities the Mode C facade dispatches (``call``)."""
    source = FACADE_JS.read_text(encoding="utf-8")
    return set(re.findall(r'call\(\s*"([a-z_]+\.[a-z_]+)"', source))


def _facade_stream_capabilities() -> set[str]:
    """Return the streaming capabilities the Mode C facade subscribes (``stream``)."""
    source = FACADE_JS.read_text(encoding="utf-8")
    return set(re.findall(r'stream\(\s*"([a-z_]+\.[a-z_]+)"', source))


def test_js_handlers_match_the_contract() -> None:
    """`client/native/index.js` HANDLERS covers exactly the single-shot capabilities."""
    assert _handler_keys() == set(single_shot_capability_names())


def test_event_handlers_match_the_streaming_contract() -> None:
    """`client/native/index.js` EVENT_HANDLERS covers exactly the streaming caps."""
    assert _event_handler_keys() == set(streaming_capability_names())


def test_facade_matches_the_mode_c_contract() -> None:
    """The Mode C facade dispatches exactly the contract's mode_c capabilities.

    Single-shot mode_c capabilities appear as ``call(...)`` and streaming ones as
    ``stream(...)``; together they must equal the mode_c set.
    """
    mode_c_single = {c.name for c in native.MODE_C_CAPABILITIES if not c.streaming}
    mode_c_stream = {c.name for c in native.MODE_C_CAPABILITIES if c.streaming}
    assert _facade_call_capabilities() == mode_c_single
    assert _facade_stream_capabilities() == mode_c_stream


def test_mode_c_is_a_subset_of_all_capabilities() -> None:
    """Every Mode C capability is a capability."""
    assert mode_c_capability_names() <= capability_names()


def test_streaming_is_a_subset_of_all_capabilities() -> None:
    """Every streaming capability is a capability."""
    assert streaming_capability_names() <= capability_names()


def test_every_capability_group_has_a_python_module() -> None:
    """Each capability group is a native submodule (the Python awaitable surface)."""
    for cap in native.CAPABILITIES:
        assert hasattr(native, cap.group), cap.group


def test_contract_has_no_duplicate_names() -> None:
    """Capability names are unique."""
    names = [cap.name for cap in native.CAPABILITIES]
    assert len(names) == len(set(names))
