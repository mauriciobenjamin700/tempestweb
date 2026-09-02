"""Unit tests for the CI contrast gate (#202).

The gate itself runs in a browser and is exercised by
``tests/client/contrast-gate.test.js``. What is checked here is the wiring around
it: the script exists and parses, the scenes exist for both themes, and the CI job
that runs it is allowed to fail the build — the property the PWA audit spent its
whole life missing, and worth asserting once per gate.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_SCRIPT = REPO_ROOT / "scripts" / "contrast-gate.mjs"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
LIGHT_SCENES = REPO_ROOT / "tests" / "fixtures" / "a11y_scenes.json"
DARK_SCENES = REPO_ROOT / "tests" / "fixtures" / "a11y_scenes_dark.json"


def _node() -> str:
    """Return the Node executable, skipping when unavailable.

    Returns:
        The resolved ``node`` path.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to parse the contrast gate script")
    return node


def _job_block(name: str) -> str:
    """Return the YAML block of one job from the CI workflow.

    Slices by indentation rather than parsing YAML: PyYAML is not a declared
    dependency of the test extras, so importing it would pass locally and fail in
    a job installed without the docs group.

    Args:
        name: The job key, as written in the workflow.

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


def test_gate_script_parses() -> None:
    """scripts/contrast-gate.mjs is loadable JS."""
    result = subprocess.run(
        [_node(), "--check", str(GATE_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_both_themes_have_the_same_scenes() -> None:
    """The dark fixture covers every scene the light one does.

    A theme is audited against scenes built under it, so a scene present in one
    fixture and missing from the other is a screen measured in one palette only.
    """
    light = json.loads(LIGHT_SCENES.read_text(encoding="utf-8"))
    dark = json.loads(DARK_SCENES.read_text(encoding="utf-8"))
    assert sorted(light) == sorted(dark)


def test_dark_scenes_are_not_the_light_ones() -> None:
    """The dark fixture is actually built dark.

    Generating both from the same theme would leave the gate reporting green over
    a palette it never rendered — the failure mode this whole gate exists to end.
    """
    light = LIGHT_SCENES.read_text(encoding="utf-8")
    dark = DARK_SCENES.read_text(encoding="utf-8")
    assert light != dark


def test_contrast_job_is_blocking() -> None:
    """The contrast job can fail the build, and installs what it needs.

    A gate that cannot fail is not a gate; `.github/workflows/pwa.yml` carried one
    for its whole life, wrapped in ``continue-on-error`` and a ``|| echo``.
    """
    block = _job_block("contrast")
    assert "playwright install" in block, "the contrast job installs no browser"
    assert "scripts/contrast-gate.mjs" in block, "the contrast job runs no gate"
    for swallow in ("continue-on-error", "|| echo", "|| true"):
        assert swallow not in block, (
            f"the contrast job swallows failure with {swallow!r}"
        )


def test_scene_fixtures_are_regenerated_in_ci() -> None:
    """Both a11y jobs regenerate the scenes and diff them.

    The scenes are generated from the example apps; a fixture edited by hand — or
    left stale after an example changes — would audit a screen nobody ships.
    """
    for job in ("a11y", "contrast"):
        block = _job_block(job)
        assert "tests.conformance._a11y_scenes" in block, f"{job} does not regenerate"
        assert "git diff --exit-code tests/fixtures/" in block, f"{job} does not diff"
