"""tempestweb command-line entrypoint.

Wires the ``new`` / ``dev`` / ``build`` / ``run`` subcommands to their
implementations in :mod:`tempestweb.cli.commands`. The parser keeps a stable
shape (``args.command`` plus ``args.mode`` where relevant) so it is safe to
introspect in tests and scripts; each handler delegates to a pure command
entrypoint that does the real work without touching ``argv`` or the process.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from tempestweb.cli.commands import (
    BuildError,
    DevError,
    NewError,
    RunError,
    SyncError,
    build_artifact,
    create_project,
    prepare_run,
    serve_dev,
    serve_run,
    sync_modules,
)

__all__ = ["main", "build_parser"]


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser.

    Returns:
        The configured parser with the ``new``/``dev``/``build``/``run`` commands.
    """
    parser = argparse.ArgumentParser(
        prog="tempestweb",
        description="Build web apps in typed Python (WASM + server + transpile modes).",
    )
    sub = parser.add_subparsers(dest="command", required=False)

    new = sub.add_parser("new", help="Scaffold a new tempestweb app.")
    new.add_argument("name", help="Project name / directory.")
    new.add_argument(
        "--into",
        default=".",
        help="Parent directory to create the project inside (default: cwd).",
    )
    new.add_argument(
        "--force",
        action="store_true",
        help="Write into an existing non-empty directory.",
    )
    new.add_argument(
        "--template",
        choices=["default", "pwa"],
        default="default",
        help="Scaffold template: default (two-mode counter) or pwa "
        "(Mode C installable/offline PWA).",
    )
    new.add_argument(
        "--no-verify",
        dest="verify",
        action="store_false",
        help="Skip rendering the scaffold to prove it is runnable.",
    )

    dev = sub.add_parser("dev", help="Run the dev loop (watch + reload).")
    dev.add_argument(
        "--mode",
        choices=["wasm", "transpile"],
        default="wasm",
        help="Static mode to serve with livereload (wasm or transpile).",
    )
    dev.add_argument(
        "--path",
        default=".",
        help="Project directory to watch (default: cwd).",
    )
    dev.add_argument("--host", default=None, help="Override the bind address.")
    dev.add_argument("--port", type=int, default=None, help="Override the bind port.")

    build = sub.add_parser("build", help="Build a deployable artifact.")
    build.add_argument(
        "--mode",
        choices=["wasm", "server", "transpile"],
        default="wasm",
        help="wasm = static bundle (Pyodide); server = FastAPI app; "
        "transpile = static bundle of native JS (no Python runtime, experimental).",
    )
    build.add_argument(
        "--path",
        default=".",
        help="Project directory to build (default: cwd).",
    )
    build.add_argument(
        "--out",
        default=None,
        help="Artifact output directory (default: <project>/dist/<mode>).",
    )
    build.add_argument(
        "--offline",
        action="store_true",
        help="Vendor the Pyodide runtime + wheels so wasm boots offline "
        "(downloads them at build time).",
    )

    run = sub.add_parser("run", help="Build and serve the app locally.")
    run.add_argument("--mode", choices=["wasm", "server", "transpile"], default="wasm")
    run.add_argument(
        "--path",
        default=".",
        help="Project directory to build and serve (default: cwd).",
    )
    run.add_argument("--host", default=None, help="Override the bind address.")
    run.add_argument(
        "--port",
        type=int,
        default=None,
        help="Override the bind port.",
    )
    run.add_argument(
        "--offline",
        action="store_true",
        help="Build the wasm bundle with a vendored, offline-capable Pyodide.",
    )

    sync = sub.add_parser(
        "sync",
        help="Fill [wasm].modules from the installed pure-Python dependencies.",
    )
    sync.add_argument(
        "--path",
        default=".",
        help="Project directory to sync (default: cwd).",
    )
    sync.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be added without writing tempestweb.toml.",
    )

    vapid = sub.add_parser(
        "vapid",
        help="Generate a VAPID keypair for WebPush.",
    )
    vapid.add_argument(
        "--env",
        action="store_true",
        help="Print as VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY env lines.",
    )

    return parser


def _cmd_new(args: argparse.Namespace) -> int:
    """Handle ``tempestweb new``.

    Args:
        args: Parsed arguments for the ``new`` subcommand.

    Returns:
        Process exit code.
    """
    try:
        result = create_project(
            args.name,
            parent=args.into,
            force=args.force,
            verify=args.verify,
            template=args.template,
        )
    except NewError as exc:
        print(f"tempestweb new: {exc}", file=sys.stderr)
        return 1
    print(f"Created {result.root}")
    for rel in result.files:
        print(f"  + {rel}")
    dev_cmd = (
        "tempestweb dev --mode transpile"
        if args.template == "pwa"
        else ("tempestweb dev")
    )
    print(f"\nNext:\n  cd {result.root.name}\n  {dev_cmd}")
    return 0


