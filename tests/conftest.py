"""Shared pytest fixtures for tempestweb."""

from __future__ import annotations

import asyncio
import json
import warnings
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


@pytest.fixture(autouse=True)
def _ensure_event_loop() -> Any:
    """Give every test a usable asyncio event loop.

    ``pytest-asyncio`` closes the loop it creates for each async test, leaving a
    closed loop as the thread's current loop. Later **sync** tests that trigger
    the core's rebuild (which calls ``asyncio.get_event_loop()``) would then hit
    a closed loop. This installs a fresh loop whenever the current one is missing
    or closed, without overriding the loop pytest-asyncio sets for async tests.
    A loop created here is closed on teardown so it is not garbage-collected
    open (which would raise a ``ResourceWarning`` from ``BaseEventLoop.__del__``).
    """
    try:
        loop = asyncio.get_running_loop()
        closed = loop.is_closed()
    except RuntimeError:
        # No loop is running in this thread. Probe the policy's current loop;
        # ``get_event_loop`` emits a DeprecationWarning when none is set, which
        # is exactly the case we are handling, so silence that single probe.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            try:
                loop = asyncio.get_event_loop_policy().get_event_loop()
                closed = loop.is_closed()
            except RuntimeError:
                closed = True
    created: asyncio.AbstractEventLoop | None = None
    if closed:
        created = asyncio.new_event_loop()
        asyncio.set_event_loop(created)
    yield
    if created is not None and not created.is_closed():
        created.close()
