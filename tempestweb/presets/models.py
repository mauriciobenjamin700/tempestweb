"""The small typed records a preset takes instead of a widget tree.

A preset's whole promise is that you describe *what* is on the screen and it
decides *how* it looks. These dataclasses are the "what": a nav entry, a KPI, a
dashboard section, a table column, a form field. They hold data and, where a
cell or a field needs one, a ready widget — never a callback into the layout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from tempest_core import Widget

__all__ = [
    "Align",
    "FormField",
    "FormSection",
    "Kpi",
    "NavItem",
    "Section",
    "Span",
    "TableColumn",
    "Tone",
]

#: Horizontal alignment of a table column's cells.
Align = Literal["start", "center", "end"]

#: Whether a grid item takes its natural track or the full row.
Span = Literal["auto", "full"]

#: The semantic colour of a KPI's delta, mirroring the core's badge tones.
Tone = Literal["neutral", "success", "warning", "danger"]


@dataclass(frozen=True, slots=True)
class NavItem:
    """One entry in the admin shell's sidebar.

    Attributes:
        label: The text shown in the sidebar.
        value: The value handed to ``on_navigate`` when the entry is chosen, and
            compared against the shell's ``active`` to mark the current entry.
        badge: Optional short text rendered as a trailing badge (``"3"``,
            ``"novo"``); ``None`` renders no badge.
    """

    label: str
    value: str
    badge: str | None = None


@dataclass(frozen=True, slots=True)
class Kpi:
    """A single headline number on a dashboard.

    Attributes:
        label: What the number measures ("Receita", "Churn").
        value: The number, already formatted for display ("R$ 82k", "1,8%").
            Presets never format numbers: locale and currency are the app's call.
        delta: Optional change indicator shown next to the value ("+12%").
        up: Whether ``delta`` is an increase. Drives the arrow direction only —
            whether up is *good* is the app's business, expressed via ``tone``.
        tone: The delta's semantic colour.
    """

    label: str
    value: str
    delta: str | None = None
    up: bool = True
    tone: Tone = "neutral"


@dataclass(frozen=True, slots=True)
class Section:
    """A titled block of a dashboard, rendered as a card in the section grid.

    Attributes:
        title: The section heading.
        body: The section's content — a chart, a table, any widget.
        subtitle: Optional supporting line under the heading.
        span: ``"auto"`` lets the section share a row; ``"full"`` makes it take
            the whole row (a wide chart, a table).
    """

    title: str
    body: Widget
    subtitle: str | None = None
    span: Span = "auto"


@dataclass(frozen=True, slots=True)
class TableColumn:
    """One column of a list page's table.

    Attributes:
        label: The header text.
        align: How the column's cells are aligned. Numbers usually read better
            as ``"end"``.
    """

    label: str
    align: Align = "start"


@dataclass(frozen=True, slots=True)
class FormField:
    """One labelled control in a form page.

    Attributes:
        label: The field's label.
        control: The input widget itself — any core/tempestweb field. The preset
            positions it; it never builds or validates it.
        help: Optional hint shown under the control.
        error: Optional validation message, shown instead of ``help`` when set.
        span: ``"full"`` makes the field take the whole row (a textarea, an
            address); ``"auto"`` lets it share the row with its neighbours.
    """

    label: str
    control: Widget
    help: str | None = None
    error: str | None = None
    span: Span = "auto"


@dataclass(frozen=True, slots=True)
class FormSection:
    """A group of related fields under one heading.

    Attributes:
        title: The group heading ("Dados da conta", "Notificações").
        fields: The fields in the group, laid out in the responsive form grid.
        subtitle: Optional line under the heading explaining the group.
    """

    title: str
    fields: list[FormField] = field(default_factory=list)
    subtitle: str | None = None
