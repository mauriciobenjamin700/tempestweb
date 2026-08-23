"""GENERATED from the Mode C client.

Regenerate: ``python -m tests.conformance._transpile_value_members``.

The members each served value carries in the JS. A call on anything else
is refused at build time, because it would compile, load and then throw
``is not a function`` at mount — the failure ``node --check`` cannot see.
Do not edit by hand.
"""

from __future__ import annotations

__all__: list[str] = ["VALUE_MEMBERS"]

#: Served name -> the members the client's own object carries.
VALUE_MEMBERS: dict[str, frozenset[str]] = {
    "Color": frozenset({"from_hex"}),
    "Edge": frozenset({"all", "symmetric"}),
}
