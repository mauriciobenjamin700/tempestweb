"""tempestweb command-line entrypoint.

This is the foundation skeleton: it wires up the subcommands so ``tempestweb
--help`` works and agents can flesh out each command in its own phase. Commands
that are not implemented yet exit with a clear "not implemented" message rather
than pretending to work.
"""

from __future__ import annotations

import argparse
import sys

__all__ = ["main", "build_parser"]


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser.

    Returns:
        The configured parser with the ``new``/``dev``/``build``/``run`` commands.
    """
    parser = argparse.ArgumentParser(
        prog="tempestweb",
        description="Build web apps in typed Python (WASM + server modes).",
    )
    sub = parser.add_subparsers(dest="command", required=False)

    new = sub.add_parser("new", help="Scaffold a new tempestweb app.")
    new.add_argument("name", help="Project name / directory.")

    dev = sub.add_parser("dev", help="Run the dev loop (watch + reload).")
    dev.add_argument(
        "--mode",
        choices=["wasm", "server"],
        default="wasm",
        help="Execution mode for the dev session.",
    )

    build = sub.add_parser("build", help="Build a deployable artifact.")
    build.add_argument(
        "--mode",
        choices=["wasm", "server"],
        default="wasm",
        help="wasm = static bundle (Pyodide); server = FastAPI app.",
    )

    run = sub.add_parser("run", help="Build and serve the app locally.")
    run.add_argument("--mode", choices=["wasm", "server"], default="wasm")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entrypoint for the ``tempestweb`` console script.

    Args:
        argv: Optional argument vector (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    # Each command is implemented in its own phase (see docs/agents/MANIFEST.md).
    print(
        f"tempestweb: command {args.command!r} is not implemented yet.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
