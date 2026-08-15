"""Guard: every relative link in the docs resolves to a page the site builds.

``mkdocs build --strict`` does **not** catch this. A link pointing at a page
listed in ``exclude_docs`` is reported at ``INFO`` level, and ``--strict`` only
promotes ``WARNING`` and above — so the docs workflow stays green while the
published site serves a 404. That is exactly how six such links reached
production (``security.md`` and ``stability.md`` linking ``roadmap.md`` and
``contract.md`` relatively instead of through their GitHub blob URLs).

This module closes the hole from the ``pytest`` side, where it fails loudly:
it collects every relative markdown link on every page that actually gets
built, and asserts the target exists and is itself built.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs"
MKDOCS_YML = REPO_ROOT / "mkdocs.yml"

#: A markdown inline link whose target is a relative ``.md`` path, with an
#: optional ``#anchor``. Absolute URLs, in-page anchors and ``mailto:`` are
#: excluded by requiring the target to end in ``.md`` before the anchor.
_LINK_RE = re.compile(r"\]\((?!https?://|#|mailto:)([^)#\s]+\.md)(#[^)\s]*)?\)")

#: A fenced code block, so links quoted inside a sample are not mistaken for
#: real links. Matches ``` and ~~~ fences with any info string.
_FENCE_RE = re.compile(r"^(?P<f>```+|~~~+).*?^(?P=f)\s*$", re.M | re.S)


def _excluded_patterns() -> list[str]:
    """Read the ``exclude_docs`` block scalar out of ``mkdocs.yml``.

    Hand-parsed rather than loaded with a YAML library: the test env is not
    guaranteed to carry one (it arrives only as a transitive dependency of the
    ``docs`` extra), and the block is a flat literal scalar of one path per
    line. The parse asserts a non-empty result, so restructuring ``mkdocs.yml``
    fails the test instead of silently disabling the guard.

    Returns:
        The raw patterns, e.g. ``["plan.md", "roadmap.md", "agents/"]``.
    """
    lines = MKDOCS_YML.read_text(encoding="utf-8").splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.startswith("exclude_docs:")),
        None,
    )
    assert start is not None, "mkdocs.yml no longer declares exclude_docs"
    patterns: list[str] = []
    for line in lines[start + 1 :]:
        if not line.strip():
            break
        if not line.startswith((" ", "\t")):
            break
        patterns.append(line.strip())
    assert patterns, "the exclude_docs block parsed empty — the format changed"
    return patterns


def _is_excluded(relative: str, patterns: list[str]) -> bool:
    """Whether a docs-relative path is kept out of the built site.

    Args:
        relative: The path relative to ``docs/``, POSIX-style.
        patterns: The raw ``exclude_docs`` entries.

    Returns:
        ``True`` when the path matches a filename entry at any depth or sits
        under a directory entry (an entry ending in ``/``).
    """
    for pattern in patterns:
        if pattern.endswith("/"):
            if relative.startswith(pattern):
                return True
        elif Path(relative).name == pattern:
            return True
    return False


def _built_pages(patterns: list[str]) -> list[Path]:
    """Every markdown page MkDocs actually builds.

    Args:
        patterns: The raw ``exclude_docs`` entries.

    Returns:
        The page paths, sorted for a stable failure order.
    """
    return sorted(
        page
        for page in DOCS.rglob("*.md")
        if not _is_excluded(page.relative_to(DOCS).as_posix(), patterns)
    )


def _links(page: Path) -> list[str]:
    """Collect the relative ``.md`` link targets on one page.

    Fenced code blocks are stripped first: a markdown link shown as a code
    sample is documentation about a link, not a link.

    Args:
        page: The markdown file to scan.

    Returns:
        The raw link targets, anchors already dropped.
    """
    text = _FENCE_RE.sub("", page.read_text(encoding="utf-8"))
    return [match.group(1) for match in _LINK_RE.finditer(text)]


def test_relative_links_resolve_to_pages_that_are_built() -> None:
    """No relative link points at a missing or excluded page.

    Both failure modes end the same way for a reader — a 404 on the published
    site — and neither fails ``mkdocs build --strict``. Excluded targets are
    reported separately from missing ones because the fixes differ: an excluded
    target wants the GitHub blob URL (the pattern ``docs/index.md`` already
    uses), a missing one is a typo or a page that moved.
    """
    patterns = _excluded_patterns()
    missing: list[str] = []
    excluded: list[str] = []

    for page in _built_pages(patterns):
        for target in _links(page):
            resolved = (page.parent / target).resolve()
            try:
                relative = resolved.relative_to(DOCS).as_posix()
            except ValueError:
                missing.append(
                    f"{page.relative_to(REPO_ROOT)} -> {target} (outside docs/)"
                )
                continue
            if not resolved.is_file():
                missing.append(f"{page.relative_to(REPO_ROOT)} -> {target}")
            elif _is_excluded(relative, patterns):
                excluded.append(f"{page.relative_to(REPO_ROOT)} -> {target}")

    assert not excluded, (
        "links to pages excluded from the built site (use the GitHub blob URL, "
        "as docs/index.md does):\n  " + "\n  ".join(excluded)
    )
    assert not missing, "links to pages that do not exist:\n  " + "\n  ".join(missing)
