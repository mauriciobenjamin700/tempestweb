"""Mirror ``mkdocs-redirects`` stubs into the English site tree.

``mkdocs-static-i18n`` builds two sites — the default locale at the root and
``en`` under ``site/en/`` — by running a nested build per locale.
``mkdocs-redirects`` writes its stub pages from ``on_post_build``, which runs
once for the outer build, so every redirect lands in the root tree only. A
reader who follows an old English URL (``/en/security/``) gets a 404 while the
Portuguese one (``/security/``) redirects correctly.

Plugin ordering does not fix it: the stubs are absent from ``site/en/`` whether
``redirects`` is declared before or after ``i18n``.

This hook copies each stub that ``mkdocs-redirects`` produced into the matching
path under ``site/en/``. Copying is deliberate rather than re-generating the
HTML: the stub's ``href`` is relative to its own directory, and the English tree
mirrors the root tree's shape exactly, so the same bytes are correct in both.

Wired through ``hooks:`` in ``mkdocs.yml``. Guarded by
``tests/unit/test_docs_redirects.py``, which builds the site and asserts both
trees carry every stub.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from mkdocs.config.defaults import MkDocsConfig

LOGGER: logging.Logger = logging.getLogger("mkdocs.hooks.i18n_redirects")

#: The locale sub-directory ``mkdocs-static-i18n`` builds alongside the default
#: one. Kept as a constant because the hook has no access to the i18n plugin's
#: resolved locale list at ``on_post_build`` time.
LOCALE_DIR: str = "en"


def _stub_path(old_page: str) -> str:
    """Map a ``redirect_maps`` key to the file ``mkdocs-redirects`` writes.

    Mirrors the plugin's own naming under ``use_directory_urls`` (the default):
    ``security.md`` becomes ``security/index.html``. A key that already names an
    HTML file is used unchanged, which is the plugin's other accepted form.

    Args:
        old_page: A ``redirect_maps`` key, e.g. ``"security.md"``.

    Returns:
        The stub's path relative to the site directory.
    """
    if old_page.endswith(".md"):
        return f"{old_page[: -len('.md')]}/index.html"
    return old_page


def on_post_build(config: MkDocsConfig, **kwargs: object) -> None:
    """Copy every redirect stub into the English tree.

    Runs after both the root build and the nested locale builds have written
    their output, so ``site/en/`` already exists and only the stubs are missing.
    A stub that is absent from the root tree is logged and skipped rather than
    raised on: the redirect plugin may be disabled, and a docs build should not
    die because of a mirroring step.

    MkDocs calls this once per locale pass, all of them with the *same*
    ``site_dir``, so the passes cannot be told apart by path. On the first pass
    ``site/en/`` does not exist yet and the hook returns after an ``INFO`` line;
    the last pass finds it and does the copying. The message is deliberately not
    a warning — the state is normal, and ``mkdocs build --strict`` promotes any
    warning to a build failure. A mirroring that genuinely fails to happen is
    caught by ``tests/unit/test_docs_redirects.py``, which asserts the stubs
    exist in both trees after a real build.

    Args:
        config: The resolved MkDocs config.
        **kwargs: Forward compatibility with MkDocs' hook signature; unused.

    Returns:
        None.
    """
    plugin = config.plugins.get("redirects")
    if plugin is None:
        return
    redirect_maps: dict[str, str] = plugin.config.get("redirect_maps") or {}
    if not redirect_maps:
        return

    site_dir = Path(config.site_dir)
    locale_root = site_dir / LOCALE_DIR
    if not locale_root.is_dir():
        LOGGER.info(
            "i18n_redirects: %s/ not written yet; a later pass mirrors", LOCALE_DIR
        )
        return

    copied = 0
    for old_page in redirect_maps:
        relative = _stub_path(old_page)
        source = site_dir / relative
        if not source.is_file():
            LOGGER.warning("i18n_redirects: no stub at %s; skipping", relative)
            continue
        target = locale_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        copied += 1
    LOGGER.info("i18n_redirects: mirrored %d redirect(s) into %s/", copied, LOCALE_DIR)
