"""Guard: every navigation label reaches the Portuguese reader in Portuguese.

The site's default locale is PT-BR, but the ``nav:`` keys in ``mkdocs.yml`` are
written in English and translated by ``mkdocs-static-i18n`` through
``nav_translations``. A label with no entry there falls through untranslated —
it simply renders in English in the Portuguese sidebar, with no warning from
``mkdocs build --strict``.

That is how "Generate a client from OpenAPI" sat in English in the PT nav: the
page was added, the translation was not, and nothing in the build noticed.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MKDOCS_YML = REPO_ROOT / "mkdocs.yml"

#: Labels that are identifiers, not prose — a module path reads the same in
#: both languages and translating it would be wrong. Anything else that lands
#: here is a missing translation, not an exemption.
IDENTIFIER_RE = re.compile(r"^tempestweb\.[a-z_]+$")


def _nav_labels() -> set[str]:
    """Every label in the ``nav:`` block that points at a page.

    Returns:
        The labels, with surrounding quotes stripped.
    """
    text = MKDOCS_YML.read_text(encoding="utf-8")
    nav = text[text.index("\nnav:") :]
    labels = {
        match.group(2)
        for line in nav.splitlines()
        if (match := re.match(r'\s+- ("?)(.+?)\1: [\w./-]+\.md$', line))
    }
    assert labels, "no nav labels parsed — the mkdocs.yml format changed"
    return labels


def _translated_labels() -> set[str]:
    """The label keys declared under ``nav_translations:``.

    Returns:
        The source-language keys that have a Portuguese rendering.
    """
    text = MKDOCS_YML.read_text(encoding="utf-8")
    block = text[text.index("nav_translations:") : text.index("\nnav:")]
    return set(re.findall(r'^\s+"?(.+?)"?:\s', block, re.M))


def test_every_nav_label_is_translated() -> None:
    """An untranslated label shows up in English in the default locale's sidebar.

    Section titles count too: they are nav labels like any other, and a section
    heading in the wrong language is more visible than a leaf page.
    """
    untranslated = sorted(
        label
        for label in _nav_labels() - _translated_labels()
        if re.search(r"[A-Za-z]", label) and not IDENTIFIER_RE.match(label)
    )
    assert not untranslated, (
        "nav labels with no nav_translations entry (they render in English on "
        "the PT site):\n  " + "\n  ".join(untranslated)
    )
