"""Unit tests for O3 feature flags: provider, in-memory, vendor adapters."""

from __future__ import annotations

from unittest.mock import MagicMock

from tempestweb.observability import (
    FeatureFlagsProvider,
    GrowthBookFeatureFlagsAdapter,
    InMemoryFeatureFlagsAdapter,
    LaunchDarklyFeatureFlagsAdapter,
)


def test_is_enabled_reads_boolean_flag() -> None:
    flags = FeatureFlagsProvider(InMemoryFeatureFlagsAdapter({"new_ui": True}))

    assert flags.is_enabled("new_ui") is True
    assert flags.is_enabled("missing") is False


def test_is_enabled_default_used_for_unknown_flag() -> None:
    flags = FeatureFlagsProvider(InMemoryFeatureFlagsAdapter())

    assert flags.is_enabled("missing", default=True) is True


def test_get_returns_value_or_default() -> None:
    flags = FeatureFlagsProvider(
        InMemoryFeatureFlagsAdapter({"limit": 5, "label": "beta"})
    )

    assert flags.get("limit") == 5
    assert flags.get("label") == "beta"
    assert flags.get("missing", default="off") == "off"


def test_on_change_fires_when_in_memory_flag_changes() -> None:
    adapter = InMemoryFeatureFlagsAdapter({"x": False})
    flags = FeatureFlagsProvider(adapter)
    calls: list[int] = []
    flags.on_change(lambda: calls.append(1))

    adapter.set("x", True)

    assert calls == [1]
    assert flags.is_enabled("x") is True


def test_unsubscribe_stops_notifications() -> None:
    adapter = InMemoryFeatureFlagsAdapter()
    flags = FeatureFlagsProvider(adapter)
    calls: list[int] = []
    unsubscribe = flags.on_change(lambda: calls.append(1))

    adapter.set("a", 1)
    unsubscribe()
    adapter.set("b", 2)

    assert calls == [1]


def test_swapping_adapter_changes_no_call_sites() -> None:
    def read(provider: FeatureFlagsProvider) -> bool:
        return provider.is_enabled("feature")

    in_memory = FeatureFlagsProvider(InMemoryFeatureFlagsAdapter({"feature": True}))

    gb_client = MagicMock()
    gb_client.get_feature_value.return_value = True
    growthbook = FeatureFlagsProvider(GrowthBookFeatureFlagsAdapter(gb_client))

    assert read(in_memory) is True
    assert read(growthbook) is True


def test_growthbook_adapter_reads_from_injected_client() -> None:
    client = MagicMock()
    client.get_feature_value.return_value = "variant-b"
    flags = FeatureFlagsProvider(GrowthBookFeatureFlagsAdapter(client))

    assert flags.get("exp", default="control") == "variant-b"
    client.get_feature_value.assert_called_once_with("exp", "control")


def test_growthbook_refresh_notifies_subscribers() -> None:
    client = MagicMock()
    adapter = GrowthBookFeatureFlagsAdapter(client)
    flags = FeatureFlagsProvider(adapter)
    calls: list[int] = []
    flags.on_change(lambda: calls.append(1))

    adapter.refresh()

    assert calls == [1]


def test_launchdarkly_adapter_reads_variation_with_context() -> None:
    client = MagicMock()
    client.variation.return_value = True
    context = {"key": "user-1"}
    flags = FeatureFlagsProvider(LaunchDarklyFeatureFlagsAdapter(client, context))

    assert flags.is_enabled("flag") is True
    client.variation.assert_called_once_with("flag", context, False)


def test_launchdarkly_notify_fires_listeners() -> None:
    client = MagicMock()
    adapter = LaunchDarklyFeatureFlagsAdapter(client, {"key": "u1"})
    flags = FeatureFlagsProvider(adapter)
    calls: list[int] = []
    flags.on_change(lambda: calls.append(1))

    adapter.notify()

    assert calls == [1]
