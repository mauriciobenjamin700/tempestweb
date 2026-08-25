"""Guard: the number the Mode C guide quotes is the matrix's real size.

``docs/advanced/transpile.md`` tells the reader how many cases pin the component
port, and that number is the whole argument for trusting it. It is also prose:
nothing related it to the fixture, so when tempestweb#106 added a dark twin per
case the matrix went from 185 to 336 and the guide kept saying 185 — understating
its own coverage by nearly half, in both languages.

The count moves whenever a component is added or an axis is introduced, which is
exactly when nobody thinks to grep the docs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "transpile_component_samples.json"
PAGES = (
    REPO_ROOT / "docs" / "advanced" / "transpile.md",
    REPO_ROOT / "docs" / "advanced" / "transpile.en.md",
)

#: The sentence the guide states the matrix size in, in either language.
_COUNT_RE = re.compile(r"\*\*(\d+) (?:casos|cases)\*\*")


def _matrix_size() -> int:
    """The number of scenarios the committed component matrix holds.

    Returns:
        The case count, twins included.
    """
    return len(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_both_languages_quote_the_matrix_size() -> None:
    """A page that quotes no count at all would pass the check below silently."""
    for page in PAGES:
        assert _COUNT_RE.search(page.read_text(encoding="utf-8")) is not None, (
            f"{page.name} no longer states the matrix size; the guard below has "
            "nothing to compare and the claim has nothing backing it"
        )


def test_the_quoted_count_matches_the_fixture() -> None:
    """Prose and fixture have to agree, or the guide oversells or undersells."""
    expected = _matrix_size()
    for page in PAGES:
        quoted = int(_COUNT_RE.search(page.read_text(encoding="utf-8")).group(1))
        assert quoted == expected, (
            f"{page.name} says {quoted} cases; the matrix holds {expected}. "
            "Regenerate with `python -m tests.conformance._transpile_components` "
            "and update the sentence in both languages."
        )
