"""Unit tests for the CI PWA gate (P4).

Runs ``scripts/pwa-gate.mjs`` through Node and asserts it passes (exit 0), so the
gate's deterministic core is itself covered by the Python ``test_pwa*`` gate. The
workflow file is validated for shape too — including that the browser audit is
allowed to fail the build, which is the property the job spent its whole life
missing.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_SCRIPT = REPO_ROOT / "scripts" / "pwa-gate.mjs"
AUDIT_SCRIPT = REPO_ROOT / "scripts" / "pwa-audit.mjs"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pwa.yml"


def _node() -> str:
    """Return the Node executable, skipping when unavailable.

    Returns:
        The resolved ``node`` path.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to run the PWA gate script")
    return node


def _job_block(name: str) -> str:
    """Return the YAML block of one job from the PWA workflow.

    Slices by indentation rather than parsing YAML on purpose: PyYAML is not a
    declared dependency, and the workflow's own ``unit`` job installs without the
    docs group that would drag it in — a test importing it would pass locally and
    fail in CI.

    Args:
        name: The job key, as written in the workflow (e.g. ``"pwa-audit"``).

    Returns:
        The job's block, without the surrounding jobs.

    Raises:
        AssertionError: If the workflow declares no such job.
    """
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(lines) if line == f"  {name}:"), None)
    assert start is not None, f"the workflow declares no job {name!r}"
    block: list[str] = []
    for line in lines[start + 1 :]:
        starts_next_job = (
            line.startswith("  ")
            and not line.startswith("   ")
            and line.rstrip().endswith(":")
        )
        if starts_next_job:
            break
        block.append(line)
    return "\n".join(block)


def test_gate_scripts_exist() -> None:
    """The gate scripts and the workflow exist."""
    assert GATE_SCRIPT.is_file()
    assert AUDIT_SCRIPT.is_file()
    assert WORKFLOW.is_file()


def test_gate_script_passes() -> None:
    """scripts/pwa-gate.mjs exits 0 (manifest installable, push contract intact)."""
    result = subprocess.run(
        [_node(), str(GATE_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "PWA gate OK" in result.stdout


def test_gate_push_smoke_passes() -> None:
    """The --push-smoke placeholder also exits 0."""
    result = subprocess.run(
        [_node(), str(GATE_SCRIPT), "--push-smoke"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "push-smoke" in result.stdout


def test_audit_script_parses() -> None:
    """scripts/pwa-audit.mjs is loadable JS.

    ``node --check`` parses without resolving imports, so this says the file is
    syntactically whole — the audit's real proof is the job running it.
    """
    result = subprocess.run(
        [_node(), "--check", str(AUDIT_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_audit_script_needs_a_target() -> None:
    """Invoked without a base URL, the audit refuses instead of auditing nothing."""
    result = subprocess.run(
        [_node(), str(AUDIT_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode != 0
    assert "usage:" in result.stderr


def test_workflow_defines_pwa_jobs() -> None:
    """The PWA workflow declares the unit/pwa-audit/push-e2e jobs."""
    text = WORKFLOW.read_text(encoding="utf-8")
    for job in ("unit:", "pwa-audit:", "push-e2e:"):
        assert job in text, f"missing job {job}"
    assert "node --check client/sw/sw.js" in text
    assert "node --check client/sw/sw-teardown.js" in text
    assert "test_pwa*.py" in text


def test_pwa_audit_job_builds_a_real_artifact() -> None:
    """The audit job builds an artifact and points the browser at it.

    The job it replaced asserted against a ``staticDistDir`` no step ever built,
    so the audit tool failed before opening a browser — every run, invisibly.
    """
    block = _job_block("pwa-audit")
    assert "tempestweb build" in block, "the audit job builds no artifact"
    assert "scripts/pwa-audit.mjs" in block, "the audit job runs no audit"
    assert "playwright install" in block, "the audit job installs no browser"


def test_pwa_audit_job_can_fail_the_build() -> None:
    """The audit job is blocking — no ``continue-on-error``, no swallowed failure.

    This is the regression guard for the defect the job shipped with: it carried
    ``continue-on-error: true`` *and* ``|| echo "lighthouse soft-fail"``, so it
    reported success no matter what it found. A gate that cannot fail is not a
    gate, and nothing in CI could say so.
    """
    block = _job_block("pwa-audit")
    assert "continue-on-error" not in block, "the audit job cannot fail the build"
    for swallow in ("|| echo", "|| true", "continue-on-error"):
        assert swallow not in block, f"the audit job swallows failure with {swallow!r}"
