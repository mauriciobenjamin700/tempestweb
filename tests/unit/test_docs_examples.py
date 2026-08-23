"""Guard: every showcase example has a page, in both languages and in the nav.

``examples/`` and ``docs/examples/`` drifted to fifteen apps apart, and the reason
each one was missing differed — some deliberately, some not (tempestweb#124). With
no rule written down there was no way to tell a gap from a decision, and nothing
in the gate complained, because nothing tied an example to a page.

The rule, and the only place it is enforced:

* **A showcase example has a page** — ``<name>.md`` and ``<name>.en.md``, both in
  ``mkdocs.yml``'s ``nav`` — because ``CLAUDE.md`` points a reader at
  ``docs/examples/`` to see a whole app working.
* **A track demo does not.** The ``*_demo`` apps exist to prove one capability
  while a track is being built; they are listed in the gallery as source to read,
  not documented as a tutorial. That is a class, declared here, not a case-by-case
  omission.
* **Two named exceptions**, each with a better home: ``counter`` is the tutorial's
  own app (``docs/tutorial/``), and ``deploy`` is not an app at all (a Dockerfile,
  a compose file and an nginx config — it belongs to the deploy page).

Adding an example without a page now fails here, which is the part that stops the
drift from coming back.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT: Path = Path(__file__).resolve().parents[2]
EXAMPLES: Path = ROOT / "examples"
PAGES: Path = ROOT / "docs" / "examples"
MKDOCS: Path = ROOT / "mkdocs.yml"

#: Examples documented somewhere other than ``docs/examples/``, and where.
NAMED_EXCEPTIONS: dict[str, str] = {
    "counter": "the tutorial walks through it (docs/tutorial/)",
    "deploy": "not an app: Dockerfile + compose + nginx (docs/advanced/deploy.md)",
}

#: Suffix marking a track demo: an app written to prove one capability, listed in
#: the gallery as source rather than documented as a tutorial.
TRACK_DEMO_SUFFIX: str = "_demo"


def _example_names() -> set[str]:
    """Every example directory that holds a runnable app.

    Returns:
        The directory names under ``examples/`` containing an ``app.py``.
    """
    return {path.parent.name for path in EXAMPLES.glob("*/app.py")}


def _showcase_names() -> set[str]:
    """The examples the rule says must have a page.

    Returns:
        Example names minus the track demos and the named exceptions.
    """
    return {
        name
        for name in _example_names()
        if not name.endswith(TRACK_DEMO_SUFFIX) and name not in NAMED_EXCEPTIONS
    }


def test_every_showcase_example_has_a_page_in_both_languages() -> None:
    """A showcase example has ``<name>.md`` and ``<name>.en.md``."""
    missing: list[str] = []
    for name in sorted(_showcase_names()):
        for suffix in (".md", ".en.md"):
            if not (PAGES / f"{name}{suffix}").exists():
                missing.append(f"docs/examples/{name}{suffix}")
    assert not missing, (
        "showcase examples without a page:\n  "
        + "\n  ".join(missing)
        + "\n\nWrite the page, or — if the example is a track demo — name it "
        f"'<something>{TRACK_DEMO_SUFFIX}', or add it to NAMED_EXCEPTIONS with the "
        "page that documents it instead."
    )


def test_every_showcase_page_is_in_the_nav() -> None:
    """A page nobody can navigate to is a page nobody reads."""
    config = MKDOCS.read_text(encoding="utf-8")
    missing = [
        name
        for name in sorted(_showcase_names())
        if f"examples/{name}.md" not in config
    ]
    assert not missing, f"showcase example pages missing from mkdocs.yml nav: {missing}"


def test_the_track_demos_are_listed_in_the_gallery() -> None:
    """Each track demo is findable, even without a page of its own.

    Not documenting a demo is a decision; hiding it is not. The gallery lists them
    as source to read, so the reader who wants the capability finds the app.
    """
    gallery = (PAGES / "index.md").read_text(encoding="utf-8")
    demos = sorted(
        name for name in _example_names() if name.endswith(TRACK_DEMO_SUFFIX)
    )
    unlisted = [name for name in demos if name not in gallery]
    assert not unlisted, (
        f"track demos missing from the gallery (docs/examples/index.md): {unlisted}"
    )


def test_the_english_gallery_lists_them_too() -> None:
    """The rule is bilingual, like every other page in this site."""
    gallery = (PAGES / "index.en.md").read_text(encoding="utf-8")
    demos = sorted(
        name for name in _example_names() if name.endswith(TRACK_DEMO_SUFFIX)
    )
    unlisted = [name for name in demos if name not in gallery]
    assert not unlisted, f"track demos missing from the English gallery: {unlisted}"


def test_no_page_documents_an_example_that_no_longer_exists() -> None:
    """A page whose example was deleted is a broken promise, not history.

    ``server-mode`` and ``webpush-server`` are pages for example *servers* — they
    have no ``app.py`` because they are not view apps — so they are matched against
    the directory listing rather than the app glob.
    """
    directories = {path.name for path in EXAMPLES.iterdir() if path.is_dir()}
    orphans = [
        page.stem
        for page in sorted(PAGES.glob("*.md"))
        if not page.name.endswith(".en.md")
        and page.stem != "index"
        and page.stem not in directories
    ]
    assert not orphans, f"pages whose example is gone: {orphans}"


def test_the_rule_is_written_down_where_agents_read_it() -> None:
    """``CLAUDE.md`` carries the rule, not just this test.

    The test is the enforcement; the repo's own instructions are where a reader
    (or an agent) looks first, and a rule that lives only in a test is a rule
    nobody finds before breaking it.
    """
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert re.search(r"_demo", claude), (
        "CLAUDE.md does not state the examples/docs rule (which examples get a "
        "page, and which are track demos)"
    )
