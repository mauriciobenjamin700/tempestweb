"""Project scaffolding for ``tempestweb new``.

Generates a minimal but *runnable* project tree: an ``app.py`` exposing the
``make_state`` / ``view`` contract (a working counter), a ``tempestweb.toml``
config, a README and a ``.gitignore``. The output imports only from
``tempestweb`` and runs unchanged under both execution modes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "DEFAULT_MODE",
    "PROJECT_FILES",
    "ProjectExistsError",
    "ScaffoldResult",
    "render_files",
    "scaffold_project",
]

# The mode a fresh project defaults to (Mode A — WASM, per docs/plan.md §6).
DEFAULT_MODE = "wasm"

# Project-relative paths the scaffolder always writes, in a stable order.
PROJECT_FILES: tuple[str, ...] = (
    "app.py",
    "tempestweb.toml",
    "README.md",
    ".gitignore",
)


class ProjectExistsError(RuntimeError):
    """Raised when the target directory already exists and is not empty."""


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
"""{{ app entrypoint }} — runs unchanged in both modes.

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

The application never names a transport — `tempestweb build --mode` picks it.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestweb._core import App, Button, Column, Row, Style, Text, Widget
from tempestweb._core.style import Edge


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


def _tempestweb_toml(name: str) -> str:
    """Return the contents of the scaffolded ``tempestweb.toml``.

    Args:
        name: The project name.

    Returns:
        A minimal project config the CLI reads for defaults.
    """
    return f'''\
# tempestweb project configuration.
[project]
name = "{name}"
entrypoint = "app.py"

[dev]
# Default execution mode for `tempestweb dev` / `build` / `run`.
mode = "{DEFAULT_MODE}"
host = "127.0.0.1"
port = 8000
'''


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


def render_files(name: str) -> dict[str, str]:
    """Render every scaffolded file's contents without touching disk.

    Args:
        name: The project name (used in config and README).

    Returns:
        A mapping of project-relative path to file contents, covering exactly
        :data:`PROJECT_FILES`.
    """
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
) -> ScaffoldResult:
    """Create a new runnable project tree under ``parent/name``.

    Args:
        name: The project name; also the created directory name.
        parent: The directory to create the project inside. Defaults to the cwd.
        force: When ``True``, write into an existing non-empty directory instead
            of refusing.

    Returns:
        A :class:`ScaffoldResult` describing the created tree.

    Raises:
        ProjectExistsError: If the target directory exists and is non-empty and
            ``force`` is ``False``.
    """
    root = (Path(parent) / name).resolve()
    if root.exists() and any(root.iterdir()) and not force:
        raise ProjectExistsError(
            f"{root} already exists and is not empty (pass force=True to overwrite)"
        )

    root.mkdir(parents=True, exist_ok=True)
    contents = render_files(name)
    for rel in PROJECT_FILES:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents[rel], encoding="utf-8")

    return ScaffoldResult(root=root, files=PROJECT_FILES)
