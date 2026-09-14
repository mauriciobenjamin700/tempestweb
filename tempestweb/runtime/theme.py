"""Resolution of ``ThemeMode.SYSTEM`` against the platform dark-mode flag.

``Theme.is_dark()`` and ``Theme.scheme()`` take ``platform_dark_mode`` as a
keyword with a ``False`` default, and nothing on the render path ever filled it
in: ``SYSTEM`` — the default of both ``Theme()`` and ``Theme.from_seed()``, and
the mode whose contract is *"defers to the platform"* — resolved light forever.

Rather than thread the flag through every widget that reads the theme, the
runtime **materializes** the decision once, before the build: an app whose
declared theme is ``SYSTEM`` runs with an equivalent theme pinned to ``LIGHT``
or ``DARK`` by the client's last ``media`` report. Both halves of the #148 split
then agree by construction — the widgets resolve their colors from the pinned
mode, and the stylesheet's ``data-tw-theme`` comes from the same
``Theme.is_dark()`` call the runtimes already make.

The theme the app declared is remembered per app, so the resolution is
reversible: the platform returning to light re-pins ``LIGHT`` instead of leaving
the app stuck on the dark it once resolved. An app that swaps its own theme
(``App.set_theme``) is detected by identity and becomes the new declared theme.
"""

from typing import Any
from weakref import WeakKeyDictionary

from tempest_core import App, Theme, ThemeMode

__all__ = ["resolve_platform_theme"]

_DECLARED: "WeakKeyDictionary[App[Any], Theme]" = WeakKeyDictionary()
_INSTALLED: "WeakKeyDictionary[App[Any], Theme]" = WeakKeyDictionary()


def resolve_platform_theme(app: App[Any]) -> bool:
    """Pin the app's ``SYSTEM`` theme to the platform's current dark-mode flag.

    Reads ``app.media.platform_dark_mode`` — kept current by the client's
    ``media`` event — and installs, via :meth:`~tempest_core.App.set_theme`, a
    copy of the declared theme whose mode is the resolved one. A theme declared
    ``LIGHT`` or ``DARK`` is absolute and left untouched.

    Idempotent: calling it again with an unchanged flag installs nothing and
    requests no rebuild, so it is safe to call on every ``media`` event and at
    mount.

    Args:
        app: The application whose theme context to resolve.

    Returns:
        ``True`` when a different theme was installed (and a rebuild requested).
    """
    current = getattr(app, "theme", None)
    if not isinstance(current, Theme):
        return False
    declared = _DECLARED.get(app)
    if declared is None or current is not _INSTALLED.get(app):
        declared = current
        _DECLARED[app] = declared
    if declared.mode is not ThemeMode.SYSTEM:
        _INSTALLED[app] = current
        return False
    media = getattr(app, "media", None)
    dark = bool(getattr(media, "platform_dark_mode", False))
    resolved = declared.model_copy(
        update={"mode": ThemeMode.DARK if dark else ThemeMode.LIGHT}
    )
    if current.mode is resolved.mode and current is not declared:
        _INSTALLED[app] = current
        return False
    app.set_theme(resolved)
    _INSTALLED[app] = resolved
    return True
