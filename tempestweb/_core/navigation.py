"""Navigation primitives: routes and the navigation stack.

A mobile app is more than one screen. This module models the **navigation
stack** as plain, serializable Pydantic objects, mirroring ``go_router``
(Flutter) and React Navigation (RN): a :class:`Route` names a screen and carries
typed parameters, and a :class:`NavStack` is the ordered list of routes from the
root to the screen on top.

The stack is **not** a new IR node. The ``view(app)`` reads ``app.nav.top`` and
builds the screen's subtree, so changing routes is just the view producing a
different tree — the existing reconciler diffs it into patches with no new patch
kind. :class:`App` owns a :class:`NavStack` and mutates it through
``push``/``pop``/``replace``/``reset``, each scheduling a single coalesced
rebuild. Per-renderer transition handling (``slide``, ``fade``) is a hint the
renderers consume; it is not modelled here.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "Route",
    "NavStack",
    "routes_from_path",
]


class Route(BaseModel):
    """A single navigation destination.

    A route is an immutable value (frozen, like :class:`~tempestroid.style.Style`
    and :class:`~tempestroid.widgets.Event`) so the navigation stack can be
    compared and diffed by value.

    Attributes:
        name: The route name (a path-like identifier, e.g. ``"/"`` or
            ``"/details"``).
        params: Typed parameters passed to the destination screen.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    params: dict[str, Any] = Field(default_factory=dict)


class NavStack(BaseModel):
    """The ordered stack of routes, from root to the visible screen.

    Unlike :class:`Route`, the stack is **mutable**: :class:`~tempestroid.App`
    pushes, pops, replaces and resets it in place and schedules a rebuild. The
    bottom of the stack is the root route; the top is the screen currently shown.

    Attributes:
        stack: The route stack. Defaults to a single root route ``"/"`` so an app
            always has a screen to render.

    Properties:
        top: The route on top of the stack (the visible screen).
        can_pop: Whether the stack can be popped without emptying it.
    """

    stack: list[Route] = Field(default_factory=lambda: [Route(name="/")])

    @property
    def top(self) -> Route:
        """The route on top of the stack (the visible screen).

        Returns:
            The top-most route.
        """
        return self.stack[-1]

    @property
    def can_pop(self) -> bool:
        """Whether the stack can be popped without emptying it.

        Returns:
            ``True`` when more than one route is on the stack (a back navigation
            is possible), ``False`` at the root.
        """
        return len(self.stack) > 1


def routes_from_path(path: str) -> list[Route]:
    """Resolve a deep-link path into an initial navigation stack.

    A deep link arrives as an intent extra on the device (or a launch argument
    in the simulator) and is resolved to the stack the app should open on. This
    is the device-independent half of the deep-link path: the entry point passes
    the resulting stack to :meth:`~tempestroid.App.reset` so the app opens
    directly on the linked screen with its back stack already built.

    The path is split on ``"/"`` into cumulative segments, so ``"/a/b"`` opens
    the stack ``["/", "/a", "/a/b"]`` — the user can pop back through the
    intermediate screens. The root ``"/"`` (or an empty path) yields the single
    root route, matching :class:`NavStack`'s default.

    Args:
        path: The deep-link path (e.g. ``"/details"`` or ``"/shop/item"``).

    Returns:
        A non-empty list of routes from the root to the linked screen.
    """
    segments = [segment for segment in path.split("/") if segment]
    routes: list[Route] = [Route(name="/")]
    accumulated = ""
    for segment in segments:
        accumulated = f"{accumulated}/{segment}"
        routes.append(Route(name=accumulated))
    return routes
