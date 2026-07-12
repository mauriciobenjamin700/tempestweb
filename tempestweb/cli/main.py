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
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import cast

from tempestweb.cli import quality
from tempestweb.cli.commands import (
    BuildError,
    DeployError,
    DevError,
    NewError,
    RunError,
    SyncError,
    build_artifact,
    create_project,
    prepare_run,
    scaffold_deploy,
    serve_dev,
    serve_run,
    sync_modules,
)
from tempestweb.cli.config import ConfigError, load_config
from tempestweb.cli.quality import DEFAULT_STRICTNESS, Strictness

__all__ = ["main", "build_parser"]


def _package_version() -> str:
    """Return the installed ``tempestweb`` version, or ``"unknown"``.

    Returns:
        The distribution version string, or ``"unknown"`` when the package is
        not installed as a distribution (e.g. running from a source checkout).
    """
    try:
        return version("tempestweb")
    except PackageNotFoundError:  # pragma: no cover - only in odd source layouts
        return "unknown"


_TOP_EPILOG = """\
examples:
  tempestweb new myapp                    scaffold a runnable project
  cd myapp && tempestweb dev              develop with hot-reload (Mode A)
  tempestweb dev --mode server            develop in Mode B (FastAPI + reload)
  tempestweb run --mode server            serve as built, no watcher (prod-like)
  tempestweb build --mode transpile       build a static Mode C bundle
  tempestweb deploy --tls                 scaffold production deploy files

`dev` watches and reloads while you develop; `run` serves the built app as-is.
Every command that builds/serves takes the project DIRECTORY via --path
(default: current directory) — never a positional .py file.
"""


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser.

    Returns:
        The configured parser with the ``new``/``dev``/``build``/``run`` commands.
    """
    parser = argparse.ArgumentParser(
        prog="tempestweb",
        description="Build web apps in typed Python (WASM + server + transpile modes).",
        epilog=_TOP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"tempestweb {_package_version()}",
        help="Show the tempestweb version and exit.",
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

    dev = sub.add_parser(
        "dev",
        help="Run the app locally (build + serve; watch + reload).",
        description="Build and serve the app locally in any mode. The static "
        "modes (wasm, transpile) get browser livereload; server mode (Mode B) "
        "runs the built FastAPI host under uvicorn and restarts on change.",
    )
    dev.add_argument(
        "--mode",
        choices=["wasm", "server", "transpile"],
        default="wasm",
        help="Execution mode to serve: wasm (Mode A), server (Mode B) or "
        "transpile (Mode C). Default: wasm.",
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

    run = sub.add_parser(
        "run",
        help="Serve the app as built — no file watching (production-like).",
        description="Build the app once and serve it, without the dev watcher or "
        "livereload. Use this for a production-like local run (and it is what the "
        "generated deploy Dockerfile runs); use `dev` while developing.",
    )
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

    deploy = sub.add_parser(
        "deploy",
        help="Scaffold production deploy files (nginx + Docker + guide).",
    )
    deploy.add_argument("--path", default=".", help="Project directory (default: cwd).")
    deploy.add_argument(
        "--out",
        default=None,
        help="Output directory for the deploy files (default: <project>/deploy).",
    )
    deploy.add_argument(
        "--server-name",
        default="_",
        help="nginx server_name (your domain; default: _ = any host).",
    )
    deploy.add_argument(
        "--tls",
        action="store_true",
        help="Emit a TLS (443) server block + HTTP->HTTPS redirect.",
    )
    deploy.add_argument(
        "--replicas",
        type=int,
        default=1,
        help="Number of app upstream replicas in nginx (default: 1).",
    )
    deploy.add_argument(
        "--no-sticky",
        dest="sticky",
        action="store_false",
        help="Drop ip_hash (use with a RedisSessionRouter for SSE scale-out).",
    )
    deploy.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing deploy files.",
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

    _add_quality_parsers(sub)

    return parser


def _add_quality_parsers(
    sub: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the quality-gate subcommands (lint/fix/format/type/test/check).

    Each runs a tool (ruff/mypy/pytest) against the project, layering
    tempestweb's typing conventions per the project's ``[quality]`` level. The
    ``--path`` default (cwd) is the target inspected; ``--strictness`` overrides
    the configured level for a single invocation.

    Args:
        sub: The subparsers action to register the commands on.
    """

    def _target(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--path",
            default=".",
            help="File or directory to inspect (default: cwd).",
        )

    def _strictness(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--strictness",
            choices=["lenient", "standard", "strict"],
            default=None,
            help="Override the [quality] typing_strictness level for this run.",
        )

    lint = sub.add_parser("lint", help="Run `ruff check` on the project.")
    _target(lint)
    _strictness(lint)

    fix = sub.add_parser(
        "fix",
        help="Apply every ruff autofix, then format (`ruff check --fix` + format).",
    )
    _target(fix)
    _strictness(fix)
    fix.add_argument(
        "--unsafe",
        action="store_true",
        help="Also apply ruff's unsafe autofixes (review the diff afterwards).",
    )

    fmt = sub.add_parser(
        "format", help="Run `ruff format` on the project (writes files)."
    )
    _target(fmt)

    fmt_check = sub.add_parser(
        "fmt-check", help="Run `ruff format --check` on the project (read-only)."
    )
    _target(fmt_check)

    type_ = sub.add_parser("type", help="Run `mypy` against the project.")
    _target(type_)
    _strictness(type_)

    test = sub.add_parser("test", help="Run `pytest` (optionally filtered by --path).")
    test.add_argument(
        "--path",
        default=None,
        help="Optional pytest path filter (default: the project's testpaths).",
    )

    check = sub.add_parser(
        "check", help="Run the full gate: ruff check + format --check + mypy + pytest."
    )
    _target(check)
    _strictness(check)


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


