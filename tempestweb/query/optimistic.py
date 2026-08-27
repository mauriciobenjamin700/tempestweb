"""Applying a change to a cached list before the server has agreed to it.

Two operations cover almost every optimistic mutation: put a row in (creating it
or replacing it), and take a row out. Both return a **new** tuple — the cached
value is never mutated in place, which is what makes the rollback in
:class:`~tempestweb.query.QueryCache` able to restore exactly what was there.

Example:
    >>> rows = ({"id": 1, "name": "Ana"}, {"id": 2, "name": "Bia"})
    >>> upsert_by_id(rows, {"id": 2, "name": "Beatriz"})[1]
    {'id': 2, 'name': 'Beatriz'}
    >>> upsert_by_id(rows, {"id": 3, "name": "Caio"})[-1]
    {'id': 3, 'name': 'Caio'}
    >>> len(remove_by_id(rows, 1))
    1

An upsert of a row that is not there **appends** it, and keeps the position of
every row that is — replacing in place rather than moving the edited row to the
end, because a list that reorders itself when you rename something reads as a
bug to whoever is looking at it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

__all__ = [
    "ID_FIELD",
    "upsert_by_id",
    "remove_by_id",
    "replace_where",
]

#: The field an identified row is matched on.
ID_FIELD = "id"


def upsert_by_id(
    rows: Iterable[object],
    row: object,
    *,
    id_field: str = ID_FIELD,
) -> tuple[object, ...]:
    """Replace a row with the same id, or append it when there is none.

    Args:
        rows: The rows currently cached.
        row: The row to put in.
        id_field: The field the rows are identified by.

    Returns:
        A new tuple. The replaced row keeps its position; a new row goes last.
        When ``row`` carries no id, it is appended — an unidentified row cannot
        replace anything, and dropping it silently would lose the user's edit.
    """
    identifier = _identifier(row, id_field)
    if identifier is None:
        return (*rows, row)

    result: list[object] = []
    replaced = False
    for existing in rows:
        found = _identifier(existing, id_field)
        if not replaced and found is not None and found == identifier:
            result.append(row)
            replaced = True
        else:
            result.append(existing)
    if not replaced:
        result.append(row)
    return tuple(result)


def remove_by_id(
    rows: Iterable[object],
    identifier: object,
    *,
    id_field: str = ID_FIELD,
) -> tuple[object, ...]:
    """Drop every row carrying an id.

    Args:
        rows: The rows currently cached.
        identifier: The id to drop.
        id_field: The field the rows are identified by.

    Returns:
        A new tuple without those rows. Removing an id that is not there is not
        an error — it answers the same rows back, which is what a double-click on
        Delete should do.
    """
    return tuple(
        row
        for row in rows
        if (found := _identifier(row, id_field)) is None or found != identifier
    )


def replace_where(
    rows: Iterable[object],
    matches: object,
    row: object,
) -> tuple[object, ...]:
    """Replace every row a predicate accepts.

    For the cases ``upsert_by_id`` does not cover — a composite key, a row
    identified by something other than a field.

    Args:
        rows: The rows currently cached.
        matches: A callable answering whether a row should be replaced.
        row: The replacement.

    Returns:
        A new tuple.

    Raises:
        TypeError: If ``matches`` is not callable.
    """
    if not callable(matches):
        raise TypeError("replace_where needs a callable predicate")
    return tuple(row if matches(existing) else existing for existing in rows)


def _identifier(row: object, id_field: str) -> object | None:
    """Read a row's id, whether it is a mapping or an object.

    Args:
        row: The row to read.
        id_field: The field the rows are identified by.

    Returns:
        The id, or ``None`` when the row carries none. A row with no id never
        matches another row with no id — two unidentified rows are two rows, so
        an upsert appends one instead of collapsing them, and a remove leaves
        both alone.
    """
    if isinstance(row, Mapping):
        return row.get(id_field)
    return getattr(row, id_field, None)
