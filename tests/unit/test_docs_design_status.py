"""Guard: a design doc may not carry a count of our own code that ages alone.

The design docs under ``docs/`` that ``mkdocs.yml`` excludes from the site are
read by agents and maintainers, not users — and nothing builds them, so no gate
sees them. That is how ``docs/modo-c-transpile.md`` came to say "🚧 Button feito"
long after every styled widget was tabled, and "os ~64 widgets" after the count
moved (tempestweb#123). A stale status there is expensive in a specific way: an
agent reads it and either reimplements what exists or refuses work that is
already possible.

Prose cannot be type-checked, but the *shape* that goes stale can: a hard-coded
count of our own widgets, components, fixture cases or generated-artifact bytes.
Each of those has a source of truth in the repo — ``buildable_widgets()``, the
fixture itself, the file on disk — so the doc should point at it instead of
copying the number. This test fails when one is copied.

**What it does not cover, so nobody reads more into it than it says:** the other
half of the #123 drift was a *status marker* — "🚧 Button feito" while every
styled widget was already tabled. A marker is a claim about our code the same way
a count is, but it has no shape to match on: "🚧" next to a sentence is not
distinguishable, by regex, from "🚧" that is still true. Keeping a marker honest
is a review duty, not a gate, and the way to make it cheap is to write the marker
next to the thing that answers it (the generator, the fixture, the test) so the
next reader can check in one command instead of trusting the prose.
"""

from __future__ import annotations

import re
from pathlib import Path

DOCS: Path = Path(__file__).resolve().parents[2] / "docs"

#: The design pages excluded from the site build, hence unguarded by `--strict`.
DESIGN_PAGES: tuple[str, ...] = (
    "modo-c-transpile.md",
    "plan.md",
    "native-modo-c.md",
    "roadmap.md",
    "contract.md",
    "arquitetura.md",
)

#: Counts of *our* code that move on their own. Each pattern names a thing the
#: repo can answer exactly, so the prose has no business remembering the number.
VOLATILE_CLAIMS: tuple[tuple[str, str], ...] = (
    (r"~?\d+\s+widgets\b", "widget count — derive from buildable_widgets()"),
    (r"~?\d+\s+(componentes|components)\b", "component count — derive from the port"),
    (r"\d+\s+(casos|cases)\b", "fixture case count — the fixture is the count"),
    (r"\d+\s?KB\b", "generated-artifact size — measure it, do not remember it"),
    (r"\d+ de \d+ exemplos\b", "corpus tally — the gate reports it"),
)

#: Lines that carry a number about something outside this repo (the size of the
#: Pyodide runtime) or a fact of history (what the original spike contained).
#: Neither ages with our code, so neither is a violation.
ALLOWED_LINES: frozenset[str] = frozenset(
    {
        "| Runtime Python | browser (~6 MB Pyodide) | servidor vivo | **nenhum** |",
        "| Cold start | Pesado (~6–10 MB WASM) | Leve (HTML + cliente JS) |",
        "**No spike:** counter ponta-a-ponta (state + view + 2 handlers), 4 widgets",
    }
)


def test_no_design_doc_hardcodes_a_count_of_our_own_code() -> None:
    """No excluded design page copies a count the repo can answer itself."""
    offenders: list[str] = []
    for name in DESIGN_PAGES:
        page = DOCS / name
        if not page.exists():
            continue
        for number, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip() in ALLOWED_LINES:
                continue
            for pattern, why in VOLATILE_CLAIMS:
                match = re.search(pattern, line, re.IGNORECASE)
                if match is not None:
                    offenders.append(f"{name}:{number}: {match.group(0)!r} — {why}")
    assert not offenders, (
        "a design doc hard-codes a count of our own code, which goes stale "
        "silently (nothing builds these pages):\n  " + "\n  ".join(offenders)
    )


def test_the_guarded_pages_are_the_excluded_ones() -> None:
    """The guarded list matches what ``mkdocs.yml`` excludes from the site.

    A page moved into ``exclude_docs`` stops being built, so it stops being
    checked by anything — this test is what keeps the two lists in step, instead
    of a new design page quietly landing outside every gate.
    """
    config = (DOCS.parent / "mkdocs.yml").read_text(encoding="utf-8")
    block = config[config.index("exclude_docs:") :]
    block = block[: block.index("\n\n")]
    excluded = {
        line.strip()
        for line in block.splitlines()[1:]
        if line.strip() and line.strip().endswith(".md")
    }
    assert excluded == set(DESIGN_PAGES), (
        "mkdocs.yml excludes a different set of design pages than this guard "
        f"covers: excluded={sorted(excluded)}, guarded={sorted(DESIGN_PAGES)}"
    )
