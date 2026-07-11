"""Project scaffolding for ``tempestweb new``.

Generates a minimal but *runnable* project tree: an ``app.py`` exposing the
``make_state`` / ``view`` contract (a working counter), a ``tempestweb.toml``
config, a README and a ``.gitignore``. The output imports only from
``tempestweb`` and runs unchanged under both execution modes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tempestweb.core.constants import DEFAULT_MODE

__all__ = [
    "DEFAULT_MODE",
    "PROJECT_FILES",
    "TEMPLATES",
    "ProjectExistsError",
    "ScaffoldResult",
    "UnknownTemplateError",
    "render_files",
    "scaffold_project",
]

# Project-relative paths the scaffolder always writes, in a stable order.
PROJECT_FILES: tuple[str, ...] = (
    "app.py",
    "tempestweb.toml",
    "README.md",
    ".gitignore",
)

# The scaffold templates a project can be created from.
TEMPLATES: tuple[str, ...] = ("default", "pwa")


class ProjectExistsError(RuntimeError):
    """Raised when the target directory already exists and is not empty."""


class UnknownTemplateError(RuntimeError):
    """Raised when an unknown scaffold template is requested."""


@dataclass(slots=True)
class ScaffoldResult:
    """The outcome of scaffolding a project.

    Attributes:
        root: The created project directory.
        files: Project-relative paths that were written, in write order.
    """

    root: Path
    files: tuple[str, ...]


def _app_py() -> str:
    """Return the contents of the scaffolded ``app.py``.

    Returns:
        A runnable counter app exposing ``make_state`` and ``view``.
    """
    return '''\
"""Application entrypoint — runs unchanged in both modes.

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

The application never names a transport — `tempestweb build --mode` picks it.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.style import Edge


@dataclass
class State:
    """Application state."""

    value: int = 0


def make_state() -> State:
    """Build the initial state.

    Returns:
        A fresh :class:`State`.
    """
    return State()


def view(app: App[State]) -> Widget:
    """Render the UI from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def increment() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    def decrement() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value - 1))

    return Column(
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Count: {app.state.value}", key="label"),
            Row(
                style=Style(gap=4.0),
                children=[
                    Button(label="-", on_click=decrement, key="dec"),
                    Button(label="+", on_click=increment, key="inc"),
                ],
            ),
        ],
    )
'''


def _pwa_app_py() -> str:
    """Return the ``app.py`` for the PWA (Mode C) template.

    Returns:
        A runnable native-JS PWA: a counter plus an install button using the
        ``native.install`` capability. Stays within the transpilable subset.
    """
    return '''\
"""PWA entrypoint — a native-JavaScript Progressive Web App (Mode C).

    tempestweb dev   --mode transpile   # live-reload dev server
    tempestweb build --mode transpile   # installable, offline PWA bundle

Zero Python in the browser: the app layer is transcribed to native JavaScript.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.style import Edge

from tempestweb import native


@dataclass
class State:
    """Application state."""

    value: int = 0
    install: str = ""


def make_state() -> State:
    """Build the initial state.

    Returns:
        A fresh :class:`State`.
    """
    return State()


def view(app: App[State]) -> Widget:
    """Render the UI from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    def increment() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    def decrement() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value - 1))

    async def install() -> None:
        outcome = await native.install.prompt()
        app.set_state(lambda s: setattr(s, "install", outcome))

    return Column(
        style=Style(gap=12.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Count: {app.state.value}", key="label"),
            Row(
                style=Style(gap=4.0),
                children=[
                    Button(label="-", on_click=decrement, key="dec"),
                    Button(label="+", on_click=increment, key="inc"),
                ],
            ),
            Button(label="Install", on_click=install, key="install"),
            Text(content=app.state.install, key="installout"),
        ],
    )
'''


def _tempestweb_toml(name: str) -> str:
    """Return the contents of the scaffolded ``tempestweb.toml``.

    Args:
        name: The project name.

    Returns:
        A minimal project config the CLI reads for defaults.
    """
    return f"""\
# tempestweb project configuration.
[project]
name = "{name}"
entrypoint = "app.py"

[dev]
# Default execution mode for `tempestweb dev` / `build` / `run`.
mode = "{DEFAULT_MODE}"
host = "127.0.0.1"
port = 8000
"""


def _pwa_toml(name: str) -> str:
    """Return the ``tempestweb.toml`` for the PWA (Mode C) template.

    Args:
        name: The project name.

    Returns:
        A config defaulting to ``transpile`` mode with a ``[pwa]`` manifest block.
    """
    return f"""\
