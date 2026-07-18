"""OpenAPI → typed tempestweb API client generation.

Reads an OpenAPI 3.x document (FastAPI ``/openapi.json`` or a file) and emits a
per-tag client: ``@dataclass`` models plus a service class per route group that
calls :func:`tempestweb.native.http.request`.
"""

from __future__ import annotations

from tempestweb.cli.openapi.generate import generate, ref_name
from tempestweb.cli.openapi.load import SpecLoadError, load_spec

__all__ = ["generate", "ref_name", "load_spec", "SpecLoadError"]
