"""Guards on the two pages nobody builds: `README.md` and the docs landing page.

Every other docs guard checks the site — links resolve, snippets name real APIs,
every subpackage has a reference page. None of them looks at the **top**: the
README that PyPI renders, and the landing grid that is the first thing a reader
sees. Those two are prose nothing compiles, so they rot in silence.

They rotted twice, and both were found by hand rather than by a test:

* Five of the nine ``tempestweb/…`` paths the README's Layout table named did not
  exist — a docs move rewrote the paths inside the code spans, and the table went
  on telling readers to look in ``tempestweb/tutorial/components/``.
* Seven public surfaces shipped in 0.114.0 → 0.120.0 (``export``, ``access``,
  ``query``, ``tabular``, plus the ``imaging`` and ``device`` capability families)
  reached neither page, and the landing grid still counted 14 subpackages when
  there were 18.

So: a path the README names must exist, a subpackage must be reachable from both
pages, and neither page may carry a hand-counted number of our own code — the
same rule ``test_docs_design_status.py`` already applies to the design docs, now
pointed at the pages where being wrong costs the most.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "README.md"
PACKAGE = REPO_ROOT / "tempestweb"
LANDING = [REPO_ROOT / "docs" / "index.md", REPO_ROOT / "docs" / "index.en.md"]

#: A ``tempestweb/…`` path written inside a code span.
PACKAGE_PATH = re.compile(r"`(tempestweb/[a-z_][a-z_/]*)`")

#: A number followed by a word naming something we ship. These age the moment
#: the thing is added, and nothing rebuilds the sentence that carries them.
#:
#: The fuzzy forms count too, and all three had already shipped stale here: a
#: modifier between the number and the noun (``46 single-concept demos`` when the
#: gallery held 60), a tilde (``all ~64 widgets`` when ``buildable_widgets()``
#: returned 75) and an open-ended suffix (``the 40-plus examples``). A hedge is
#: still a number a reader takes literally, and none of them self-update.
#:
#: ``Material 3`` is excluded by the lookbehind: the 3 there belongs to the
#: design system's name, not to a count of anything in this repo.
COUNTED = re.compile(
    r"(?<!Material )\b~?(\d+)(?:-plus)?\s*\n?\s*(?:[\w-]+\s+){0,2}"
    r"(subpacotes|subpackages|apps rodáveis"
    r"|runnable apps|capacidades nativas|native capabilities|componentes"
    r"|components|widgets|demos|exemplos|examples)\b",
    re.I,
)

#: Subpackages that are deliberately absent from the top-level prose: they are
#: plumbing a reader never imports directly.
INTERNAL = frozenset({"core", "runtime", "devserver"})


def _subpackages() -> set[str]:
    """The importable subpackages of ``tempestweb``.

    Returns:
        Directory names holding an ``__init__.py``, excluding caches.
    """
    return {
        child.name
        for child in PACKAGE.iterdir()
        if child.is_dir()
        and (child / "__init__.py").is_file()
        and not child.name.startswith("__")
    }


def test_every_path_the_readme_names_exists() -> None:
    """A path in the README is navigation advice, and wrong advice is worse than none.

    This is the check that would have caught the Layout table sending readers to
    ``tempestweb/tutorial/components/``, a directory that never existed.
    """
    named = sorted(set(PACKAGE_PATH.findall(README.read_text(encoding="utf-8"))))
    missing = [path for path in named if not (REPO_ROOT / path).is_dir()]

    assert not missing, "README.md names paths that do not exist:\n  " + "\n  ".join(
        missing
    )


def test_every_public_subpackage_is_reachable_from_the_readme() -> None:
    """The README is what PyPI renders — a surface absent from it is undiscoverable.

    Someone who ran ``pip install tempestweb`` has no other index. A package that
    ships and is never mentioned here is a package nobody finds.
    """
    text = README.read_text(encoding="utf-8")
    missing = sorted(
        name
        for name in _subpackages() - INTERNAL
        if f"tempestweb/{name}" not in text and f"tempestweb.{name}" not in text
    )

    assert not missing, (
        "public subpackages the README never mentions:\n  "
        + "\n  ".join(missing)
        + "\n(add them to the Layout table, or to INTERNAL if a reader never "
        "imports them directly)"
    )


def test_every_public_subpackage_is_reachable_from_the_landing_page() -> None:
    """The landing grid is the site's index; both languages, or one reader is lost."""
    problems: list[str] = []
    for page in LANDING:
        text = page.read_text(encoding="utf-8")
        for name in sorted(_subpackages() - INTERNAL):
            linked = any(
                f"{section}/{name}" in text
                for section in ("reference", "advanced", "tutorial")
            )
            if not linked:
                problems.append(f"{page.name}: {name}")

    assert not problems, (
        "subpackages missing from the landing page's discovery grid:\n  "
        + "\n  ".join(problems)
    )


def test_neither_top_page_hand_counts_our_own_code() -> None:
    """A counted number ages the day the thing is added, and nothing rebuilds it.

    ``docs/index.md`` claimed 14 subpackages when there were 18, and 46 runnable
    examples when there were 48. Both were true once. Say "every" or link the
    list instead of counting it.
    """
    offenders: list[str] = []
    for page in [README, *LANDING]:
        for count, noun in COUNTED.findall(page.read_text(encoding="utf-8")):
            offenders.append(f"{page.name}: '{count} {noun}'")

    assert not offenders, (
        "a top-level page hand-counts our own code, which goes stale silently:\n  "
        + "\n  ".join(offenders)
        + "\n(drop the number — 'every subpackage', 'the gallery' — or link the list)"
    )
