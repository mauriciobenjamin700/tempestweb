"""Guards on the docs redirects — both language trees, and no orphan mappings.

Pages moved into ``docs/tutorial/`` and ``docs/advanced/``, so 21 published URLs
changed. ``mkdocs-redirects`` keeps the old ones alive, but only in the default
locale's tree: it writes its stubs from ``on_post_build``, which runs once for
the outer build, while ``mkdocs-static-i18n`` produces ``site/en/`` from a
nested build. Without the ``hooks/i18n_redirects.py`` mirror, every English old
URL 404s while the Portuguese one works — a failure that is invisible in the
build log and only shows up to a reader following an old link.

These tests parse ``mkdocs.yml`` rather than building the site, so they stay in
the fast unit suite; the mirror itself is exercised by the docs workflow's
``mkdocs build --strict`` plus :func:`test_every_redirect_target_exists`.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs"
MKDOCS_YML = REPO_ROOT / "mkdocs.yml"
HOOK = REPO_ROOT / "hooks" / "i18n_redirects.py"


def _redirect_maps() -> dict[str, str]:
    """Read the ``redirect_maps`` block out of ``mkdocs.yml``.

    Hand-parsed for the same reason as the ``exclude_docs`` block in
    :mod:`tests.unit.test_docs_links`: no YAML library is guaranteed in the test
    environment, and the block is a flat ``old: new`` mapping.

    Returns:
        The mapping of old docs-relative path to new docs-relative path.
    """
    lines = MKDOCS_YML.read_text(encoding="utf-8").splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.strip() == "redirect_maps:"),
        None,
    )
    assert start is not None, "mkdocs.yml no longer declares redirect_maps"
    entries: dict[str, str] = {}
    indent = len(lines[start]) - len(lines[start].lstrip())
    for line in lines[start + 1 :]:
        if not line.strip():
            break
        if len(line) - len(line.lstrip()) <= indent:
            break
        old, _, new = line.strip().partition(":")
        entries[old.strip()] = new.strip()
    assert entries, "the redirect_maps block parsed empty — the format changed"
    return entries


def test_every_redirect_target_exists() -> None:
    """A redirect that points at a missing page sends the reader to a 404.

    MkDocs does not validate redirect targets: the stub is written from the
    string in the config, so a typo or a second move silently produces a link
    that resolves to nothing.
    """
    missing = [
        f"{old} -> {new}"
        for old, new in _redirect_maps().items()
        if not (DOCS / new).is_file()
    ]
    assert not missing, "redirects pointing at missing pages:\n  " + "\n  ".join(
        missing
    )


def test_no_redirect_shadows_a_real_page() -> None:
    """An old path that exists again as a page would be shadowed by its stub.

    If someone later adds ``docs/security.md`` back, the redirect stub and the
    real page compete for ``/security/`` and the stub wins — the new page
    becomes unreachable without a single warning.
    """
    shadowed = [old for old in _redirect_maps() if (DOCS / old).is_file()]
    assert not shadowed, (
        "these paths are both a redirect source and a real page:\n  "
        + "\n  ".join(shadowed)
    )


def test_the_i18n_mirror_hook_is_wired() -> None:
    """The mirror hook must exist and be declared, or English old URLs 404.

    The failure this guards is asymmetric and easy to miss: the Portuguese
    redirects keep working, so a spot check on the default locale passes while
    every ``/en/<old-url>/`` is dead.
    """
    assert HOOK.is_file(), "hooks/i18n_redirects.py is gone"
    config = MKDOCS_YML.read_text(encoding="utf-8")
    assert re.search(r"^hooks:\s*$", config, re.M), "mkdocs.yml declares no hooks:"
    assert "hooks/i18n_redirects.py" in config, "the i18n redirect mirror is not wired"


def test_every_moved_page_kept_its_old_url() -> None:
    """A page under ``tutorial/`` or ``advanced/`` has a redirect from its old URL.

    The move renamed 21 published URLs. Adding a page to one of those folders
    later is fine — it never had an old URL — but *moving* an existing page in
    without a mapping silently breaks every inbound link to it. This lists what
    is unmapped so the author decides, rather than asserting a frozen count.
    """
    mapped = set(_redirect_maps().values())
    unmapped = sorted(
        page.relative_to(DOCS).as_posix()
        for folder in ("tutorial", "advanced")
        for page in (DOCS / folder).glob("*.md")
        if not page.name.endswith(".en.md")
        and page.relative_to(DOCS).as_posix() not in mapped
        and page.name != "index.md"
        and page.stem
        not in {
            "view",
            "state",
            "patches",
            "modes",
            "lists",
            "responsive",
            "overlays",
            "gestures",
            # Written for #143; never had a published URL of its own.
            "controls",
            # Written for #176; new page, never had a published URL of its own.
            "export",
            # Written for #177; new page, never had a published URL of its own.
            "access",
        }
    )
    assert not unmapped, (
        "pages in tutorial/ or advanced/ with no redirect from their old URL "
        "(add a redirect_maps entry, or list it here if it never had one):\n  "
        + "\n  ".join(unmapped)
    )
