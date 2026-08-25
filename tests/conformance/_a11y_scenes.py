"""Generate the a11y gate's scenes from the real example apps.

Run as a module to (re)write the golden::

    python -m tests.conformance._a11y_scenes

The accessibility gate (``scripts/a11y-gate.mjs``) runs axe-core over the DOM the
**real renderer** builds. What it needs is IR, and the honest source of IR is the
apps this repo ships: each scene below is one example's ``view`` built with the
core, serialized exactly as the wire carries it. So the gate audits the markup a
reader would actually get, not a hand-written fragment that happens to be
accessible.

The scenes are chosen for markup diversity, not for count: the component gallery
(every ported component on one page), the control panel (switch/slider/checkbox/
radio), a list with a text field, a form, a nav shell with a drawer, and a media
screen. A regression in any of those is a regression a person would hit.

Diversity is measured by **widget type**, not by screen count, and the first six
scenes missed seven of the controls that had just learned to speak — the range
slider, the dropdown, the autocomplete, both pickers, the file picker and the tab
bar. Adding the three screens that carry them found two more critical violations
immediately, so a control that reports an event belongs in a scene: that is what
makes the gate's silence mean something.

Diversity by **component** is the same argument, and it had the same hole: nine
scenes and not one used ``TextField``/``EmailField``/``PasswordField`` or the two
forms built from them. ``login-form`` looks like it does and does not — it uses the
core's ``EmailInput``/``PasswordInput`` inside a ``FormField``, which the renderer
names. So the tempestweb-owned fields shipped an anonymous control (axe ``label``,
critical, whenever the placeholder was empty) with a green gate. ``login_demo``,
which uses ``LoginForm``, closes that.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from tempest_core import App, build
from tempestweb.runtime.serialize import node_to_wire

ROOT: Path = Path(__file__).resolve().parents[2]
EXAMPLES: Path = ROOT / "examples"
SCENES_FIXTURE: Path = ROOT / "tests" / "fixtures" / "a11y_scenes.json"

#: The examples the gate audits, and why each one is here.
SCENES: dict[str, str] = {
    "mode-c-components": "every ported component on one page",
    "settings-panel": "the selection controls (switch, checkbox, slider, radio)",
    "todo": "a virtualized list plus a text field",
    "login-form": "a form with labelled fields and a submit",
    "router-drawer": "a nav shell: app bar, drawer, breadcrumb",
    "image-gallery": "images, which is where alt text is either there or not",
    "booking-form": "the pickers, the dropdown, the range slider, the file picker",
    "search-autocomplete": "a text field backed by a datalist",
    "tabs-profile": "a tab bar and the panel it switches",
    "login_demo": "the tempestweb-native fields — the ones the gate never saw",
}


def _load(name: str) -> ModuleType:
    """Import one example's ``app`` module by directory name.

    Args:
        name: The example directory under ``examples/``.

    Returns:
        The imported module exposing ``make_state`` and ``view``.
    """
    module_name = f"_a11y_scene_{name}"
    path = EXAMPLES / name / "app.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def build_scenes() -> dict[str, Any]:
    """Build every scene to its serialized IR.

    Returns:
        ``{example name: wire node}``.
    """
    scenes: dict[str, Any] = {}
    for name in SCENES:
        module = _load(name)
        app: App[Any] = App(
            state=module.make_state(),
            view=module.view,
            apply_patches=lambda _: None,
        )
        scenes[name] = node_to_wire(build(module.view(app)))
    return scenes


def render_fixture_text() -> str:
    """Render the scenes fixture as canonical JSON text.

    Returns:
        The fixture file content.
    """
    payload = json.dumps(build_scenes(), indent=2, sort_keys=True, ensure_ascii=False)
    return payload + "\n"


def write_fixture() -> Path:
    """Write the scenes fixture to disk.

    Returns:
        The path written.
    """
    SCENES_FIXTURE.write_text(render_fixture_text(), encoding="utf-8")
    return SCENES_FIXTURE


def main() -> None:
    """Regenerate the scenes fixture and print its path."""
    print(f"wrote {write_fixture()}")


if __name__ == "__main__":
    main()
