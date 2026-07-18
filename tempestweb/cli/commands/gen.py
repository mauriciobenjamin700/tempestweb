"""``tempestweb gen api`` — generate a typed client from an OpenAPI spec.

If your backend is FastAPI (or any API exposing OpenAPI 3.x), ``gen api`` reads
the spec and writes a typed client the Tempest way: one package per route group
(tag), each with ``@dataclass`` models (``schemas.py``) and a service class
(``service.py``) whose methods call :func:`tempestweb.native.http.request`. No
hand-written ``fetch`` and no types drifting from the backend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from tempestweb.cli.openapi import SpecLoadError, generate, load_spec

__all__ = ["GenError", "GenResult", "generate_api"]


class GenError(RuntimeError):
    """Raised when ``tempestweb gen`` cannot complete."""


@dataclass
class GenResult:
    """Outcome of a client generation.

    Attributes:
        out_dir: The directory the client was written to.
        files: Relative paths written, in write order.
        tags: The OpenAPI tags that produced a route group.
    """

    out_dir: Path
    files: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


def generate_api(source: str, out: str = "api") -> GenResult:
    """Generate a typed client from an OpenAPI spec.

    Args:
        source: File path or ``http(s)`` URL to an ``openapi.json``.
        out: Output directory for the generated client (created if missing).

    Returns:
        The generation result (output dir, written files, tags).

    Raises:
        GenError: When the spec cannot be loaded/parsed or contains no
            operations to generate from.
    """
    try:
        document = load_spec(source)
    except SpecLoadError as exc:
        raise GenError(str(exc)) from exc

    files, tags = generate(document)
    if not tags:
        raise GenError(
            "No operations found in the spec — nothing to generate. "
            "Check that the source points at a valid OpenAPI document with paths."
        )

    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for relative, contents in files.items():
        target = out_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents, encoding="utf-8")
        written.append(relative)

    return GenResult(out_dir=out_dir, files=written, tags=tags)
