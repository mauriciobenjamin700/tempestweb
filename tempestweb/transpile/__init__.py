"""Mode C transpiler — typed Python app layer → native JavaScript.

Transcribes a tempestweb app module (state dataclasses + `view` + handlers) into
an ES module that runs on the native JS runtime (`client/transpile/runtime.js`),
with zero Python at execution time. See docs/modo-c-transpile.md.
"""

from __future__ import annotations

from pathlib import Path

from tempestweb.transpile.codegen import generate
from tempestweb.transpile.errors import TranspileError

__all__: list[str] = ["TranspileError", "transpile_file", "transpile_source"]


def transpile_source(
    source: str, filename: str = "<source>", *, banner: str | None = None
) -> str:
    """Transpile Python module source into native-JS module source.

    Args:
        source: The Python source to transpile.
        filename: Source name for diagnostics and the default banner.
        banner: Optional leading comment line (see :func:`generate`).

    Returns:
        The generated JavaScript module source.

    Raises:
        TranspileError: If the module uses a construct outside the subset.
    """
    return generate(source, filename, banner=banner)


def transpile_file(path: str | Path, *, banner: str | None = None) -> str:
    """Transpile a Python source file into native-JS module source.

    Args:
        path: Path to the `.py` module to transpile.
        banner: Optional leading comment line (see :func:`generate`).

    Returns:
        The generated JavaScript module source.

    Raises:
        TranspileError: If the module uses a construct outside the subset.
    """
    file_path = Path(path)
    source = file_path.read_text(encoding="utf-8")
    return generate(source, file_path.name, banner=banner)
