"""O1 — Logger: structured logging with pluggable sinks and typed levels.

A logger fans a structured record (level + message + arbitrary fields) out to one
or more :class:`LoggerSink` callables. The default sink prints to the console; in
Mode A (browser) that is the dev console, and network sinks must be async so they
never block the UI thread. Swapping where logs go is just passing a different
sink list to :func:`create_logger` — call sites stay identical.

Example:
    >>> records: list[LogRecord] = []
    >>> log = create_logger(sinks=[console_sink, records.append], level="INFO")
    >>> log.debug("ignored, below threshold")
    >>> log.info("user logged in", user_id="u1")
    >>> [r.message for r in records]
    ['user logged in']
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

__all__ = [
    "LogLevel",
    "LogRecord",
    "LoggerSink",
    "Logger",
    "console_sink",
    "create_logger",
]

#: The set of severity levels, ordered from least to most severe.
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

#: Numeric severity used to compare levels for threshold filtering.
_LEVEL_ORDER: dict[str, int] = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}


@dataclass(frozen=True)
class LogRecord:
    """One structured log entry handed to every sink.

    Attributes:
        level: The severity of this record.
        message: The human-readable log message.
        fields: Arbitrary JSON-able structured fields attached at the call site.
    """

    level: LogLevel
    message: str
    fields: dict[str, Any] = field(default_factory=dict)


class LoggerSink(Protocol):
    """A destination for log records.

    A sink is any callable taking a single :class:`LogRecord`. This is
    deliberately the same shape as ``list.append`` and ``print``-style helpers,
    so capturing logs in a test is just passing ``my_list.append`` as a sink.
    """

    def __call__(self, record: LogRecord) -> None:
        """Consume a single log record.

        Args:
            record: The structured record to handle.

        Returns:
            None.
        """
        ...


def console_sink(record: LogRecord) -> None:
    """Print a record to the console in a stable, greppable single-line format.

    Args:
        record: The structured record to print.

    Returns:
        None.
    """
    suffix: str = f" {record.fields}" if record.fields else ""
    print(f"[{record.level}] {record.message}{suffix}")


class Logger:
    """A structured logger that fans records out to its sinks above a threshold.

    Records below ``level`` are dropped before any sink runs, so an expensive
    network sink never sees a filtered-out ``DEBUG`` line. A sink that raises is
    isolated: the remaining sinks still receive the record, because one broken
    destination must not take down logging for the rest.
    """

    def __init__(self, sinks: list[LoggerSink], level: LogLevel = "INFO") -> None:
        """Initialize the logger.

        Args:
            sinks: The destinations every passing record is delivered to. A copy
                is stored so later mutation of the caller's list has no effect.
            level: The minimum severity a record must have to be delivered.
        """
        self._sinks: list[LoggerSink] = list(sinks)
        self._level: LogLevel = level

    @property
    def level(self) -> LogLevel:
        """The current minimum severity threshold.

        Returns:
            The active :data:`LogLevel`.
        """
        return self._level

    def set_level(self, level: LogLevel) -> None:
        """Change the minimum severity threshold at runtime.

        Args:
            level: The new minimum severity.

        Returns:
            None.
        """
        self._level = level

    def _enabled(self, level: LogLevel) -> bool:
        """Whether a record at ``level`` clears the current threshold.

        Args:
            level: The severity to test.

        Returns:
            ``True`` if a record at ``level`` should be delivered.
        """
        return _LEVEL_ORDER[level] >= _LEVEL_ORDER[self._level]

    def log(self, level: LogLevel, message: str, **fields: Any) -> None:  # noqa: ANN401 - structured log fields are arbitrary JSON-able
        """Emit a record at an explicit level.

        Args:
            level: The severity of the record.
            message: The log message.
            **fields: Arbitrary structured fields attached to the record.

        Returns:
            None.
        """
        if not self._enabled(level):
            return
        record: LogRecord = LogRecord(level=level, message=message, fields=fields)
        for sink in self._sinks:
            try:
                sink(record)
            except Exception:  # noqa: BLE001 - one bad sink must not break others
                continue

    def debug(self, message: str, **fields: Any) -> None:  # noqa: ANN401 - structured log fields are arbitrary JSON-able
        """Emit a ``DEBUG`` record.

        Args:
            message: The log message.
            **fields: Arbitrary structured fields.

        Returns:
            None.
        """
        self.log("DEBUG", message, **fields)

    def info(self, message: str, **fields: Any) -> None:  # noqa: ANN401 - structured log fields are arbitrary JSON-able
        """Emit an ``INFO`` record.

        Args:
            message: The log message.
            **fields: Arbitrary structured fields.

        Returns:
            None.
        """
        self.log("INFO", message, **fields)

    def warning(self, message: str, **fields: Any) -> None:  # noqa: ANN401 - structured log fields are arbitrary JSON-able
        """Emit a ``WARNING`` record.

        Args:
            message: The log message.
            **fields: Arbitrary structured fields.

        Returns:
            None.
        """
        self.log("WARNING", message, **fields)

    def error(self, message: str, **fields: Any) -> None:  # noqa: ANN401 - structured log fields are arbitrary JSON-able
        """Emit an ``ERROR`` record.

        Args:
            message: The log message.
            **fields: Arbitrary structured fields.

        Returns:
            None.
        """
        self.log("ERROR", message, **fields)

    def critical(self, message: str, **fields: Any) -> None:  # noqa: ANN401 - structured log fields are arbitrary JSON-able
        """Emit a ``CRITICAL`` record.

        Args:
            message: The log message.
            **fields: Arbitrary structured fields.

        Returns:
            None.
        """
        self.log("CRITICAL", message, **fields)


def create_logger(
    sinks: list[LoggerSink] | None = None, level: LogLevel = "INFO"
) -> Logger:
    """Create a :class:`Logger` with the given sinks and threshold.

    Args:
        sinks: The destinations to deliver records to. Defaults to a single
            :func:`console_sink` when omitted.
        level: The minimum severity to deliver.

    Returns:
        A configured :class:`Logger`.
    """
    return Logger(sinks=sinks if sinks is not None else [console_sink], level=level)
