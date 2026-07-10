"""Regenerate the Mode C i18n parity fixture from the real core.

Run as a module to (re)write the golden::

    python -m tests.conformance._transpile_i18n

`client/transpile/i18n.js` ports `tempest_core.i18n`. This fixture pins the
string the *real* core `translate` returns for a battery of (locale, key, params)
inputs, so a JS test asserts the port matches — including the miss/fallback rules.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tempest_core import Locale, translate

FIXTURES_DIR: Path = Path(__file__).resolve().parents[1] / "fixtures"
I18N_FIXTURE: Path = FIXTURES_DIR / "transpile_i18n_cases.json"

_TABLE: dict[str, dict[str, str]] = {
    "pt": {"hello": "Olá, {name}", "bye": "Tchau"},
    "en": {"hello": "Hi, {name}", "bye": "Bye"},
}

# (language, key, params) cases — hit, miss key, miss language, missing param.
_CASES: list[tuple[str, str, dict[str, str]]] = [
    ("pt", "hello", {"name": "Ana"}),
    ("en", "hello", {"name": "Bob"}),
    ("pt", "bye", {}),
    ("pt", "missing_key", {"name": "X"}),
    ("de", "hello", {"name": "Z"}),  # missing language
    ("pt", "hello", {}),  # placeholder with no value -> un-interpolated template
]


def build_cases() -> list[dict[str, Any]]:
    """Build ``{language, key, params, expected}`` cases from the core."""
    cases: list[dict[str, Any]] = []
    for language, key, params in _CASES:
        expected = translate(key, Locale(language=language), _TABLE, **params)
        cases.append(
            {
                "language": language,
                "key": key,
                "params": params,
                "expected": expected,
            }
        )
    return cases


def render_fixture_text() -> str:
    """Render the i18n parity fixture as canonical JSON text."""
    payload = {"table": _TABLE, "cases": build_cases()}
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def write_fixture() -> Path:
    """Write the i18n parity fixture to disk and return its path."""
    I18N_FIXTURE.write_text(render_fixture_text(), encoding="utf-8")
    return I18N_FIXTURE


def main() -> None:
    """Regenerate the i18n parity fixture and print its path."""
    print(f"wrote {write_fixture()}")


if __name__ == "__main__":
    main()
