"""Guards on the *writing*, not the shape: recap, parity, anchors, admonitions.

The other docs guards check that the site holds together — links resolve, every
subpackage has a reference page, snippets name real APIs. None of them checks
that a page still **teaches** the way `~/.claude/rules/docs-standard.md` asks:
end with a recap, keep both languages structurally in step, use admonitions the
theme actually renders, and never point a reader at a heading that is not there.

Each check here replaced a manual sweep. A sweep finds today's defect; a guard
finds every future one — and an audit run by hand is also an audit that can be
wrong, which is exactly what happened while writing these:

* A first pass reported 52 broken anchors. All 52 were an artefact of comparing
  resolved and unresolved paths — the real count was zero.
* A first pass reported three guide pages with no recap. All three had one, as an
  ``!!! check`` admonition or an ``h3``, which the pattern did not match.

So these deliberately accept every shape the docs actually use, and each one was
verified to still fail against a deliberately broken page.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs"
SITE = REPO_ROOT / "site"

#: The folders whose pages teach something and therefore owe the reader a recap.
GUIDE_DIRS = ("tutorial", "advanced")

#: A recap, in either shape the docs use: an ``h2``/``h3`` heading, or a closing
#: admonition whose title says it recaps.
RECAP = re.compile(
    r'^\s*(?:#{2,3}\s+|!!!\s+\w+\s+")(recap|resumo|recapitulando|recapping)',
    re.I | re.M,
)

#: A landing page introduces the pages that follow rather than concluding
#: anything, so it closes with a pointer instead of a recap.
RECAP_EXEMPT = frozenset({"index.md", "index.en.md"})

#: Any heading, for comparing the two languages structurally.
HEADING = re.compile(r"^(#{2,3})\s+\S", re.M)

#: The admonition types the Material theme renders. Anything else silently
#: degrades to a plain paragraph with the type name showing.
ADMONITION_TYPES = frozenset(
    {
        "note",
        "abstract",
        "summary",
        "tldr",
        "info",
        "todo",
        "tip",
        "hint",
        "important",
        "success",
        "check",
        "done",
        "question",
        "help",
        "faq",
        "warning",
        "caution",
        "attention",
        "failure",
        "fail",
        "missing",
        "danger",
        "error",
        "bug",
        "example",
        "snippet",
        "quote",
        "cite",
    }
)

#: An admonition or collapsible block opener.
ADMONITION = re.compile(r"^\s*(?:!!!|\?\?\?\+?)\s+([a-z-]+)", re.M)

#: An ``id="…"`` in built HTML — every heading gets one.
HTML_ID = re.compile(r'\sid="([^"]+)"')

#: A link carrying a fragment, in built HTML.
HTML_ANCHOR_LINK = re.compile(r'href="([^"]+#[^"]+)"')


def _guide_pages(suffix: str = ".md") -> list[Path]:
    """The teaching pages of one language.

    Args:
        suffix: ``".md"`` for Portuguese, ``".en.md"`` for English.

    Returns:
        Every page under the guide folders with that suffix, sorted.
    """
    pages: list[Path] = []
    for folder in GUIDE_DIRS:
        for page in (DOCS / folder).glob("*.md"):
            is_en = page.name.endswith(".en.md")
            if (suffix == ".en.md") == is_en:
                pages.append(page)
    return sorted(pages)


@pytest.mark.parametrize("suffix", [".md", ".en.md"])
def test_every_guide_page_ends_with_a_recap(suffix: str) -> None:
    """ "Ensine fazendo, depois recapitule" — a page that just stops is unfinished.

    Both shapes count: a ``## Recap`` heading, or a closing ``!!! check`` whose
    title recaps. A reader who skimmed gets the summary either way.
    """
    missing = [
        page.relative_to(DOCS).as_posix()
        for page in _guide_pages(suffix)
        if page.name not in RECAP_EXEMPT and not RECAP.search(page.read_text("utf-8"))
    ]

    assert not missing, (
        "guide pages with no recap:\n  "
        + "\n  ".join(missing)
        + "\n(close with '## Recap', or an admonition titled Recap/Recapitulando)"
    )


def test_the_two_languages_stay_structurally_in_step() -> None:
    """A translation that lost a section is a reader who never learns it.

    Comparing headings rather than words: the prose differs by design, the
    skeleton must not. A page gaining a section in one language only is the
    common way a translation rots.
    """
    drift: list[str] = []
    for page in DOCS.rglob("*.md"):
        if "agents" in page.parts or page.name.endswith(".en.md"):
            continue
        english = page.with_name(page.stem + ".en.md")
        if not english.exists():
            continue
        here = len(HEADING.findall(page.read_text("utf-8")))
        there = len(HEADING.findall(english.read_text("utf-8")))
        if here != there:
            drift.append(f"{page.relative_to(DOCS).as_posix()}: PT={here} EN={there}")

    assert not drift, (
        "pages whose two languages have drifted apart structurally:\n  "
        + "\n  ".join(drift)
    )


def test_every_admonition_is_a_type_the_theme_renders() -> None:
    """An unknown type does not fail the build — it renders the word as text.

    ``!!! warn`` (rather than ``warning``) produces a box titled "Warn" with no
    icon and no colour, which reads as a typo to everyone who sees it and to
    nobody who builds it.
    """
    unknown: list[str] = []
    for page in sorted(DOCS.rglob("*.md")):
        if "agents" in page.parts:
            continue
        for kind in ADMONITION.findall(page.read_text("utf-8")):
            if kind not in ADMONITION_TYPES:
                unknown.append(f"{page.relative_to(DOCS).as_posix()}: '{kind}'")

    assert not unknown, (
        "admonitions the Material theme will not render:\n  " + "\n  ".join(unknown)
    )


@pytest.mark.skipif(
    not (SITE / "index.html").exists(),
    reason="needs a built site — run `mkdocs build` first (CI does)",
)
def test_no_cross_page_link_points_at_a_missing_heading() -> None:
    """The blind spot the project's own notes name: MkDocs logs it as INFO only.

    ``--strict`` fails on a broken *page* link and stays quiet about a broken
    *anchor*, so a link to ``../deploy/#scale-out`` survives the heading being
    renamed and quietly drops the reader at the top of the page instead of the
    section they were promised.

    Resolving every path before comparing matters: an earlier version of this
    check compared resolved targets against unresolved keys and reported 52
    false positives.
    """
    anchors = {
        html.resolve(): set(HTML_ID.findall(html.read_text("utf-8", errors="ignore")))
        for html in SITE.rglob("*.html")
    }

    broken: list[str] = []
    for html in sorted(anchors):
        for href in HTML_ANCHOR_LINK.findall(html.read_text("utf-8", errors="ignore")):
            if href.startswith(("http://", "https://", "mailto:")):
                continue
            path, _, fragment = href.partition("#")
            fragment = unquote(fragment)
            if not fragment:
                continue
            target = html if not path else (html.parent / path)
            if not str(target).endswith(".html"):
                target = Path(str(target).rstrip("/")) / "index.html"
            target = target.resolve()
            if target in anchors and fragment not in anchors[target]:
                broken.append(f"{html.relative_to(SITE).as_posix()} -> {href}")

    assert not broken, (
        "links pointing at a heading the target page does not have:\n  "
        + "\n  ".join(sorted(set(broken)))
    )
