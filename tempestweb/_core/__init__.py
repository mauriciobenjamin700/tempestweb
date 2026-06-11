"""Back-compat shim: ``tempestweb._core`` re-exports the extracted ``tempest_core``.

The renderer-agnostic engine was extracted from the former vendored
``tempestweb/_core/`` into the standalone ``tempest-core`` package. This shim keeps
the historical import path working so existing code (and the example gallery) can
still ``from tempestweb._core import …`` / ``from tempestweb._core.<sub> import …``
unchanged. New code should import from ``tempest_core`` directly.

It re-exports the public top-level API and aliases every ``tempest_core`` submodule
under the ``tempestweb._core`` name in ``sys.modules``, so a submodule import like
``tempestweb._core.components.brforms`` resolves to ``tempest_core.components.brforms``.
"""

from __future__ import annotations

import importlib
import pkgutil
import sys

import tempest_core
from tempest_core import *  # noqa: F401,F403 — re-export the public API

__all__ = list(getattr(tempest_core, "__all__", []))


def _alias_submodules() -> None:
    """Register every ``tempest_core`` submodule under ``tempestweb._core.*``.

    Pre-seeding ``sys.modules`` lets ``import tempestweb._core.<path>`` resolve to
    the extracted package even though no such files exist under this shim.
    """
    prefix = f"{tempest_core.__name__}."
    for info in pkgutil.walk_packages(tempest_core.__path__, prefix=prefix):
        try:
            module = importlib.import_module(info.name)
        except ImportError:  # pragma: no cover - optional submodule
            continue
        alias = info.name.replace(tempest_core.__name__, __name__, 1)
        sys.modules.setdefault(alias, module)
        # Also expose it as an attribute on its parent so ``tempestweb._core.style``
        # works (not just ``from tempestweb._core.style import …``).
        parent_name, _, leaf = alias.rpartition(".")
        parent = sys.modules.get(parent_name)
        if parent is not None:
            setattr(parent, leaf, module)


_alias_submodules()
