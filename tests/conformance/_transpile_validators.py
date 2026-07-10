"""Regenerate the Mode C validator-parity fixture from the real core.

Run as a module to (re)write the golden::

    python -m tests.conformance._transpile_validators

`client/transpile/validators.js` is a hand-authored port of
`tempest_core.validators`. This fixture pins, for a battery of inputs, the exact
message (or null) the *real* core returns, so a JS test asserts the port stays
faithful. Derived from the core — never hand-typed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tempest_core import validators as v

FIXTURES_DIR: Path = Path(__file__).resolve().parents[1] / "fixtures"
VALIDATORS_FIXTURE: Path = FIXTURES_DIR / "transpile_validator_cases.json"

# Inputs to exercise per validator — valid, invalid, masked, all-same, edge.
_INPUTS: dict[str, list[str]] = {
    "validate_cpf": ["529.982.247-25", "52998224725", "111.111.111-11", "123", "abc"],
    "validate_cnpj": ["11.222.333/0001-81", "11222333000181", "00000000000000", "1"],
    "validate_email": ["a@b.co", "bad", "x@y", "user@domain.com", " a@b.co "],
    "validate_phone": ["(11) 98765-4321", "11987654321", "1132654321", "123", ""],
}


def build_cases() -> list[dict[str, Any]]:
    """Build ``{validator, input, expected}`` triples from the real core.

    Returns:
        One case per (validator, input), with the core's returned message or
        ``None``.
    """
    cases: list[dict[str, Any]] = []
    for name, inputs in _INPUTS.items():
        fn = getattr(v, name)
        for value in inputs:
            cases.append({"validator": name, "input": value, "expected": fn(value)})
    return cases


def render_fixture_text() -> str:
    """Render the validator-parity fixture as canonical JSON text."""
    payload = json.dumps(build_cases(), indent=2, ensure_ascii=False)
    return payload + "\n"


def write_fixture() -> Path:
    """Write the validator-parity fixture to disk and return its path."""
    VALIDATORS_FIXTURE.write_text(render_fixture_text(), encoding="utf-8")
    return VALIDATORS_FIXTURE


def main() -> None:
    """Regenerate the validator-parity fixture and print its path."""
    print(f"wrote {write_fixture()}")


if __name__ == "__main__":
    main()