def _cmd_dev(args: argparse.Namespace) -> int:
    """Handle ``tempestweb dev``.

    Builds the wasm bundle, serves it with browser livereload, watches the
    project, and rebuilds + reloads on every change (Mode A). Mode B is served by
    ``tempestweb run --mode server`` instead.

    Args:
        args: Parsed arguments for the ``dev`` subcommand.

    Returns:
        Process exit code.
    """
    try:
        asyncio.run(
            serve_dev(args.path, mode=args.mode, host=args.host, port=args.port)
        )
    except DevError as exc:
        print(f"tempestweb dev: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        print("\nStopped.")
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    """Handle ``tempestweb build``.

    Args:
        args: Parsed arguments for the ``build`` subcommand.

    Returns:
        Process exit code.
    """
    try:
        result = build_artifact(
            args.path, mode=args.mode, out_dir=args.out, offline=args.offline
        )
    except BuildError as exc:
        print(f"tempestweb build: {exc}", file=sys.stderr)
        return 1
    print(f"Built {result.mode} artifact at {result.out_dir}")
    for rel in result.files:
        print(f"  + {rel}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    """Handle ``tempestweb run``.

    Builds the artifact, then serves it. Mode B (server) starts the real FastAPI
    WS/SSE host under uvicorn; Mode A (wasm) static-hosts the bundle. Both block
    until Ctrl-C.

    Args:
        args: Parsed arguments for the ``run`` subcommand.

    Returns:
        Process exit code.
    """
    try:
        plan = prepare_run(
            args.path,
            mode=args.mode,
            host=args.host,
            port=args.port,
            offline=args.offline,
        )
    except RunError as exc:
        print(f"tempestweb run: {exc}", file=sys.stderr)
        return 1
    print(f"Built {plan.build.mode} artifact at {plan.build.out_dir}")

    print(f"Serving at {plan.url} (Ctrl-C to stop)")
    try:
        serve_run(plan)
    except RunError as exc:
        print(f"tempestweb run: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        print("\nStopped.")
    return 0


def _cmd_sync(args: argparse.Namespace) -> int:
    """Handle ``tempestweb sync``.

    Fills ``[wasm].modules`` with the project's installed pure-Python
    dependencies (excluding the framework and ``[wasm].packages``), preserving
    existing entries. With ``--dry-run`` it reports without writing.

    Args:
        args: Parsed arguments for the ``sync`` subcommand.

    Returns:
        Process exit code.
    """
    try:
        result = sync_modules(args.path, dry_run=args.dry_run)
    except SyncError as exc:
        print(f"tempestweb sync: {exc}", file=sys.stderr)
        return 1
    if not result.added:
        print("[wasm].modules already up to date.")
        return 0
    verb = "Would add" if args.dry_run else "Added"
    print(f"{verb} {len(result.added)} module(s) to [wasm].modules:")
    for module in result.added:
        print(f"  + {module}")
    if not args.dry_run:
        print(f"\nWrote {result.config_path}")
    return 0


def _cmd_vapid(args: argparse.Namespace) -> int:
    """Handle ``tempestweb vapid``.

    Generates a fresh VAPID keypair for WebPush. Prints a human-readable pair by
    default, or ``--env`` lines ready to export as secrets.

    Args:
        args: Parsed arguments for the ``vapid`` subcommand.

    Returns:
        Process exit code.
    """
    from tempestweb.server.webpush import generate_vapid_keys

    try:
        keys = generate_vapid_keys()
    except RuntimeError as exc:
        print(f"tempestweb vapid: {exc}", file=sys.stderr)
        return 1
    if args.env:
        print(f"VAPID_PUBLIC_KEY={keys.public_key}")
        print(f"VAPID_PRIVATE_KEY={keys.private_key}")
    else:
        print(f"public_key:  {keys.public_key}")
        print(f"private_key: {keys.private_key}")
        print(
            "\nKeep the private key secret (export as VAPID_PRIVATE_KEY); "
            "share the public key with the browser client."
        )
    return 0


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

    handlers = {
        "new": _cmd_new,
        "dev": _cmd_dev,
        "build": _cmd_build,
        "run": _cmd_run,
        "sync": _cmd_sync,
        "vapid": _cmd_vapid,
    }
    handler = handlers[args.command]
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