def _cmd_deploy(args: argparse.Namespace) -> int:
    """Handle ``tempestweb deploy``.

    Scaffolds an nginx config, Dockerfile, docker-compose and a DEPLOY.md guide
    tailored to the project (upstream port, server name, TLS, replicas).

    Args:
        args: Parsed arguments for the ``deploy`` subcommand.

    Returns:
        Process exit code.
    """
    try:
        result = scaffold_deploy(
            args.path,
            out=args.out,
            server_name=args.server_name,
            tls=args.tls,
            replicas=args.replicas,
            sticky=args.sticky,
            force=args.force,
        )
    except DeployError as exc:
        print(f"tempestweb deploy: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote deploy files to {result.out_dir}")
    for rel in result.files:
        print(f"  + {rel}")
    print("\nNext:\n  read DEPLOY.md, then: docker compose up --build")
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


def _resolve_level(args: argparse.Namespace) -> Strictness:
    """Resolve the strictness level for a quality command.

    A ``--strictness`` flag wins; otherwise the level is read from the project's
    ``[quality] typing_strictness`` (resolved from the target directory, or the
    cwd when the target is a file), falling back to the default.

    Args:
        args: The parsed arguments (may carry ``strictness`` and ``path``).

    Returns:
        The resolved strictness level.
    """
    override = getattr(args, "strictness", None)
    if override is not None:
        return cast("Strictness", override)
    target = Path(getattr(args, "path", None) or ".")
    root = target if target.is_dir() else Path.cwd()
    try:
        return load_config(root).typing_strictness
    except ConfigError:
        return DEFAULT_STRICTNESS


def _cmd_lint(args: argparse.Namespace) -> int:
    """Handle ``tempestweb lint`` — ``ruff check`` on the target."""
    return quality.run_ruff_check(args.path, level=_resolve_level(args))


def _cmd_fix(args: argparse.Namespace) -> int:
    """Handle ``tempestweb fix`` — ruff autofix + format on the target."""
    return quality.run_ruff_fix(
        args.path, unsafe=args.unsafe, level=_resolve_level(args)
    )


def _cmd_format(args: argparse.Namespace) -> int:
    """Handle ``tempestweb format`` — ``ruff format`` (writes files)."""
    return quality.run_ruff_format(args.path, check=False)


def _cmd_fmt_check(args: argparse.Namespace) -> int:
    """Handle ``tempestweb fmt-check`` — ``ruff format --check`` (read-only)."""
    return quality.run_ruff_format(args.path, check=True)


def _cmd_type(args: argparse.Namespace) -> int:
    """Handle ``tempestweb type`` — ``mypy`` on the target."""
    return quality.run_mypy(args.path, level=_resolve_level(args))


def _cmd_test(args: argparse.Namespace) -> int:
    """Handle ``tempestweb test`` — ``pytest`` with an optional path filter."""
    return quality.run_pytest(args.path)


def _cmd_check(args: argparse.Namespace) -> int:
    """Handle ``tempestweb check`` — the full quality gate."""
    return quality.run_full_check(args.path, level=_resolve_level(args))


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
        "deploy": _cmd_deploy,
        "vapid": _cmd_vapid,
        "lint": _cmd_lint,
        "fix": _cmd_fix,
        "format": _cmd_format,
        "fmt-check": _cmd_fmt_check,
        "type": _cmd_type,
        "test": _cmd_test,
        "check": _cmd_check,
    }
    handler = handlers[args.command]
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
