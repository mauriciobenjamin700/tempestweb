"""Composite, higher-level UI components built from primitive widgets.

Each component is a :class:`tempestroid.widgets.Component` that lowers to a
primitive ``Text`` / ``Row`` / ``Column`` / ``Container`` tree via its ``render``
method, so it works in both renderers (Qt and Compose) with no renderer changes
and is fully device-ready. The package collects reusable page-structure and
navigation building blocks:

* :class:`AppBar` — top bar with leading widget, title and trailing actions.
* :class:`Header` / :class:`Footer` — page header band and bottom bar.
* :class:`Sidebar` — fixed-width lateral column.
* :class:`Scaffold` — page frame stacking app bar, body and bottom bar.
* :class:`NavBar` — selectable navigation/tab bar with an active index.
* Brazilian form inputs — :class:`EmailInput`, :class:`PasswordInput`,
  :class:`PhoneInput`, :class:`CPFInput`, :class:`CNPJInput` and the grouped
  :class:`AddressInput` (pair them with :mod:`tempestroid.validators`).
* Media pickers — :class:`ImagePicker`, :class:`DocumentPicker` and the circular
  :class:`ImagePicture` profile-photo picker.

The default theme tokens and :func:`merge_style` (used to overlay a caller's
``style`` onto a component default) are re-exported for building custom
components in the same idiom.
"""

from __future__ import annotations

from tempestweb._core.components.bars import (
    AppBar,
    CollapsingAppBar,
    Footer,
    Header,
)
from tempestweb._core.components.base import (
    ACCENT,
    BACKGROUND,
    MUTED,
    ON_MUTED,
    ON_SURFACE,
    SURFACE,
    merge_style,
)
from tempestweb._core.components.brforms import (
    AddressInput,
    CNPJInput,
    CPFInput,
    EmailInput,
    PasswordInput,
    PhoneInput,
)
from tempestweb._core.components.cards import Avatar, Card, Divider, ListTile
from tempestweb._core.components.dates import Calendar, Clock
from tempestweb._core.components.disclosure import Accordion
from tempestweb._core.components.feedback import Badge, Banner, EmptyState
from tempestweb._core.components.fields import SearchBar, Stepper
from tempestweb._core.components.layout import Grid, Scaffold, Sidebar
from tempestweb._core.components.mediainputs import (
    DocumentPicker,
    ImagePicker,
    ImagePicture,
)
from tempestweb._core.components.menu import Burger, Drawer
from tempestweb._core.components.navigation import Breadcrumb, NavBar
from tempestweb._core.components.selection import (
    Chip,
    RadioGroup,
    Rating,
    SegmentedControl,
)
from tempestweb._core.components.table import DataTable, Table, TableCell, TableRow

__all__ = [
    "AppBar",
    "CollapsingAppBar",
    "Header",
    "Footer",
    "Sidebar",
    "Scaffold",
    "Grid",
    "NavBar",
    "Breadcrumb",
    "Burger",
    "Drawer",
    "Calendar",
    "Clock",
    "Card",
    "ListTile",
    "Avatar",
    "Divider",
    "SegmentedControl",
    "RadioGroup",
    "Chip",
    "Rating",
    "Stepper",
    "SearchBar",
    "EmailInput",
    "PasswordInput",
    "PhoneInput",
    "CPFInput",
    "CNPJInput",
    "AddressInput",
    "ImagePicker",
    "DocumentPicker",
    "ImagePicture",
    "Accordion",
    "Banner",
    "EmptyState",
    "Badge",
    "Table",
    "DataTable",
    "TableCell",
    "TableRow",
    "merge_style",
    "BACKGROUND",
    "SURFACE",
    "ACCENT",
    "MUTED",
    "ON_SURFACE",
    "ON_MUTED",
]