# tempestweb project configuration.
[project]
name = "{name}"
entrypoint = "app.py"

[dev]
# Mode C (transpile): a native-JavaScript Progressive Web App.
mode = "transpile"
host = "127.0.0.1"
port = 8000

# Web App Manifest — customize freely (all fields optional).
[pwa]
name = "{name}"
theme_color = "#6750a4"
display = "standalone"
"""


def _pwa_readme(name: str) -> str:
    """Return the ``README.md`` for the PWA (Mode C) template.

    Args:
        name: The project name.

    Returns:
        A getting-started README for the installable/offline PWA.
    """
    return f"""\
# {name}

An installable, offline-capable **Progressive Web App** built with
[tempestweb](https://pypi.org/project/tempestweb/) Mode C — typed Python
transcribed to native JavaScript (zero Python in the browser).

## Develop

```bash
tempestweb dev --mode transpile     # live-reload dev server
```

## Build

```bash
tempestweb build --mode transpile   # static, installable, offline PWA bundle
```

The build emits a Web App Manifest and a cache-first service worker that
precaches the whole shell, so the app installs and opens offline after the first
load. Customize the manifest under `[pwa]` in `tempestweb.toml`.
"""


def _readme(name: str) -> str:
    """Return the contents of the scaffolded ``README.md``.

    Args:
        name: The project name.

    Returns:
        A short getting-started README.
    """
    return f"""\
# {name}

A [tempestweb](https://pypi.org/project/tempestweb/) app — typed Python, two
execution modes, one codebase.

## Develop

```bash
tempestweb dev --mode wasm     # Python in the browser (Pyodide)
tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)
```

## Build

```bash
tempestweb build --mode wasm   # static bundle (deploy to any CDN/host)
tempestweb build --mode server # FastAPI app
```

The same `app.py` runs in both modes — only the transport changes.
"""


def _gitignore() -> str:
    """Return the contents of the scaffolded ``.gitignore``.

    Returns:
        Sensible ignores for a Python tempestweb project.
    """
    return """\
__pycache__/
*.py[cod]
.venv/
dist/
.tempestweb/
"""


def render_files(name: str, *, template: str = "default") -> dict[str, str]:
    """Render every scaffolded file's contents without touching disk.

    Args:
        name: The project name (used in config and README).
        template: The scaffold template — ``"default"`` (a two-mode counter) or
            ``"pwa"`` (a Mode C native-JS Progressive Web App).

    Returns:
        A mapping of project-relative path to file contents, covering exactly
        :data:`PROJECT_FILES`.

    Raises:
        UnknownTemplateError: If ``template`` is not one of :data:`TEMPLATES`.
    """
    if template not in TEMPLATES:
        raise UnknownTemplateError(
            f"unknown template {template!r}; expected one of {TEMPLATES}"
        )
    if template == "pwa":
        return {
            "app.py": _pwa_app_py(),
            "tempestweb.toml": _pwa_toml(name),
            "README.md": _pwa_readme(name),
            ".gitignore": _gitignore(),
        }
    return {
        "app.py": _app_py(),
        "tempestweb.toml": _tempestweb_toml(name),
        "README.md": _readme(name),
        ".gitignore": _gitignore(),
    }


def scaffold_project(
    name: str,
    *,
    parent: str | Path = ".",
    force: bool = False,
    template: str = "default",
) -> ScaffoldResult:
    """Create a new runnable project tree under ``parent/name``.

    Args:
        name: The project name; also the created directory name.
        parent: The directory to create the project inside. Defaults to the cwd.
        force: When ``True``, write into an existing non-empty directory instead
            of refusing.
        template: The scaffold template (``"default"`` or ``"pwa"``).

    Returns:
        A :class:`ScaffoldResult` describing the created tree.

    Raises:
        ProjectExistsError: If the target directory exists and is non-empty and
            ``force`` is ``False``.
        UnknownTemplateError: If ``template`` is unknown.
    """
    contents = render_files(name, template=template)
    root = (Path(parent) / name).resolve()
    if root.exists() and any(root.iterdir()) and not force:
        raise ProjectExistsError(
            f"{root} already exists and is not empty (pass force=True to overwrite)"
        )

    root.mkdir(parents=True, exist_ok=True)
    for rel in PROJECT_FILES:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents[rel], encoding="utf-8")

    return ScaffoldResult(root=root, files=PROJECT_FILES)
