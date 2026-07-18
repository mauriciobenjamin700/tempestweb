"""Load an OpenAPI document from a local file path or an ``http(s)`` URL."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

__all__ = ["load_spec", "SpecLoadError"]


class SpecLoadError(RuntimeError):
    """Raised when an OpenAPI source cannot be fetched or parsed."""


def load_spec(source: str, *, timeout: float = 30.0) -> dict[str, Any]:
    """Load and parse an OpenAPI 3.x document.

    Args:
        source: A local file path or an ``http(s)`` URL to an ``openapi.json``
            (e.g. a FastAPI ``/openapi.json`` endpoint).
        timeout: Network timeout in seconds when ``source`` is a URL.

    Returns:
        The parsed OpenAPI document.

    Raises:
        SpecLoadError: When the source cannot be read, fetched, or parsed as
            JSON.
    """
    if source.startswith("http://") or source.startswith("https://"):
        try:
            with urllib.request.urlopen(source, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
        except Exception as exc:
            raise SpecLoadError(f"Failed to fetch {source}: {exc}") from exc
    else:
        path = Path(source)
        if not path.is_file():
            raise SpecLoadError(f"No such OpenAPI file: {source}")
        raw = path.read_text(encoding="utf-8")

    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SpecLoadError(
            f"Could not parse {source} as JSON. Only openapi.json (JSON) is "
            "supported — point at the FastAPI /openapi.json endpoint."
        ) from exc

    if not isinstance(document, dict):
        raise SpecLoadError(f"{source} is not a JSON object.")
    return document
