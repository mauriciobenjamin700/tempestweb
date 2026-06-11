"""The ``tempestweb._core`` back-compat shim resolves to ``tempest_core``.

The renderer-agnostic engine was extracted to the ``tempest-core`` package; this
shim keeps the historical import path working (used by the example gallery) so a
``from tempestweb._core[.sub] import …`` resolves to the extracted module.
"""

from __future__ import annotations

import tempest_core


def test_top_level_reexports_match() -> None:
    """Top-level symbols imported via the shim are the tempest_core ones."""
    from tempestweb._core import App, Column, Style, build, diff

    assert App is tempest_core.App
    assert Column is tempest_core.Column
    assert build is tempest_core.build
    assert diff is tempest_core.diff
    assert Style is tempest_core.Style


def test_submodule_from_import_resolves() -> None:
    """`from tempestweb._core.<sub> import X` resolves to tempest_core."""
    from tempest_core.components.brforms import EmailInput as CoreEmailInput
    from tempest_core.style import Edge as CoreEdge
    from tempestweb._core.components.brforms import EmailInput
    from tempestweb._core.style import Edge
    from tempestweb._core.validators import validate_email

    assert EmailInput is CoreEmailInput
    assert Edge is CoreEdge
    assert callable(validate_email)


def test_submodule_attribute_access_resolves() -> None:
    """`tempestweb._core.<sub>` attribute access points at the same module."""
    import tempestweb._core.style

    import tempestweb._core.widgets

    assert tempestweb._core.style is tempest_core.style
    assert tempestweb._core.widgets is tempest_core.widgets
    assert tempestweb._core.components.cards.Card is tempest_core.components.cards.Card
