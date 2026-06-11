"""File watcher that drives the reload signal.

The watcher observes a project directory and, whenever a watched file changes,
calls :meth:`ReloadSignal.trigger`. It is deliberately transport-agnostic: it
knows nothing about WASM, WebSocket or browsers — it only turns filesystem
changes into reload events. Whoever owns the transport subscribes to the same
:class:`~tempestweb.devserver.reload.ReloadSignal`.

The underlying change stream defaults to :func:`watchfiles.awatch` but can be
replaced with any async iterable of change batches, which is how the tests drive
the watcher deterministically without touching the filesystem.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable, Iterable, Sequence
from pathlib import Path

from tempestweb.devserver.reload import ReloadEvent, ReloadKind, ReloadSignal

__all__ = ["DEFAULT_WATCH_SUFFIXES", "ChangeStream", "FileWatcher"]

# Only changes to these suffixes trigger a reload by default. Editors write
# swap/temp files constantly; restricting suffixes keeps the loop quiet.
DEFAULT_WATCH_SUFFIXES: tuple[str, ...] = (".py", ".html", ".css", ".js")

# A change batch is the set of absolute paths that changed together. This mirrors
# the shape of one ``watchfiles.awatch`` yield (a set of ``(Change, path)`` pairs)
# after we discard the change kind — we only care *which* paths moved.
ChangeBatch = Sequence[str]

# A change stream is any async iterable of change batches. ``watchfiles.awatch``
# yields ``set[tuple[Change, str]]``; the adapter below normalizes it to paths.
ChangeStream = AsyncIterator[ChangeBatch]


class FileWatcher:
    """Turns filesystem changes under a project root into reload events.

    The watcher filters changes by suffix, deduplicates a batch into a sorted
    tuple of project-relative paths, and triggers the shared
    :class:`ReloadSignal` once per batch.
    """

    def __init__(
        self,
        root: str | os.PathLike[str],
        signal: ReloadSignal,
        *,
        suffixes: Iterable[str] = DEFAULT_WATCH_SUFFIXES,
        kind: ReloadKind = ReloadKind.RESTART,
    ) -> None:
        """Initialize the watcher.

        Args:
            root: The project directory to watch.
            signal: The reload hub to trigger on each relevant change.
            suffixes: File suffixes that count as a reload-worthy change. A path
                whose suffix is not listed is ignored. Defaults to
                :data:`DEFAULT_WATCH_SUFFIXES`.
            kind: The reload kind emitted for every change. Defaults to
                :attr:`ReloadKind.RESTART` (clean state — the v1 behavior).
        """
        self.root: Path = Path(root).resolve()
        self.signal: ReloadSignal = signal
        self.suffixes: tuple[str, ...] = tuple(suffixes)
        self.kind: ReloadKind = kind

    def _relevant(self, paths: ChangeBatch) -> tuple[str, ...]:
        """Filter a change batch to reload-worthy, project-relative paths.

        Args:
            paths: Absolute or relative paths reported as changed.

        Returns:
            A sorted, de-duplicated tuple of paths relative to :attr:`root` (or
            the original path if it is not under the root). Empty if nothing in
            the batch matched a watched suffix.
        """
        kept: set[str] = set()
        for raw in paths:
            path = Path(raw)
            if self.suffixes and path.suffix not in self.suffixes:
                continue
            try:
                rel = path.resolve().relative_to(self.root)
                kept.add(str(rel))
            except ValueError:
                kept.add(str(path))
        return tuple(sorted(kept))

    def handle_batch(self, paths: ChangeBatch) -> ReloadEvent | None:
        """Process one change batch and trigger a reload if anything matched.

        Args:
            paths: The paths reported as changed in this batch.

        Returns:
            The emitted :class:`ReloadEvent`, or ``None`` when nothing in the
            batch matched a watched suffix (no reload triggered).
        """
        relevant = self._relevant(paths)
        if not relevant:
            return None
        return self.signal.trigger(kind=self.kind, paths=list(relevant))

    async def run(
        self,
        stream: ChangeStream | None = None,
        *,
        stream_factory: Callable[[Path], ChangeStream] | None = None,
    ) -> None:
        """Consume a change stream until it is exhausted, triggering reloads.

        Args:
            stream: An async iterable of change batches to consume directly.
                Mutually exclusive with ``stream_factory``. The tests pass this.
            stream_factory: A factory that builds the change stream from the
                resolved root. Defaults to a :func:`watchfiles.awatch` adapter.

        Raises:
            ValueError: If both ``stream`` and ``stream_factory`` are provided.
        """
        if stream is not None and stream_factory is not None:
            raise ValueError("pass either stream or stream_factory, not both")
        if stream is None:
            factory = stream_factory or _watchfiles_stream
            stream = factory(self.root)
        async for batch in stream:
            self.handle_batch(batch)


async def _watchfiles_stream(
    root: Path,
    *,
    force_polling: bool = False,
) -> ChangeStream:
    """Adapt :func:`watchfiles.awatch` into a path-only change stream.

    Args:
        root: The directory to watch.
        force_polling: Force the polling backend instead of native filesystem
            events. Defaults to ``False`` (native). Polling is slower but works
            on filesystems where native notifications are unreliable (network
            mounts, some container/WSL setups). The keyword is optional, so the
            function still satisfies the ``Callable[[Path], ChangeStream]``
            ``stream_factory`` contract when called positionally.

    Yields:
        Each batch as a sequence of changed absolute paths (the ``Change`` kind
        from watchfiles is discarded — the watcher only cares which paths moved).

    Raises:
        RuntimeError: If the ``watchfiles`` package is not installed. Install the
            CLI extra: ``pip install "tempestweb[cli]"``.
    """
    try:
        from watchfiles import awatch
    except ModuleNotFoundError as exc:  # pragma: no cover - import guard
        raise RuntimeError(
            "the dev watcher needs watchfiles; install with "
            '`pip install "tempestweb[cli]"`'
        ) from exc

    async for changes in awatch(root, force_polling=force_polling):
        yield [path for _change, path in changes]
