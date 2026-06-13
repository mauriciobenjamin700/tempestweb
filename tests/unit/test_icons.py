"""Tests for the tempestweb.icons façade (Material + Lucide helpers)."""

from __future__ import annotations

from tempest_core import build
from tempestweb.icons import (
    Icon,
    Icons,
    MaterialIcons,
    custom_icon,
    icon_path,
    lucide_icon,
    material_icon,
)


def test_material_icon_prefixes_the_name() -> None:
    """material_icon tags the name so the client uses the Material set."""
    icon = material_icon(MaterialIcons.HOME, size=20.0, key="m")
    assert isinstance(icon, Icon)
    assert icon.name == "material:home"
    assert icon.size == 20.0
    assert icon.key == "m"


def test_lucide_icon_prefixes_the_name() -> None:
    """lucide_icon tags the name with the lucide: set prefix."""
    icon = lucide_icon(Icons.MAIL)
    assert icon.name == "lucide:mail"
    assert icon.size is None


def test_custom_icon_carries_the_raw_path() -> None:
    """custom_icon ships the SVG path inline via the path: pseudo-set."""
    icon = custom_icon("M3 3 l5 5")
    assert icon.name == "path:M3 3 l5 5"


def test_icons_serialize_as_icon_nodes() -> None:
    """The helpers lower to an "Icon" IR node carrying the prefixed name."""
    node = build(material_icon("settings"))
    assert node.type == "Icon"
    assert node.props.get("name") == "material:settings"


def test_material_names_enum_is_string_valued() -> None:
    """MaterialIcons members double as their snake_case string."""
    assert MaterialIcons.VISIBILITY_OFF == "visibility_off"
    assert material_icon(MaterialIcons.SEARCH).name == "material:search"


def test_core_lucide_registry_reexported() -> None:
    """The core's Lucide resolution comes through the façade unchanged."""
    assert icon_path("mail") is not None
    assert icon_path("not-a-real-icon") is None
