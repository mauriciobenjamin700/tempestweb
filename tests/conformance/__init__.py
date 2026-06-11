"""Conformance harness for tempestweb.

This package pins the Python<->client wire format against golden fixtures
derived from the *real* vendored core (never hand-invented), and proves the
**A-vs-B guarantee**: two independent transports fed the same patch stream
render an identical DOM.

Modules:
    _scenarios: Canonical, code-defined view sequences built with the real core.
    _generate: Turns the scenarios into JSON-able golden fixtures (regenerable).
    _dom: A minimal, deterministic reference DOM and patch applicator that mirrors
        the behavior the JS client (``client/dom.js``) must implement, per
        ``docs/contract.md``.
    _transports: Two mock :class:`tempestweb.transports.base.PatchTransport`
        implementations with deliberately different internals.
"""

from __future__ import annotations
