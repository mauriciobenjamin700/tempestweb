"""Unit test for the CI PWA gate script (P4).

Runs ``scripts/pwa-gate.mjs`` through Node and asserts it passes (exit 0), so the
gate's deterministic core is itself covered by the Python ``test_pwa*`` gate. The
workflow file is validated for shape too.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_SCRIPT = REPO_ROOT / "scripts" / "pwa-gate.mjs"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pwa.yml"
LHCI = REPO_ROOT / ".lighthouserc.json"


def _node() -> str:
    """Return the Node executable, skipping when unavailable.

    Returns:
        The resolved ``node`` path.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to run the PWA gate script")
    return node


def test_gate_script_exists() -> None:
    """The gate script and CI config exist."""
    assert GATE_SCRIPT.is_file()
    assert WORKFLOW.is_file()
    assert LHCI.is_file()


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


def test_workflow_defines_pwa_jobs() -> None:
    """The PWA workflow declares the unit/lighthouse/push-e2e jobs."""
    text = WORKFLOW.read_text(encoding="utf-8")
    for job in ("unit:", "lighthouse:", "push-e2e:"):
        assert job in text, f"missing job {job}"
    assert "node --check client/sw/sw.js" in text
    assert "test_pwa*.py" in text
