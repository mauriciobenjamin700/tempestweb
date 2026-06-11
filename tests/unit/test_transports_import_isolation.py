"""Mode A must import without the Mode B (Starlette) server stack.

In Mode A the package is imported inside Pyodide, where Starlette/uvicorn are not
installed. So importing the WASM transport — and the runtime ``bootstrap`` entry
the in-browser glue calls — must not eagerly pull the WebSocket/SSE transports.
``tempestweb.transports`` loads those lazily (PEP 562 ``__getattr__``); these tests
pin that, and that lazy access still resolves them when the server extra is present.
"""

from __future__ import annotations

import subprocess
import sys

_HEAVY = ("starlette", "fastapi", "uvicorn", "websockets")


def _modules_after(import_line: str) -> set[str]:
    """Return the heavy server modules present after running ``import_line``.

    Runs in a fresh interpreter so an already-imported Starlette in the test
    process cannot mask an eager import.

    Args:
        import_line: The import statement to execute in the child interpreter.

    Returns:
        The set of heavy server module prefixes that got imported.
    """
    code = (
        "import sys\n"
        f"{import_line}\n"
        "loaded = set(sys.modules)\n"
        f"heavy = {_HEAVY!r}\n"
        "print(','.join(sorted(m for m in loaded "
        "if any(m == h or m.startswith(h + '.') for h in heavy))))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    return {name for name in out.stdout.strip().split(",") if name}


def test_wasm_transport_import_pulls_no_server_stack() -> None:
    """Importing the WASM transport must not import Starlette/FastAPI/uvicorn."""
    pulled = _modules_after("from tempestweb.transports import WasmTransport")
    assert pulled == set(), f"Mode A import pulled the server stack: {sorted(pulled)}"


def test_runtime_bootstrap_import_pulls_no_server_stack() -> None:
    """The in-browser glue imports ``bootstrap``; it must stay server-free."""
    pulled = _modules_after("from tempestweb.runtime.wasm_main import bootstrap")
    assert pulled == set(), (
        f"bootstrap import pulled the server stack: {sorted(pulled)}"
    )


def test_mode_b_transports_still_resolve_lazily() -> None:
    """Lazy access of the Mode B transports still returns the real classes."""
    from tempestweb.transports import SSETransport, WebSocketTransport

    assert WebSocketTransport.__name__ == "WebSocketTransport"
    assert SSETransport.__name__ == "SSETransport"
