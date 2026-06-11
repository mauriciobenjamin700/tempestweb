"""Shared pytest fixtures for tempestweb."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture() -> Any:
    """Return a loader for JSON golden fixtures under tests/fixtures/."""

    def _load(name: str) -> Any:
        return json.loads((FIXTURES / name).read_text())

    return _load
