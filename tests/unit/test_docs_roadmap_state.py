"""Guard on the one paragraph of `docs/roadmap.md` that claims to be *now*.

`docs/roadmap.md` is in `mkdocs.yml`'s `exclude_docs`, so no build renders it and
`--strict` never sees it. It is still the page an agent or a maintainer opens to
answer "where are we?" — and its opening `!!! info "Estado atual"` block is the
only part written in the present tense. Everything below it is a table of phases,
each row carrying its own status, and those rows were kept in step. The block was
not.

The rot, found by hand on 2026-08-27:

* The block was stamped `atualizado em 2026-07-11` and said "Última versão
  publicada no PyPI: **tempestweb 0.49.0**", with "o **Trilho T** … chega na
  **0.50.0**". `pyproject.toml` said **0.124.0** and PyPI served **0.121.0** —
  75 releases of drift, in the sentence a reader trusts most.
* Its gate scoreboard read "pytest 831 pass/1 skip · jsdom 439 pass". The real
  numbers were 2013/14 and 894/0 — and 2013 became 2017 the moment this file was
  added, which is the whole argument for not guarding that line.
* It listed "a **verificação ao vivo device-dependente** dos itens 🔶" as an open
  high-level pendency while `docs/agents/device-verification.md` had already
  reached 8/8 ✅ — the block was describing work that was finished, and finished
  by measurements that found four real defects.

The sibling guard `test_docs_readme.py` exists because `README.md` and
`docs/index.md` rotted the same way; this is the same idea pointed at the third
unbuilt page.

**What this guard does not cover, on purpose.** The gate scoreboard (files
linted, files typed, tests passed) is *not* checked against the real suite. Those
numbers move on every PR that adds a test, so a guard on them would fail on work
that has nothing to do with docs, and the cheapest way to make it pass would be
to retype a number nobody measured — training exactly the reflex this file exists
to prevent. A guard that cries without a reason is worse than no guard. The block
carries the command that reproduces its numbers instead (`make check` plus
`mkdocs build --strict`), which is the practice `test_docs_design_status.py`
recommends for any count copied into prose: write the answer next to the question.

Likewise, the block naming a phase that has *since* turned ✅ is not caught here.
Only the forward direction is mechanical — a phase that is not done must be named
at the top — and pretending otherwise would mean failing this test every time
someone finishes P2.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs"

#: The roadmap in every language it exists in. Today PT-BR only: `roadmap.md` is
#: an excluded design doc rendered from the GitHub blob, not a site page, so it
#: has no `.en.md` twin — the site's bilingual door to it is `design-docs.md` /
#: `design-docs.en.md`. Listed anyway so an EN mirror is guarded the day it lands.
ROADMAPS: tuple[Path, ...] = (DOCS / "roadmap.md", DOCS / "roadmap.en.md")

#: The heading of the block that speaks in the present tense.
STATE_HEADING = re.compile(r'^!!! \w+ "Estado atual[^"]*"$')

#: A phase row of a track table: `| P2 | scope… | 🔶 (why) |`. The id cell is
#: short and uppercase-ish (`W0`, `S11`, `T-EV`, `0.0`, `C`); a row whose first
#: cell is `Fase`/`ID` is the header and a row of dashes is the separator.
PHASE_ID = re.compile(r"^[0-9A-Z][0-9A-Z.\-]{0,5}$")

#: Status markers, in the meaning the roadmap's own legend gives them.
DONE = "✅"
PENDING_VERIFICATION = "🔶"
NOT_STARTED = "⬜"


def _state_block(page: Path) -> str:
    """The text of the `Estado atual` admonition, heading excluded.

    An admonition body is the run of indented (or blank) lines that follows the
    heading, so the block ends at the first line that starts in column zero.

    Args:
        page (Path): The roadmap page to read.

    Returns:
        The block's body, or an empty string when the page has no such block.
    """
    lines = page.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if STATE_HEADING.match(line) is None:
            continue
        body: list[str] = []
        for following in lines[index + 1 :]:
            if following.strip() and not following.startswith("    "):
                break
            body.append(following)
        return "\n".join(body)
    return ""


def _unfinished_phases(page: Path) -> dict[str, str]:
    """The phases whose track-table row is not ✅.

    Args:
        page (Path): The roadmap page to read.

    Returns:
        Phase id mapped to the marker its status cell carries, for every row
        marked 🔶 or ⬜.
    """
    unfinished: dict[str, str] = {}
    for line in page.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2 or PHASE_ID.match(cells[0]) is None:
            continue
        status = cells[-1]
        if DONE in status:
            continue
        for marker in (PENDING_VERIFICATION, NOT_STARTED):
            if marker in status:
                unfinished[cells[0]] = marker
    return unfinished


def _existing() -> list[Path]:
    """The roadmap pages that are actually on disk.

    Returns:
        Every path in `ROADMAPS` that exists.
    """
    return [page for page in ROADMAPS if page.is_file()]


def test_the_roadmap_has_a_state_block_at_all() -> None:
    """Everything else here reads that block; an empty read must not pass quietly.

    This is the check that keeps the other two honest if someone renames the
    admonition or drops it — without it, deleting the block would make the whole
    file green.
    """
    missing = [page.name for page in _existing() if not _state_block(page).strip()]

    assert not missing, (
        "roadmap page without an `Estado atual` admonition:\n  "
        + "\n  ".join(missing)
        + "\n(it is the only part of the page written in the present tense — "
        "restore it, or point this guard at whatever replaced it)"
    )


def test_the_state_block_names_the_version_the_repo_ships() -> None:
    """The block said 0.49.0 while `pyproject.toml` said 0.124.0, for 75 releases.

    Naming the current version is the cheapest possible proof that somebody looked
    at the block while shipping. It is also the exact claim that rotted.
    """
    with (REPO_ROOT / "pyproject.toml").open("rb") as manifest:
        version: str = tomllib.load(manifest)["project"]["version"]

    stale = [page.name for page in _existing() if version not in _state_block(page)]

    assert not stale, (
        f"the `Estado atual` block does not mention the shipped version {version}:"
        "\n  " + "\n  ".join(stale) + "\n(update the block: say which version the "
        "repo is at, which one PyPI serves, and what the difference contains)"
    )


def test_the_state_block_still_separates_repo_version_from_pypi() -> None:
    """One number for two facts is how "0.49.0" survived being wrong twice over.

    The repo version and the published version are different facts and drift
    apart by design — the old block had a single "Última versão publicada no PyPI"
    line doing both jobs, so a reader could not tell whether an unreleased fix was
    installable. The block must keep both.
    """
    silent = [page.name for page in _existing() if "PyPI" not in _state_block(page)]

    assert not silent, (
        "the `Estado atual` block never mentions PyPI:\n  "
        + "\n  ".join(silent)
        + "\n(a reader needs both facts: the version in `pyproject.toml` and the "
        "one `pip install tempestweb` actually gets)"
    )


def test_every_unfinished_phase_is_named_in_the_state_block() -> None:
    """A phase that is not done belongs in the summary, not only in its own row.

    The tables were maintained while the block was not, so the block claimed the
    device-dependent verification was still pending when the scoreboard read 8/8.
    The mechanical half of keeping it honest: whatever the tables still mark 🔶 or
    ⬜ has to be named up top, where the reader looking for "what is left" reads.
    """
    problems: list[str] = []
    for page in _existing():
        block = _state_block(page)
        for phase, marker in sorted(_unfinished_phases(page).items()):
            if not re.search(rf"\b{re.escape(phase)}\b", block):
                problems.append(f"{page.name}: {phase} is {marker} and unnamed")

    assert not problems, (
        "a phase the tables mark as unfinished is missing from the `Estado atual` "
        "block:\n  "
        + "\n  ".join(problems)
        + "\n(name it in the block with what is actually blocking it, or fix the "
        "row if the phase is done)"
    )
