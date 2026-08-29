"""Issue #160 reproduction app — a Mode A admin panel with a real backend.

The app mirrors the shape the report names, because the three conditions the
earlier reproduction attempts lacked are all shape or environment:

* **root swap** — one ``Column(key="root")`` holds both screens, so logging in
  produces a fine-grained batch (the ``AppBar`` is recursed into, not replaced),
  which is the only way a patch can address ``…/appbar-actions/1`` at all;
* **a real backend** — every screen state comes from ``native.http.request``
  against the sibling FastAPI service, including a 7 s poll that keeps running
  after the swap, with ``set_state`` called before **and** after each ``await``;
* **panel volume** — a ``DataTable`` of 40 rows × 8 columns, a filter ``Row`` of
  four ``Input``s, KPI cards and a usage bar, so a batch is hundreds of patches
  rather than three.

The ``AppBar`` carries one action while the panel is quiet and a second one
(``act-alerts``) as soon as the backend reports open alerts, which is what makes
``appbar-actions`` a container whose child count grows *after* the swap — the
precondition for the reported failure.

The usage bar's width is the ``load_pct`` the backend computed, scaled to
pixels. That is ordinary panel code, and it is also the trigger: the backend's
encoder stringifies a non-finite float (the correct thing to do — bare ``NaN``
is not JSON), so a draining node arrives as ``"NaN"``, ``float("NaN")`` is a
``nan``, the unbounded ``Style.width`` accepts it, and the batch Python hands to
the client then serializes as the bare token ``NaN`` — which the browser's
``JSON.parse`` rejects. See ``../README.md``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from tempest_core import App as CoreApp
from tempest_core import (
    AppBar,
    Button,
    Card,
    Column,
    DataTable,
    Edge,
    Input,
    Row,
    Style,
    Text,
    Widget,
)
from tempestweb.native.http import request
from tempestweb.runtime import spawn

#: Seconds between two poll ticks, matching the panel the report came from.
POLL_INTERVAL_S: float = 7.0

#: The table's column labels; the poll can append a ninth one.
BASE_COLUMNS: tuple[str, ...] = (
    "id",
    "tunnel",
    "host",
    "region",
    "state",
    "latency",
    "bytes in",
    "bytes out",
)

#: The four filter inputs, by key and placeholder.
FILTERS: tuple[tuple[str, str], ...] = (
    ("filter-query", "buscar"),
    ("filter-region", "região"),
    ("filter-state", "estado"),
    ("filter-owner", "responsável"),
)


@dataclass
class PanelState:
    """State of the admin panel.

    Attributes:
        logged_in: Whether the dashboard (rather than the login screen) is shown.
        phase: A coarse lifecycle label rendered as text.
        user: The e-mail typed into the login form.
        rows: The table body, as a matrix of string cells.
        columns: The table's current column labels.
        alerts: How many open alerts the backend reports.
        used: Used capacity, from the poll.
        capacity: Total capacity, from the poll.
        load_pct: The load fraction the backend reports, already computed there.
            Its encoder stringifies a non-finite float, so a draining node
            arrives as the string ``"NaN"`` — and ``float("NaN")`` is a ``nan``
            the unbounded ``Style.width`` accepts.
        tick: How many poll ticks have completed.
        filter_hint: The fourth filter's placeholder, changed by the poll so a
            batch aborted earlier leaves a measurable stale value.
        error: The last error surfaced to the UI.
    """

    logged_in: bool = False
    phase: str = "idle"
    user: str = "admin@acme.com"
    rows: list[list[str]] = field(default_factory=list)
    columns: list[str] = field(default_factory=lambda: list(BASE_COLUMNS))
    alerts: int = 0
    used: float = 0.0
    capacity: float = 1.0
    load_pct: float = 0.0
    tick: int = 0
    probes: int = 0
    backend_up: bool = False
    filter_hint: str = "responsável"
    error: str = ""


#: The task polling ``/api/health`` from the login screen, once armed.
_PROBE: Any = None


def _arm_probe(app: CoreApp[PanelState]) -> None:
    """Start the login-screen health probe on the first build that has a loop.

    The report's failure needs ``appbar-actions`` to grow *before* the root swap,
    and it correlates with the window in which the service worker is still
    precaching. Nothing in Mode A runs between ``start()`` and ``mount()`` — the
    bootstrap does not yield there — so the earliest an app can act is the first
    rebuild, which the client's own ``media`` report triggers milliseconds after
    mount. This arms there: ``get_running_loop`` fails during the initial build
    (JS called into Python synchronously) and succeeds from then on.

    Args:
        app: The application handle the probe drives.
    """
    global _PROBE
    if _PROBE is not None:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    async def probe() -> None:
        """Poll ``/api/health`` every two seconds while the login screen is up."""
        while not app.state.logged_in:
            try:
                health = await _get("/api/health")
            except Exception:  # noqa: BLE001 — a probe failure is a UI state
                health = {}
            up = bool(health.get("ok"))
            app.set_state(lambda s: setattr(s, "probes", s.probes + 1))
            app.set_state(lambda s, up=up: setattr(s, "backend_up", up))
            await asyncio.sleep(2.0)

    _PROBE = loop.create_task(probe())


def make_state() -> PanelState:
    """Build the initial panel state.

    Returns:
        A fresh :class:`PanelState` on the login screen.
    """
    return PanelState()


async def _get(path: str) -> dict[str, Any]:
    """Fetch a JSON object from the sibling backend.

    Args:
        path: The absolute request path (same origin as the artifact).

    Returns:
        The decoded JSON body, or an empty dict when the body is not an object.
    """
    response = await request("GET", path)
    body = response.json_body
    return body if isinstance(body, dict) else {}


def _rows_from(payload: dict[str, Any]) -> list[list[str]]:
    """Coerce a rows payload into the string matrix the table draws.

    Args:
        payload: The ``/api/rows`` body.

    Returns:
        The rows as lists of strings.
    """
    raw = payload.get("rows", [])
    if not isinstance(raw, list):
        return []
    return [[str(cell) for cell in row] for row in raw]


def view(app: CoreApp[PanelState]) -> Widget:
    """Render the panel for the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree: the login screen or the dashboard, under one root whose
        key never changes (so the swap is diffed, not replaced).
    """
    state = app.state

    async def poll_once() -> None:
        """Run one poll tick: rows, then metrics, with a ``set_state`` each."""
        app.set_state(lambda s: setattr(s, "phase", "polling"))
        rows_payload = await _get("/api/rows")
        app.set_state(lambda s: setattr(s, "rows", _rows_from(rows_payload)))
        metrics = await _get("/api/metrics")

        def commit(s: PanelState) -> None:
            s.phase = "live"
            s.tick += 1
            s.alerts = int(metrics.get("alerts", 0))
            s.used = float(metrics.get("used", 0.0))
            s.capacity = float(metrics.get("capacity", 1.0))
            s.load_pct = float(metrics.get("load_pct", 0.0))
            s.columns = list(BASE_COLUMNS)
            if metrics.get("extra_column"):
                s.columns.append(str(metrics["extra_column"]))
            s.filter_hint = str(metrics.get("owner_hint", "responsável"))

        app.set_state(commit)

    async def poll_forever() -> None:
        """Poll the backend every :data:`POLL_INTERVAL_S` seconds, forever."""
        while True:
            try:
                await poll_once()
            except Exception as exc:  # noqa: BLE001 — surface any failure to the UI
                message = str(exc)
                app.set_state(lambda s, text=message: setattr(s, "error", text))
            await asyncio.sleep(POLL_INTERVAL_S)

    async def sign_in() -> None:
        """Authenticate against the backend and swap the root to the panel."""
        app.set_state(lambda s: setattr(s, "phase", "authenticating"))
        response = await request(
            "POST", "/api/login", json={"user": app.state.user, "password": "s3cr3t"}
        )
        if not response.ok:
            app.set_state(lambda s: setattr(s, "error", f"login {response.status}"))
            return
        app.set_state(lambda s: setattr(s, "logged_in", True))
        await poll_once()
        spawn(poll_forever())

    def on_user(event: Any) -> None:  # noqa: ANN401 — the typed change event
        """Record the typed e-mail.

        Args:
            event: The ``TextChangeEvent`` the core coerced from the wire payload.
        """
        value = getattr(event, "value", "")
        app.set_state(lambda s: setattr(s, "user", str(value)))

    _arm_probe(app)

    actions: list[Widget] = [
        Button(label="Atualizar", key="act-refresh", on_click=lambda: None)
    ]
    if not state.logged_in and state.probes % 2 == 1:
        actions.append(
            Button(label="Reconectar", key="act-reconnect", on_click=lambda: None)
        )
    if state.alerts > 0:
        actions.append(
            Button(
                label=f"Alertas ({state.alerts})",
                key="act-alerts",
                on_click=lambda: None,
            )
        )

    bar = AppBar(
        key="appbar",
        title="tw160 — painel" if state.logged_in else "tw160 — entrar",
        actions=actions,
    )

    if not state.logged_in:
        return Column(
            key="root",
            style=Style(gap=16.0, padding=Edge.all(16)),
            children=[
                bar,
                Card(
                    key="login-card",
                    children=[
                        Text(content="Acesso restrito", key="login-title"),
                        Input(
                            key="login-user",
                            value=state.user,
                            placeholder="e-mail",
                            on_change=on_user,
                        ),
                        Input(
                            key="login-pass",
                            value="s3cr3t",
                            placeholder="senha",
                            secure=True,
                        ),
                        Button(label="Entrar", key="login-submit", on_click=sign_in),
                        Text(content=f"status: {state.phase}", key="login-status"),
                    ],
                ),
            ],
        )

    fraction = state.load_pct
    filters: list[Widget] = []
    for index, (key, placeholder) in enumerate(FILTERS):
        hint = state.filter_hint if index == len(FILTERS) - 1 else placeholder
        filters.append(Input(key=key, value="", placeholder=hint))

    return Column(
        key="root",
        style=Style(gap=16.0, padding=Edge.all(16)),
        children=[
            bar,
            Row(key="filters", style=Style(gap=8.0), children=filters),
            Column(
                key="usage",
                style=Style(gap=4.0),
                children=[
                    Text(
                        content=f"uso {state.used:.0f}/{state.capacity:.0f}",
                        key="usage-label",
                    ),
                    Column(
                        key="usage-bar",
                        style=Style(
                            width=fraction * 240.0,
                            height=8.0,
                            radius=4.0,
                        ),
                        children=[Text(content="", key="usage-fill")],
                    ),
                ],
            ),
            Row(
                key="kpis",
                style=Style(gap=12.0),
                children=[
                    Card(
                        key=f"kpi-{index}",
                        children=[
                            Text(
                                content=f"KPI {index}: {state.tick * (index + 1)}",
                                key=f"kpi-text-{index}",
                            )
                        ],
                    )
                    for index in range(4)
                ],
            ),
            DataTable(key="table", columns=state.columns, rows=state.rows),
            Text(content=f"tick {state.tick} · {state.phase}", key="footer"),
        ],
    )
