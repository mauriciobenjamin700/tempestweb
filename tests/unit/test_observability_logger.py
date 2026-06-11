"""Unit tests for O1 logger: levels, structured fields, sinks, isolation."""

from __future__ import annotations

from tempestweb.observability import (
    LogRecord,
    console_sink,
    create_logger,
)


def test_records_below_threshold_are_dropped() -> None:
    captured: list[LogRecord] = []
    log = create_logger(sinks=[captured.append], level="INFO")

    log.debug("dropped")
    log.info("kept")

    assert [r.message for r in captured] == ["kept"]


def test_structured_fields_attached_to_record() -> None:
    captured: list[LogRecord] = []
    log = create_logger(sinks=[captured.append])

    log.info("user logged in", user_id="u1", attempt=2)

    assert captured[0].fields == {"user_id": "u1", "attempt": 2}


def test_every_level_helper_sets_its_level() -> None:
    captured: list[LogRecord] = []
    log = create_logger(sinks=[captured.append], level="DEBUG")

    log.debug("d")
    log.info("i")
    log.warning("w")
    log.error("e")
    log.critical("c")

    assert [r.level for r in captured] == [
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ]


def test_fans_out_to_multiple_sinks() -> None:
    a: list[LogRecord] = []
    b: list[LogRecord] = []
    log = create_logger(sinks=[a.append, b.append])

    log.info("hello")

    assert len(a) == 1
    assert len(b) == 1


def test_console_and_custom_sink_receive_same_record(capsys) -> None:
    captured: list[LogRecord] = []
    log = create_logger(sinks=[console_sink, captured.append])

    log.warning("disk low", free_mb=12)

    out = capsys.readouterr().out
    assert "[WARNING] disk low" in out
    assert "free_mb" in out
    assert captured[0].message == "disk low"


def test_a_raising_sink_does_not_break_other_sinks() -> None:
    captured: list[LogRecord] = []

    def boom(_record: LogRecord) -> None:
        raise RuntimeError("sink failure")

    log = create_logger(sinks=[boom, captured.append])
    log.info("still delivered")

    assert captured[0].message == "still delivered"


def test_set_level_changes_threshold_at_runtime() -> None:
    captured: list[LogRecord] = []
    log = create_logger(sinks=[captured.append], level="ERROR")

    log.warning("dropped")
    log.set_level("DEBUG")
    log.warning("kept")

    assert [r.message for r in captured] == ["kept"]


def test_default_logger_uses_console_sink(capsys) -> None:
    log = create_logger()
    log.info("default sink")

    assert "[INFO] default sink" in capsys.readouterr().out
