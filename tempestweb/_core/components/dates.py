"""Date/time components: ``Calendar`` (month grid) and ``Clock`` (digital).

``Calendar`` lays out a month as a grid of day buttons and reports the tapped ISO
date through ``on_select``. ``Clock`` renders a preformatted time string (the app
drives the tick from state, as in the ``stopwatch`` example). Both lower to
primitives.
"""

from __future__ import annotations

import calendar as _calendar
import datetime as _datetime
from collections.abc import Callable
from typing import Any

from pydantic import Field

from tempestweb._core.components.base import (
    ACCENT,
    MUTED,
    ON_MUTED,
    ON_SURFACE,
    SURFACE,
    merge_style,
)
from tempestweb._core.style import AlignItems, Edge, FontWeight, Style, TextAlign
from tempestweb._core.widgets import Button, Column, Component, Container, Row, Text, Widget

__all__ = ["Calendar", "Clock"]

_WEEKDAYS: tuple[str, ...] = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")


class Calendar(Component):
    """A month grid of selectable day cells.

    Attributes:
        month: The displayed month as ``"YYYY-MM"``; empty means the current
            month.
        selected: The selected day as ``"YYYY-MM-DD"`` (highlighted when it falls
            in the displayed month); empty means no selection.
        on_select: Called with the tapped day's ISO ``"YYYY-MM-DD"`` string.
    """

    month: str = Field(
        default="",
        description='The displayed month as ``"YYYY-MM"``; empty means the current '
        "month.",
    )
    selected: str = Field(
        default="",
        description='The selected day as ``"YYYY-MM-DD"`` (highlighted when it falls '
        "in the displayed month); empty means no selection.",
    )
    on_select: Callable[[str], Any] = Field(
        description='Called with the tapped day\'s ISO ``"YYYY-MM-DD"`` string.'
    )

    def _year_month(self) -> tuple[int, int]:
        """Resolve the displayed ``(year, month)``.

        Returns:
            The parsed ``month`` field, or today's year/month when it is empty.
        """
        if self.month:
            year, mon = self.month.split("-")
            return int(year), int(mon)
        today = _datetime.date.today()
        return today.year, today.month

    def _make_handler(self, iso: str) -> Callable[[], None]:
        """Build a zero-argument handler that selects ``iso``.

        Args:
            iso: The ISO date this handler reports.

        Returns:
            A click handler invoking ``on_select`` with ``iso``.
        """

        def handler() -> None:
            self.on_select(iso)

        return handler

    def _cell(self, year: int, mon: int, day: int, week_index: int, col: int) -> Widget:
        """Build one calendar cell (a day button, or a blank pad for ``day == 0``).

        Args:
            year: The displayed year.
            mon: The displayed month (1-12).
            day: The day number, or ``0`` for a padding cell.
            week_index: The row index of this cell (for keying pads).
            col: The column index of this cell (for keying pads).

        Returns:
            A day ``Button`` or an empty growing ``Container``.
        """
        if day == 0:
            return Container(key=f"pad-{week_index}-{col}", style=Style(grow=1.0))
        iso = f"{year:04d}-{mon:02d}-{day:02d}"
        selected = iso == self.selected
        return Button(
            label=str(day),
            on_click=self._make_handler(iso),
            key=f"day-{day}",
            style=Style(
                grow=1.0,
                padding=Edge.symmetric(vertical=10.0, horizontal=6.0),
                radius=8.0,
                background=ACCENT if selected else MUTED,
                color=ON_SURFACE,
            ),
        )

    def render(self) -> Widget:
        """Lower the calendar into a primitive month grid.

        Returns:
            A ``Column`` of a title, a weekday header row and one row per week.
        """
        year, mon = self._year_month()
        weeks = _calendar.Calendar().monthdayscalendar(year, mon)
        title = Text(
            content=f"{_calendar.month_name[mon]} {year}",
            style=Style(font_size=18.0, font_weight=FontWeight.BOLD, color=ON_SURFACE),
            key="calendar-title",
        )
        header = Row(
            style=Style(gap=6.0),
            children=[
                Text(
                    content=name,
                    style=Style(
                        grow=1.0,
                        font_size=12.0,
                        color=ON_MUTED,
                        text_align=TextAlign.CENTER,
                    ),
                    key=f"wd-{name}",
                )
                for name in _WEEKDAYS
            ],
            key="calendar-header",
        )
        rows = [
            Row(
                style=Style(gap=6.0),
                children=[
                    self._cell(year, mon, day, week_index, col)
                    for col, day in enumerate(week)
                ],
                key=f"week-{week_index}",
            )
            for week_index, week in enumerate(weeks)
        ]
        default = Style(gap=6.0, padding=Edge.all(12.0), background=SURFACE)
        return Column(
            key=self.key or "calendar",
            style=merge_style(default, self.style),
            children=[title, header, *rows],
        )


class Clock(Component):
    """A digital clock face rendering a preformatted time string.

    Attributes:
        time: The time text to display (e.g. ``"12:34:56"``); the app formats and
            ticks it from state.
        label: An optional caption shown muted under the time.
    """

    time: str = Field(
        default="",
        description='The time text to display (e.g. ``"12:34:56"``); the app formats '
        "and ticks it from state.",
    )
    label: str | None = Field(
        default=None, description="An optional caption shown muted under the time."
    )

    def render(self) -> Widget:
        """Lower the clock into a centered primitive column.

        Returns:
            A ``Column`` with the time and, when set, the label.
        """
        children: list[Widget] = [
            Text(
                content=self.time,
                style=Style(
                    font_size=40.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                    text_align=TextAlign.CENTER,
                ),
                key="clock-time",
            )
        ]
        if self.label is not None:
            children.append(
                Text(
                    content=self.label,
                    style=Style(
                        font_size=14.0, color=ON_MUTED, text_align=TextAlign.CENTER
                    ),
                    key="clock-label",
                )
            )
        default = Style(
            gap=4.0,
            padding=Edge.all(16.0),
            align=AlignItems.CENTER,
            background=SURFACE,
        )
        return Column(
            key=self.key or "clock",
            style=merge_style(default, self.style),
            children=children,
        )
