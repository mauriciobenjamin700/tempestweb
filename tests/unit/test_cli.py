"""The CLI parser is wired and `tempestweb` (no args) prints help."""

from __future__ import annotations

from tempestweb.cli.main import build_parser, main


def test_parser_builds() -> None:
    parser = build_parser()
    args = parser.parse_args(["build", "--mode", "server"])
    assert args.command == "build"
    assert args.mode == "server"


def test_main_no_command_returns_zero() -> None:
    assert main([]) == 0
