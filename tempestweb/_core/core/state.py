"""Application state and the coalesced rebuild loop.

An :class:`App` ties together mutable state, a ``view`` function that turns that
state into a widget tree, and a renderer's ``apply`` callback. State mutations
schedule a rebuild on the asyncio loop; several mutations in the same tick
collapse into a single ``build → diff → patch`` pass, so the UI never flickers
or does redundant work.

The runtime is renderer-agnostic — it only emits patches and hands them to the
``apply_patches`` callback. The Qt runner wires this to :class:`QtRenderer`; a
future Compose runner would wire the same loop to the device.
"""

from __future__ import annotations

import asyncio
import uuid as _uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar, cast

from tempestweb._core.animation import AnimationController
from tempestweb._core.core.ir import Patch, Scene
from tempestweb._core.core.reconciler import build_scene, diff_scene
from tempestweb._core.i18n import Locale
from tempestweb._core.navigation import NavStack, Route
from tempestweb._core.theme import MediaQueryData, Theme
from tempestweb._core.widgets import LazyColumn, LazyGrid, LazyRow, SectionList, Widget

__all__ = ["App", "OverlayEntry"]

S = TypeVar("S")

#: The virtualized list widgets whose visible window the app tracks and slides.
_LAZY_LISTS: tuple[type[Widget], ...] = (LazyColumn, LazyRow, LazyGrid)


@dataclass
class OverlayEntry:
    """One slot in the app's floating overlay layer.

    Attributes:
        id: Stable overlay id (a UUID), used as the overlay node's ``key``.
        widget: The overlay's widget tree.
        barrier: Whether a touch-blocking scrim sits behind the overlay.
        is_toast: Whether this overlay auto-dismisses on a timer (a toast).
    """

    id: str
    widget: Widget
    barrier: bool
    is_toast: bool = False


