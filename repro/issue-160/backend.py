"""Real backend for the issue #160 reproduction.

The earlier reproduction attempts served the artifact from a static file server
with injected latency. This is a service: it authenticates, answers the panel's
data endpoints, keeps a per-tick script so a run is repeatable, logs every
request (so the service-worker precache is *visible* rather than assumed), and
serves the built Mode A artifact from the **same origin** as the API — which is
what lets the app call it at all.

Two arms, chosen with ``--arm``:

``clean``
    Every ``/api/metrics`` tick returns a finite ``load_pct``. This is the arm
    that tests the environment alone (cold Pyodide CDN, a freshly registered
    service worker precaching the shell, panel-sized batches).

``drain``
    Tick 2 reports a draining node: ``alerts`` appear *and* ``load_pct`` is the
    string ``"NaN"`` — what a JSON encoder emits for a non-finite float, since
    bare ``NaN`` is not JSON. Tick 3 reports finite numbers again, a ninth table
    column and a new owner hint.

Run:
    uv run --frozen python backend.py --port 8901 --dist app/dist/wasm --arm drain
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

#: Table body served by ``/api/rows`` — 40 rows × 8 columns, panel volume.
ROWS: list[list[str]] = [
    [
        f"tnl-{index:03d}",
        f"tunnel-{index}",
        f"host-{index % 7}.acme.internal",
        ["sa-east-1", "us-east-1", "eu-west-1"][index % 3],
        ["online", "degraded", "offline"][index % 3],
        f"{12 + index % 40} ms",
        f"{index * 1024} B",
        f"{index * 2048} B",
    ]
    for index in range(40)
]


def build_app(dist: Path, arm: str, log_path: Path, latency_ms: int = 0) -> FastAPI:
    """Build the service that hosts the panel and its API.

    Args:
        dist: The built Mode A artifact directory, served at ``/``.
        arm: ``"clean"`` or ``"drain"`` (see the module docstring).
        log_path: File the request log is appended to, one JSON object per line.
        latency_ms: Artificial delay applied to **every** request. CDP network
            throttling only shapes the page's own traffic, so the service worker
            precaches at full speed and never competes with the boot. Server-side
            latency hits page and worker alike, which is what a real deployment
            does and what makes the precache still be in flight at mount time.

    Returns:
        The FastAPI application.
    """
    app = FastAPI()
    state: dict[str, Any] = {"tick": 0}

    @app.middleware("http")
    async def log_requests(request: Request, call_next: Any) -> Any:  # noqa: ANN401
        """Append one JSON line per request, so precache traffic is measurable.

        Args:
            request: The inbound request.
            call_next: The downstream ASGI handler.

        Returns:
            The downstream response.
        """
        started = time.time()
        if latency_ms > 0:
            await asyncio.sleep(latency_ms / 1000.0)
        response = await call_next(request)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "t": round(started, 4),
                        "method": request.method,
                        "path": request.url.path,
                        "status": response.status_code,
                        "sw": request.headers.get("service-worker") or "",
                        "dest": request.headers.get("sec-fetch-dest") or "",
                    }
                )
                + "\n"
            )
        return response

    @app.post("/api/login")
    async def login(payload: dict[str, Any]) -> JSONResponse:
        """Authenticate the panel user.

        Args:
            payload: ``{"user": ..., "password": ...}``.

        Returns:
            The session envelope on success, 401 otherwise.
        """
        if payload.get("password") != "s3cr3t":
            return JSONResponse({"error": "bad credentials"}, status_code=401)
        return JSONResponse({"token": "tok-160", "user": payload.get("user", "")})

    @app.get("/api/rows")
    async def rows() -> JSONResponse:
        """Return the table body.

        Returns:
            ``{"rows": [[cell, ...], ...]}`` with 40 rows of 8 cells.
        """
        return JSONResponse({"rows": ROWS})

    @app.get("/api/metrics")
    async def metrics() -> JSONResponse:
        """Return this tick's metrics, following the arm's script.

        Returns:
            The metrics envelope for the current tick.
        """
        state["tick"] += 1
        tick = int(state["tick"])
        body: dict[str, Any] = {
            "tick": tick,
            "used": 40.0 + tick,
            "capacity": 100.0,
            "load_pct": round(0.30 + 0.05 * (tick % 5), 4),
            "alerts": 0,
            "owner_hint": "responsável",
        }
        if arm == "drain":
            if tick == 2:
                body["alerts"] = 3
                body["load_pct"] = "NaN"
            elif tick >= 3:
                body["alerts"] = 3 + tick
                body["owner_hint"] = "dono"
                body["extra_column"] = "uptime"
        else:
            body["alerts"] = 0 if tick % 3 else 2
        return JSONResponse(body)

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        """Report liveness and the arm in force.

        Returns:
            ``{"ok": True, "arm": ..., "tick": ...}``.
        """
        return {"ok": True, "arm": arm, "tick": state["tick"]}

    app.mount("/", StaticFiles(directory=str(dist), html=True), name="artifact")
    return app


def main() -> None:
    """Parse the CLI arguments and serve the panel."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--arm", choices=("clean", "drain"), default="clean")
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--latency-ms", type=int, default=0)
    args = parser.parse_args()
    args.log.write_text("", encoding="utf-8")
    uvicorn.run(
        build_app(args.dist.resolve(), args.arm, args.log.resolve(), args.latency_ms),
        host="127.0.0.1",
        port=args.port,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
