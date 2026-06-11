"""tempestweb.server — Mode B FastAPI host (WebSocket + SSE).

Re-exports the server factory and the server class. See ``docs/plan.md``
(Trilho B) and ``docs/contract.md`` for the wire format carried over both
transports.
"""

from __future__ import annotations

from tempestweb.server.app import TempestWebServer, create_app

__all__ = ["TempestWebServer", "create_app"]