class App(Generic[S]):
    """Owns app state and drives coalesced rebuilds.

    The ``view`` receives the app itself, so it can read ``app.state`` and wire
    handlers that call :meth:`set_state` (sync or from inside an ``async``
    handler). This avoids any circular dependency between the view and the app.

    The app also owns a :class:`~tempestroid.navigation.NavStack` (``self.nav``),
    independent of the generic state ``S``. The ``view`` reads ``app.nav.top`` to
    decide which screen to build; :meth:`push`/:meth:`pop`/:meth:`replace`/
    :meth:`reset` mutate the stack and schedule the same coalesced rebuild as a
    state change, so navigation flows through the existing diff with no new patch
    kind.

    Type Args:
        S: The application state type.

    Methods:
        start: Build the initial scene and record it as the current tree.
        set_state: Mutate state (optionally) and request a coalesced rebuild.
        swap_view: Swap the ``view`` function and rebuild against live state.
        request_rebuild: Schedule a single coalesced rebuild on the event loop.
        push / pop / replace / reset: Navigation-stack mutations (each rebuilds).
        show_dialog / show_sheet / show_menu / toast: Push an overlay layer entry.
        dismiss: Remove an overlay by id and request a rebuild.
        set_theme / set_locale: Swap the active theme/locale and rebuild.
        slide_window / slide_section_window: Set a virtualized list's visible window.
        register_animation / unregister_animation: Manage the frame-clock controllers.

    Properties:
        current_tree: The most recently built scene (``None`` before ``start``).
        has_animations: Whether any animation controller is active on the clock.
    """

    def __init__(
        self,
        state: S,
        view: Callable[[App[S]], Widget],
        apply_patches: Callable[[list[Patch]], None],
        nav: NavStack | None = None,
        *,
        time_source: Callable[[], float] | None = None,
        theme: Theme | None = None,
        media: MediaQueryData | None = None,
        locale: Locale | None = None,
    ) -> None:
        """Initialize the app.

        Args:
            state: The initial application state.
            view: Builds the widget tree from the app (reads ``app.state`` and
                ``app.nav.top``).
            apply_patches: Renderer callback that applies a patch list.
            nav: The initial navigation stack. Defaults to a fresh
                :class:`~tempestroid.navigation.NavStack` with the root route.
            time_source: Optional monotonic clock (seconds) used by the animation
                frame loop to compute the per-frame ``dt``. Tests inject a
                deterministic source; the Qt runner passes ``loop.time``. Defaults
                to the event loop's clock.
            theme: The initial theme context the ``view`` reads. Defaults to a
                fresh :class:`~tempestroid.theme.Theme` (``SYSTEM`` mode).
            media: The initial media-query context the ``view`` reads. Defaults to
                a fresh :class:`~tempestroid.theme.MediaQueryData`.
            locale: The initial locale context the ``view`` reads. Defaults to a
                fresh :class:`~tempestroid.i18n.Locale` (``pt``, LTR).
        """
        self.state: S = state
        self.nav: NavStack = nav if nav is not None else NavStack()
        # Theme/media/locale are *input context* the view reads — not nodes in
        # the tree. Each is an immutable snapshot swapped wholesale (set_theme /
        # set_locale / _update_media), so a change schedules one coalesced
        # rebuild like any state mutation, with no new patch kind.
        self.theme: Theme = theme if theme is not None else Theme()
        self.media: MediaQueryData = media if media is not None else MediaQueryData()
        self.locale: Locale = locale if locale is not None else Locale()
        self._view: Callable[[App[S]], Widget] = view
        self._apply: Callable[[list[Patch]], None] = apply_patches
        self._current: Scene | None = None
        # The floating overlay layer, in ascending z-order. Mutated by the
        # imperative overlay API (`show_dialog`/`show_sheet`/`toast`/`show_menu`/
        # `dismiss`) and folded into every build as the scene's `overlays`.
        self._overlays: list[OverlayEntry] = []
        self._rebuild_scheduled: bool = False
        # The animation frame clock. ``_animations`` holds every active
        # controller; the clock runs (re-arming ``loop.call_later(1/60)``) only
        # while it is non-empty. ``_time_source`` is injectable for deterministic
        # tests; ``_last_tick`` records the previous frame's timestamp so each
        # tick advances the controllers by the real elapsed ``dt``.
        self._animations: set[AnimationController] = set()
        # Resolved lazily by ``_now`` so construction never touches the loop
        # (which would warn/raise outside a running loop). ``None`` means "use
        # the event loop's clock".
        self._time_source: Callable[[], float] | None = time_source
        self._last_tick: float = 0.0
        self._tick_scheduled: bool = False
        # Visible-window overrides for virtualized lists, keyed by the list's
        # `key`; SectionList sections are keyed `"<list_key>::<section_title>"`.
        # Injected into the freshly built tree (see `_build`) so a slid window
        # survives the view re-running, and the materialized window children
        # cross to the renderer as the list node's `children`.
        self._windows: dict[str, tuple[int, int]] = {}

    def start(self) -> Scene:
        """Build the initial scene and record it as the current tree.

        Returns:
            The :class:`Scene` (root tree + overlay layer), ready to hand to a
            renderer's ``mount``.
        """
        self._current = self._build()
        return self._current

    @property
    def has_animations(self) -> bool:
        """Whether at least one animation controller is active on the frame clock.

        The device bridge reads this when serializing a ``mount``/``patch`` so the
        Compose host knows whether to run its ``withFrameNanos`` loop (and emit the
        reserved ``__frame__`` token). It flips ``True`` as soon as a controller is
        registered (:meth:`register_animation`) and back to ``False`` once the last
        controller settles and is dropped by :meth:`_tick`/:meth:`_tick_from_device`.

        Returns:
            ``True`` when one or more controllers are active, ``False`` otherwise.
        """
        return bool(self._animations)

    @property
    def current_tree(self) -> Scene | None:
        """The most recently built scene (``None`` before :meth:`start`).

        Returns:
            The current scene, or ``None``.
        """
        return self._current

    def swap_view(self, view: Callable[[App[S]], Widget]) -> list[Patch]:
        """Swap the ``view`` function and rebuild against the live state.

        This is **stateful hot reload**: unlike a hot restart (which throws the
        state away and remounts), it keeps the current state object and diffs the
        tree built by the *new* view against the current tree, so on-screen state
        survives a code edit. The new tree is built eagerly (synchronously) so an
        incompatible view — e.g. one reading a state attribute the preserved
        state lacks — raises here and the old view stays installed, letting the
        caller fall back to a clean restart.

        Args:
            view: The new view function (typically from a reloaded module).

        Returns:
            The patches applied to reconcile the new tree (``[]`` if unchanged).

        Raises:
            RuntimeError: If called before :meth:`start`.
            Exception: Whatever the new ``view``/``build`` raises — the swap is
                rolled back (the old view stays installed) before re-raising.
        """
        if self._current is None:
            raise RuntimeError("cannot swap_view before start()")
        # Build with the new view eagerly so a failure aborts before we commit;
        # the old self._view is untouched until the build succeeds.
        new = build_scene(
            self._inject_windows(view(self)), self._overlay_specs()
        )
        self._view = view
        patches = diff_scene(self._current, new)
        self._current = new
        if patches:
            self._apply(patches)
        return patches

    def set_state(self, mutate: Callable[[S], None] | None = None) -> None:
        """Mutate state (optionally) and request a coalesced rebuild.

        Args:
            mutate: Optional callback that mutates ``self.state`` in place.
        """
        if mutate is not None:
            mutate(self.state)
        self.request_rebuild()

    def set_theme(self, theme: Theme) -> None:
        """Swap the active theme and request a coalesced rebuild.

        The ``view`` reads ``app.theme`` on the next build, so toggling dark/light
        (or a palette) flows through the existing diff with no new patch kind.

        Args:
            theme: The new theme context.
        """
        self.theme = theme
        self.request_rebuild()

    def set_locale(self, locale: Locale) -> None:
        """Swap the active locale and request a coalesced rebuild.

        The ``view`` reads ``app.locale`` (language for string lookup,
        ``locale.rtl`` for layout direction) on the next build.

        Args:
            locale: The new locale context.
        """
        self.locale = locale
        self.request_rebuild()

    def _update_media(self, data: MediaQueryData) -> None:
        """Update the media-query context and request a coalesced rebuild.

        Called by the renderer when the viewport, density, text-scale, OS dark
        mode, or orientation changes, so a responsive ``view`` re-runs against
        the new environment.

        Args:
            data: The new media-query snapshot.
        """
        self.media = data
        self.request_rebuild()

    def slide_window(self, key: str, start: int, end: int) -> None:
        """Set the visible window of a virtualized list and request a rebuild.

        A renderer (or the device bridge) calls this from a list's scroll handler:
        the new ``[start, end)`` window is recorded by the list's ``key`` and
        injected into the next build, so :class:`LazyColumn`/:class:`LazyRow`/
        :class:`LazyGrid` materialize the slid window. Through the keyed diff this
        becomes a minimal remove/reorder/insert patch sequence.

        Args:
            key: The ``key`` of the target list widget.
            start: The first visible index (inclusive).
            end: The one-past-last visible index (exclusive).
        """
        self._windows[key] = (start, end)
        self.request_rebuild()

    def slide_section_window(
        self, key: str, section_title: str, start: int, end: int
    ) -> None:
        """Set the visible window of one section of a :class:`SectionList`.

        Args:
            key: The ``key`` of the target :class:`SectionList` widget.
            section_title: The ``title`` of the section to slide.
            start: The first visible index (inclusive) within that section.
            end: The one-past-last visible index (exclusive) within that section.
        """
        self._windows[f"{key}::{section_title}"] = (start, end)
        self.request_rebuild()

    def _build(self) -> Scene:
        """Build the current scene: the view's tree plus the overlay layer.

        Tracked list windows are injected into the root tree first; the floating
        overlays are folded in as the scene's overlay layer.

        Returns:
            The freshly built :class:`Scene` with virtualized lists materialized
            at their tracked windows.
        """
        return build_scene(
            self._inject_windows(self._view(self)), self._overlay_specs()
        )

    def _overlay_specs(self) -> list[tuple[str, Widget, bool]]:
        """Lower the overlay entries to ``(id, widget, barrier)`` build tuples.

        Returns:
            The overlay layer in ascending z-order, ready for
            :func:`~tempestroid.core.reconciler.build_scene`.
        """
        return [(entry.id, entry.widget, entry.barrier) for entry in self._overlays]

    def _inject_windows(self, widget: Widget) -> Widget:
        """Rewrite a widget tree to carry the app's tracked list windows.

        Walks the tree by ``child_field_names``; a virtualized list with a tracked
        window (matched by ``key``) is copied with its ``window`` set, so its
        ``child_nodes`` materializes the slid window at build time. Trees without
        any tracked window are returned untouched (the common, allocation-free
        path), so lists fall back to their declared initial window on first mount.

        Args:
            widget: The root widget built by the view.

        Returns:
            The (possibly rewritten) widget tree.
        """
        if not self._windows:
            return widget
        return self._inject(widget)

    def _inject(self, widget: Widget) -> Widget:
        """Recursively apply tracked windows to a widget and its children.

        Args:
            widget: The widget to rewrite.

        Returns:
            The rewritten widget (a copy when a window applies or a child changed).
        """
        updates: dict[str, object] = {}

        if isinstance(widget, _LAZY_LISTS) and widget.key in self._windows:
            updates["window"] = self._windows[widget.key]
        elif isinstance(widget, SectionList):
            sections = [
                section.model_copy(update={"window": window})
                if (
                    widget.key is not None
                    and (
                        window := self._windows.get(
                            f"{widget.key}::{section.title}"
                        )
                    )
                    is not None
                )
                else section
                for section in widget.sections
            ]
            if any(
                new is not old
                for new, old in zip(sections, widget.sections, strict=True)
            ):
                updates["sections"] = sections

        for field in type(widget).child_field_names:
            value = getattr(widget, field)
            if isinstance(value, list):
                children = cast("list[Widget]", value)
                new_children = [self._inject(child) for child in children]
                if any(
                    new is not old
                    for new, old in zip(new_children, children, strict=True)
                ):
                    updates[field] = new_children
            elif isinstance(value, Widget):
                new_child = self._inject(value)
                if new_child is not value:
                    updates[field] = new_child

        return widget.model_copy(update=updates) if updates else widget

    def push(self, route: Route) -> None:
        """Push a route onto the navigation stack and request a rebuild.

        Args:
            route: The destination route to navigate to.
        """
        self.nav.stack.append(route)
        self.request_rebuild()

    def pop(self) -> bool:
        """Pop the top route, returning to the previous screen.

        At the root (a single route on the stack) this is a no-op: the stack is
        left untouched so the host can take its default back action (e.g. close
        the app on Android).

        Returns:
            ``True`` if a route was popped, ``False`` if already at the root.
        """
        if not self.nav.can_pop:
            return False
        self.nav.stack.pop()
        self.request_rebuild()
        return True

    def replace(self, route: Route) -> None:
        """Replace the top route in place (no stack-depth change).

        Args:
            route: The route to put on top, replacing the current screen.
        """
        self.nav.stack[-1] = route
        self.request_rebuild()

    def reset(self, stack: list[Route]) -> None:
        """Replace the entire navigation stack and request a rebuild.

        Args:
            stack: The new, non-empty route stack (e.g. for a deep link).

        Raises:
            ValueError: If ``stack`` is empty — an app must always have a screen.
        """
        if not stack:
            raise ValueError("navigation stack cannot be empty")
        self.nav.stack = list(stack)
        self.request_rebuild()

    def show_dialog(self, widget: Widget, *, barrier: bool = True) -> str:
        """Push a modal dialog onto the overlay layer.

        Args:
            widget: The dialog widget (typically a :class:`~tempestroid.Dialog`).
            barrier: Whether a touch-blocking scrim sits behind the dialog.

        Returns:
            The stable overlay id, for a later :meth:`dismiss`.
        """
        return self._push(widget, barrier=barrier)

    def show_sheet(self, widget: Widget, *, barrier: bool = True) -> str:
        """Push a bottom sheet onto the overlay layer.

        Args:
            widget: The sheet widget (typically a
                :class:`~tempestroid.BottomSheet`).
            barrier: Whether a touch-blocking scrim sits behind the sheet.

        Returns:
            The stable overlay id, for a later :meth:`dismiss`.
        """
        return self._push(widget, barrier=barrier)

    def show_menu(
        self, widget: Widget, *, anchor: str | None = None, barrier: bool = False
    ) -> str:
        """Push a menu or popover onto the overlay layer.

        Args:
            widget: The menu widget (typically a :class:`~tempestroid.Menu` or
                :class:`~tempestroid.Popover`). When it exposes an ``anchor``
                field and ``anchor`` is given, the anchor is applied to the
                widget so the renderer can position the menu.
            anchor: Optional ``key`` of the widget to anchor the menu to.
            barrier: Whether a touch-blocking scrim sits behind the menu
                (menus are usually anchored and barrier-free).

        Returns:
            The stable overlay id, for a later :meth:`dismiss`.
        """
        if anchor is not None and "anchor" in type(widget).model_fields:
            widget = widget.model_copy(update={"anchor": anchor})
        return self._push(widget, barrier=barrier)

    def toast(self, widget: Widget, *, duration_s: float = 2.5) -> str:
        """Push a transient toast that auto-dismisses after ``duration_s``.

        The auto-dismiss is scheduled on the event loop via ``call_later``; the
        app remains authoritative over the toast's lifetime even if a renderer
        also runs its own visual timer.

        Args:
            widget: The toast widget (typically a :class:`~tempestroid.Toast`).
            duration_s: How long the toast stays visible, in seconds.

        Returns:
            The stable overlay id (also dismissable early via :meth:`dismiss`).
        """
        overlay_id = self._push(widget, barrier=False, is_toast=True)
        self._loop().call_later(duration_s, self.dismiss, overlay_id)
        return overlay_id

    def dismiss(self, overlay_id: str) -> None:
        """Remove an overlay by id and request a rebuild.

        A no-op when the id is unknown (e.g. a toast already auto-dismissed, or a
        double dismiss), so renderer-driven and timer-driven dismissals are safe
        to race.

        Args:
            overlay_id: The id returned by a ``show_*``/``toast`` call.
        """
        before = len(self._overlays)
        self._overlays = [e for e in self._overlays if e.id != overlay_id]
        if len(self._overlays) != before:
            self.request_rebuild()

    def _push(
        self, widget: Widget, *, barrier: bool, is_toast: bool = False
    ) -> str:
        """Append an overlay entry and request a rebuild.

        Args:
            widget: The overlay widget.
            barrier: Whether a touch-blocking scrim sits behind it.
            is_toast: Whether it auto-dismisses on a timer.

        Returns:
            The new overlay's stable id.
        """
        overlay_id = _uuid.uuid4().hex
        self._overlays.append(
            OverlayEntry(
                id=overlay_id, widget=widget, barrier=barrier, is_toast=is_toast
            )
        )
        self.request_rebuild()
        return overlay_id

    def register_animation(self, ctrl: AnimationController) -> None:
        """Register an active animation controller on the frame clock.

        Binds the controller to this app (so it can later unregister itself) and
        starts the frame clock if it was idle. Registering an already-tracked
        controller is a no-op beyond (re)binding, so repeated
        :meth:`~tempestroid.animation.AnimationController.forward` calls are safe.

        Args:
            ctrl: The controller to drive on each frame.
        """
        ctrl.bind(self)
        self._animations.add(ctrl)
        if not self._tick_scheduled:
            self._tick_scheduled = True
            self._last_tick = self._now()
            self._loop().call_later(1.0 / 60.0, self._tick)

    def unregister_animation(self, ctrl: AnimationController) -> None:
        """Remove a controller from the frame clock.

        A no-op when the controller is not tracked (e.g. a double
        :meth:`~tempestroid.animation.AnimationController.stop`). The clock stops
        re-arming once the set drains.

        Args:
            ctrl: The controller to remove.
        """
        self._animations.discard(ctrl)

    def _tick(self) -> None:
        """Advance every active controller by the elapsed ``dt`` and rebuild.

        Computes ``dt`` from the injectable time source, advances each
        controller, drops the ones that report completion, and requests a single
        coalesced rebuild so the view re-reads the new ``value``s. Re-arms the
        loop timer only while controllers remain active.
        """
        self._tick_scheduled = False
        if not self._animations:
            return
        now = self._now()
        dt = now - self._last_tick
        self._last_tick = now
        for ctrl in list(self._animations):
            # ``App`` is the designated driver of a controller's per-frame step;
            # ``_advance`` is the clock-facing internal API (see the E3 contract).
            if ctrl._advance(dt):  # pyright: ignore[reportPrivateUsage]
                self._animations.discard(ctrl)
        self.request_rebuild()
        if self._animations:
            self._tick_scheduled = True
            self._loop().call_later(1.0 / 60.0, self._tick)

    def _tick_from_device(self) -> None:
        """Advance the frame clock once, driven by the device's ``__frame__``.

        The Compose host re-sends the reserved ``__frame__`` token every frame
        while an animation is active, so — unlike :meth:`_tick` — this advances
        the controllers once and never re-arms a loop timer itself (the host owns
        the cadence). It is the device-side analogue of one :meth:`_tick` frame.
        """
        if not self._animations:
            return
        now = self._now()
        dt = now - self._last_tick
        self._last_tick = now
        for ctrl in list(self._animations):
            # ``App`` is the designated driver of a controller's per-frame step;
            # ``_advance`` is the clock-facing internal API (see the E3 contract).
            if ctrl._advance(dt):  # pyright: ignore[reportPrivateUsage]
                self._animations.discard(ctrl)
        self.request_rebuild()

    def request_rebuild(self) -> None:
        """Schedule a single rebuild on the event loop.

        Repeated calls before the loop next runs are coalesced into one rebuild.
        """
        if self._rebuild_scheduled:
            return
        self._rebuild_scheduled = True
        self._loop().call_soon(self._rebuild)

    def _rebuild(self) -> None:
        """Rebuild the scene, diff against the current one, and apply patches."""
        self._rebuild_scheduled = False
        if self._current is None:
            return
        new = self._build()
        patches = diff_scene(self._current, new)
        self._current = new
        if patches:
            self._apply(patches)

    def _now(self) -> float:
        """Return the current animation-clock timestamp in seconds.

        Uses the injected ``time_source`` when set (deterministic in tests),
        otherwise the event loop's monotonic clock.

        Returns:
            The current time in seconds.
        """
        if self._time_source is not None:
            return self._time_source()
        return self._loop().time()

    @staticmethod
    def _loop() -> asyncio.AbstractEventLoop:
        """Return the loop to schedule on (running loop, else the policy loop).

        Returns:
            The asyncio event loop.
        """
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.get_event_loop()
