"""Guard: every error message quoted in the troubleshooting page still exists.

A troubleshooting page is only useful if pasting the message from your terminal
into the site's search finds it. That breaks the first time someone rewords an
exception and does not think to grep the docs — and it breaks silently, because
no build step relates prose to source strings.

Convention this guard relies on: in ``troubleshooting.md`` (and its ``.en``
mirror), a fenced block tagged ``text`` holding a **single line** is a literal
message that must appear verbatim in ``tempestweb/``. Fences in any other
language are examples and are ignored, as are multi-line ``text`` fences (shell
transcripts and the like).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = REPO_ROOT / "tempestweb"
PAGES = (
    REPO_ROOT / "docs" / "troubleshooting.md",
    REPO_ROOT / "docs" / "troubleshooting.en.md",
)

#: A fenced block explicitly tagged ``text``, capturing its body.
_TEXT_FENCE_RE = re.compile(r"^```text[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)

#: Implicit string concatenation in formatted Python always spans a newline, and
#: the two adjacent quotes may differ (``"`` then ``'``). Removing the pair
#: rejoins the message; a quote pair on one line is real content and is left be.
_IMPLICIT_JOIN_RE = re.compile(r"""["']\s*\n\s*["']""")


def _package_source() -> str:
    """All package source, with wrapped string literals rejoined.

    Returns:
        The concatenated source, whitespace-collapsed so a message split across
        source lines still matches the single line the docs quote.
    """
    raw = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(PACKAGE.rglob("*.py"))
    )
    return re.sub(r"\s+", " ", _IMPLICIT_JOIN_RE.sub("", raw))


def _quoted_messages(page: Path) -> list[str]:
    """The single-line ``text`` fences on one page.

    Args:
        page: The troubleshooting page to scan.

    Returns:
        The quoted messages, stripped.
    """
    messages: list[str] = []
    for body in _TEXT_FENCE_RE.findall(page.read_text(encoding="utf-8")):
        lines = [line for line in body.splitlines() if line.strip()]
        if len(lines) == 1:
            messages.append(lines[0].strip())
    return messages


def test_quoted_error_messages_exist_in_the_source() -> None:
    """A quoted message that no longer exists makes the page unsearchable.

    The reader pastes what their terminal printed, finds nothing, and concludes
    the situation is undocumented — worse than having no page, because the page
    looks authoritative.
    """
    source = _package_source()
    stale: list[str] = []
    for page in PAGES:
        for message in _quoted_messages(page):
            if re.sub(r"\s+", " ", message) not in source:
                stale.append(f"{page.name}: {message}")
    assert not stale, (
        "messages quoted in the docs that are not in tempestweb/ any more "
        "(reword the docs, or restore the message):\n  " + "\n  ".join(stale)
    )


def test_both_pages_quote_the_same_messages() -> None:
    """The locales must document the same errors, or one is a partial page.

    A message added to one language and not the other is the usual way a
    bilingual troubleshooting page rots.
    """
    pt, en = (set(_quoted_messages(page)) for page in PAGES)
    only_pt, only_en = sorted(pt - en), sorted(en - pt)
    assert not only_pt and not only_en, (
        "the two locales quote different messages:\n"
        f"  only in PT: {only_pt}\n  only in EN: {only_en}"
    )


def test_the_page_quotes_something() -> None:
    """A guard that silently matches nothing is worse than no guard.

    If the fence convention changes, this fails instead of the suite going green
    on an empty set.
    """
    assert len(_quoted_messages(PAGES[0])) >= 8, (
        "fewer quoted messages than expected — did the ```text fence convention change?"
    )
