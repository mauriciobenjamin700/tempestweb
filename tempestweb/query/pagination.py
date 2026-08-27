"""The two shapes a paginated endpoint answers in, typed.

Offset pagination (``page`` + ``total``) can jump to page 7 and show "of 12".
Cursor pagination (``next_cursor``) cannot, and in exchange it does not skip or
repeat rows when the underlying list changes between pages. An app usually meets
both, from different endpoints, in the same screen.

Example:
    >>> page = offset_page({"items": [1, 2], "total": 5, "page": 1, "page_size": 2})
    >>> page.items, page.pages, page.has_next
    ((1, 2), 3, True)
    >>> cursor_page({"items": [1], "next_cursor": "abc"}).has_next
    True

Both are frozen: a page is an answer the server gave, not a mutable buffer.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

__all__ = [
    "OffsetPage",
    "CursorPage",
    "offset_page",
    "cursor_page",
    "empty_offset_page",
    "empty_cursor_page",
    "is_offset_page",
    "is_cursor_page",
    "ITEMS_KEY",
    "TOTAL_KEY",
    "PAGE_KEY",
    "PAGE_SIZE_KEY",
    "CURSOR_KEY",
    "PageKeys",
    "DEFAULT_PAGE_KEYS",
]

#: The payload key holding the rows.
ITEMS_KEY = "items"

#: The payload key holding how many rows exist across every page.
TOTAL_KEY = "total"

#: The payload key holding the 1-based page number.
PAGE_KEY = "page"

#: The payload key holding how many rows a full page holds.
PAGE_SIZE_KEY = "page_size"

#: The payload key holding the cursor for the next page, ``null`` on the last.
CURSOR_KEY = "next_cursor"


@dataclass(frozen=True)
class OffsetPage:
    """One page of an offset-paginated answer.

    Attributes:
        items: The rows on this page.
        total: How many rows exist across every page.
        page: This page's 1-based number.
        page_size: How many rows a full page holds.
    """

    items: tuple[object, ...] = ()
    total: int = 0
    page: int = 1
    page_size: int = 0

    @property
    def pages(self) -> int:
        """How many pages the total spans.

        Returns:
            The page count, or ``0`` when the page size is unknown — dividing by
            it would raise, and a screen asking "how many pages" before the first
            answer arrives is normal, not exceptional.
        """
        if self.page_size <= 0:
            return 0
        return -(-self.total // self.page_size)

    @property
    def has_next(self) -> bool:
        """Whether a page follows this one.

        Returns:
            Whether :attr:`page` is below :attr:`pages`.
        """
        return self.page < self.pages

    @property
    def has_previous(self) -> bool:
        """Whether a page precedes this one.

        Returns:
            Whether :attr:`page` is above the first.
        """
        return self.page > 1


@dataclass(frozen=True)
class CursorPage:
    """One page of a cursor-paginated answer.

    Attributes:
        items: The rows on this page.
        next_cursor: The cursor to ask for the next page, or ``None`` when this
            is the last one.
    """

    items: tuple[object, ...] = ()
    next_cursor: str | None = None

    @property
    def has_next(self) -> bool:
        """Whether a page follows this one.

        Returns:
            Whether a cursor was handed back.
        """
        return self.next_cursor is not None


@dataclass(frozen=True)
class PageKeys:
    """Which payload keys to read, for a server naming them differently.

    Attributes:
        items: The key holding the rows.
        total: The key holding the overall count.
        page: The key holding the page number.
        page_size: The key holding the page size.
        cursor: The key holding the next cursor.
    """

    items: str = ITEMS_KEY
    total: str = TOTAL_KEY
    page: str = PAGE_KEY
    page_size: str = PAGE_SIZE_KEY
    cursor: str = CURSOR_KEY


#: The payload keys used when the caller does not say otherwise.
DEFAULT_PAGE_KEYS = PageKeys()


def offset_page(
    payload: Mapping[str, object],
    *,
    page_keys: PageKeys = DEFAULT_PAGE_KEYS,
) -> OffsetPage:
    """Read an offset-paginated payload.

    Args:
        payload: The decoded JSON body.
        page_keys: Which keys to read, for a server naming them differently.

    Returns:
        The :class:`OffsetPage`. Missing or wrongly-typed keys fall back to the
        dataclass defaults rather than raising — a listing that renders empty is
        recoverable; a screen that raised on the way to rendering is not.
    """
    return OffsetPage(
        items=_items(payload.get(page_keys.items)),
        total=_int(payload.get(page_keys.total), 0),
        page=_int(payload.get(page_keys.page), 1),
        page_size=_int(payload.get(page_keys.page_size), 0),
    )


def cursor_page(
    payload: Mapping[str, object],
    *,
    page_keys: PageKeys = DEFAULT_PAGE_KEYS,
) -> CursorPage:
    """Read a cursor-paginated payload.

    Args:
        payload: The decoded JSON body.
        page_keys: Which keys to read, for a server naming them differently.

    Returns:
        The :class:`CursorPage`.
    """
    cursor = payload.get(page_keys.cursor)
    return CursorPage(
        items=_items(payload.get(page_keys.items)),
        next_cursor=cursor if isinstance(cursor, str) and cursor else None,
    )


def empty_offset_page(*, page: int = 1, page_size: int = 0) -> OffsetPage:
    """An offset page with no rows, for the state before the first answer.

    Args:
        page: The page number the screen is on.
        page_size: The page size the screen asked for.

    Returns:
        The empty page. Preferred over ``None`` in state: a view reading
        ``page.items`` never has to check first.
    """
    return OffsetPage(page=page, page_size=page_size)


def empty_cursor_page() -> CursorPage:
    """A cursor page with no rows, for the state before the first answer.

    Returns:
        The empty page.
    """
    return CursorPage()


def is_offset_page(
    payload: object,
    *,
    page_keys: PageKeys = DEFAULT_PAGE_KEYS,
) -> bool:
    """Report whether a payload looks offset-paginated.

    Args:
        payload: The decoded JSON body.
        page_keys: Which keys identify the shape.

    Returns:
        Whether it carries both the rows key and the total key.
    """
    return (
        isinstance(payload, Mapping)
        and page_keys.items in payload
        and page_keys.total in payload
    )


def is_cursor_page(
    payload: object,
    *,
    page_keys: PageKeys = DEFAULT_PAGE_KEYS,
) -> bool:
    """Report whether a payload looks cursor-paginated.

    Args:
        payload: The decoded JSON body.
        page_keys: Which keys identify the shape.

    Returns:
        Whether it carries both the rows key and the cursor key. The cursor key
        being present with a ``null`` value still counts — that is how the last
        page announces itself.
    """
    return (
        isinstance(payload, Mapping)
        and page_keys.items in payload
        and page_keys.cursor in payload
    )


def _items(value: object) -> tuple[object, ...]:
    """Read the rows out of a payload value.

    Args:
        value: The raw value under the items key.

    Returns:
        The rows, or an empty tuple when the value is not a list.
    """
    return tuple(value) if isinstance(value, list) else ()


def _int(value: object, default: int) -> int:
    """Read an integer out of a payload value.

    ``bool`` is excluded on purpose: it is an ``int`` in Python, and a
    ``"total": true`` would otherwise become a total of 1.

    Args:
        value: The raw value.
        default: What to answer when the value is not a usable number.

    Returns:
        The integer.
    """
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return default
