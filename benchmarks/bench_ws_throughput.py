"""Mode B throughput: how many patch batches a session sustains (Track S — S9).

The reconciler benchmark measures the tree; this measures the **session** — the
loop a real Mode B app spends its life in: an event arrives, a handler mutates
state, the core diffs, the transport ships a batch. Nothing measured it before
(tempestweb#120), so there was no number for "how many interactions per second
does one connection take", and none for what N connections do to each other.

The transport here counts instead of writing to a socket, on purpose: a socket
measures the kernel and the runner's loopback, and what is under test is the
Python above it. Adding the network back only ever makes the number smaller, so
this is the ceiling.

Run it::

    uv run python benchmarks/bench_ws_throughput.py
    uv run python benchmarks/bench_ws_throughput.py --sessions 25 --events 200
"""

from __future__ import annotations

import argparse
import asyncio
import time
from typing import Any

from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempestweb.runtime.session import AppSession


class CountingTransport:
    """A transport that counts what a socket would have written."""

    def __init__(self) -> None:
        """Start every counter at zero."""
        self.batches: int = 0
        self.patches: int = 0

    async def send_patches(self, patches: list[dict[str, Any]]) -> None:
        """Count one batch.

        Args:
            patches: The wire patches for this tick.
        """
        self.batches += 1
        self.patches += len(patches)

    async def send_navigate(self, path: str) -> None:
        """Ignore navigation.

        Args:
            path: The new path.
        """
        return None

    async def send_native_call(
        self, call_id: str, capability: str, args: dict[str, Any]
    ) -> None:
        """Ignore native calls.

        Args:
            call_id: Correlation id.
            capability: Capability name.
            args: Capability args.
        """
        return None

    async def send_native_subscribe(
        self, sub_id: str, capability: str, args: dict[str, Any]
    ) -> None:
        """Ignore subscriptions.

        Args:
            sub_id: Subscription id.
            capability: Capability name.
            args: Capability args.
        """
        return None

    async def send_native_unsubscribe(self, sub_id: str) -> None:
        """Ignore unsubscriptions.

        Args:
            sub_id: Subscription id.
        """
        return None

    def on_event(self, handler: Any) -> None:  # noqa: ANN401 — sink, unused here
        """Ignore the event sink.

        Args:
            handler: The sink.
        """
        return None

    def on_native_result(self, handler: Any) -> None:  # noqa: ANN401 — sink, unused
        """Ignore the native-result sink.

        Args:
            handler: The sink.
        """
        return None

    def on_native_event(self, handler: Any) -> None:  # noqa: ANN401 — sink, unused
        """Ignore the native-event sink.

        Args:
            handler: The sink.
        """
        return None

    async def close(self) -> None:
        """Close is a no-op."""
        return None


def _view(rows: int) -> Any:  # noqa: ANN401 — returns the app's view callable
    """Build a view function over a list of ``rows`` rows.

    Args:
        rows: How many rows the screen shows.

    Returns:
        A ``view(app) -> Widget`` closure whose tree depends on ``app.state``.
    """

    def view(app: App[int]) -> Widget:
        """Render the list, marking the selected row.

        Args:
            app: The application handle; its state is the selected index.

        Returns:
            The column of rows.
        """
        selected = app.state % rows
        return Column(
            key="root",
            style=Style(gap=4.0),
            children=[
                Row(
                    key=f"row-{i}",
                    children=[
                        Text(content=f"Item {i}", key=f"label-{i}"),
                        Button(
                            key=f"btn-{i}",
                            label="picked" if i == selected else "pick",
                            on_click=lambda: None,
                        ),
                    ],
                )
                for i in range(rows)
            ],
        )

    return view


async def _run_session(rows: int, events: int) -> tuple[CountingTransport, float]:
    """Drive one session through ``events`` interactions.

    Each dispatch is followed by two bare ``sleep(0)`` yields, so the coalesced
    rebuild and its send actually run — the way the server's loop does between two
    client messages. Without them the loop would measure dispatch alone and report
    a throughput no client can observe.

    Args:
        rows: Rows on the screen.
        events: How many click events to dispatch.

    Returns:
        The transport (with its counters) and the elapsed seconds.
    """
    transport = CountingTransport()
    session: AppSession[int] = AppSession(
        state_factory=lambda: 0,
        view=_view(rows),
        transport=transport,  # type: ignore[arg-type]
    )
    await session.start()
    app = session.app
    assert app is not None

    start = time.perf_counter()
    for index in range(events):
        app.set_state(lambda state: state + 1)
        await session.dispatch(
            {"type": "click", "key": f"btn-{index % rows}", "payload": {}}
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)
    elapsed = time.perf_counter() - start
    await session.close()
    return transport, elapsed


async def measure(rows: int, events: int, sessions: int) -> dict[str, float]:
    """Measure one session alone, then ``sessions`` of them concurrently.

    Args:
        rows: Rows on each screen.
        events: Events per session.
        sessions: How many concurrent sessions in the second phase.

    Returns:
        ``{"single_eps", "concurrent_eps", "per_session_eps", "degradation"}`` in
        events per second.
    """
    _, solo_elapsed = await _run_session(rows, events)
    single_eps = events / solo_elapsed

    start = time.perf_counter()
    await asyncio.gather(*(_run_session(rows, events) for _ in range(sessions)))
    concurrent_elapsed = time.perf_counter() - start
    total_events = events * sessions
    concurrent_eps = total_events / concurrent_elapsed
    per_session_eps = concurrent_eps / sessions

    return {
        "single_eps": single_eps,
        "concurrent_eps": concurrent_eps,
        "per_session_eps": per_session_eps,
        "degradation": single_eps / per_session_eps,
    }


def main() -> None:
    """Parse args, measure, and print the throughput table."""
    parser = argparse.ArgumentParser(description="tempestweb Mode B throughput")
    parser.add_argument("--rows", type=int, default=50, help="rows per screen")
    parser.add_argument("--events", type=int, default=100, help="events per session")
    parser.add_argument("--sessions", type=int, default=10, help="concurrent sessions")
    args = parser.parse_args()

    result = asyncio.run(measure(args.rows, args.events, args.sessions))
    print(
        f"tempestweb Mode B throughput — {args.rows} rows, {args.events} events, "
        f"{args.sessions} sessions\n"
    )
    solo = result["single_eps"]
    total = result["concurrent_eps"]
    each = result["per_session_eps"]
    print(f"one session alone      {solo:10,.0f} events/s")
    print(f"{args.sessions} sessions together   {total:10,.0f} events/s")
    print(f"  per session          {each:10,.0f} events/s")
    print(
        f"\nper-session degradation under load: {result['degradation']:.2f}x "
        "(1.0 = perfect scaling)"
    )


if __name__ == "__main__":
    main()
