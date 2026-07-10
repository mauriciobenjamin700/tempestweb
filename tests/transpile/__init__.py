"""Tests for the Mode C transpiler (typed Python app layer → native JS).

Modules:
    _generate: Regenerates the committed `.gen.js` goldens from the example apps.
    test_counter: Golden test — the transpiler reproduces `counter.gen.js`.
    test_codegen: Unit tests for the individual construct → JS mappings.
"""

from __future__ import annotations
