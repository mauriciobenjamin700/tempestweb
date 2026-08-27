"""Hierarchical cache keys, so invalidation can happen by prefix.

A flat string key (``"users-page-1"``) works right up to the first mutation.
Then you need "throw away everything about users" and there is nothing to ask —
you either keep a second registry of which keys mean users, or you invalidate
the whole cache. Both are the bug this module exists to avoid.

A key here is a tuple, so one key is a prefix of another by plain comparison:

Example:
    >>> users = keys("users")
    >>> users.all()
    ('users',)
    >>> users.list(page=1)
    ('users', 'list', 'page=1')
    >>> users.detail(7)
    ('users', 'detail', '7')
    >>> is_under(users.all(), users.list(page=1))
    True
    >>> is_under(users.list(page=1), users.all())
    False

Parameters are sorted before they join the key, so ``list(page=1, size=20)``
and ``list(size=20, page=1)`` are the **same** key — otherwise the same query
written two ways caches twice and the second write never invalidates the first.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "QueryKey",
    "QueryKeys",
    "keys",
    "is_under",
]

#: A cache key: a tuple of segments, coarsest first. Being a tuple is what makes
#: prefix invalidation a slice comparison instead of a string convention.
QueryKey = tuple[str, ...]


@dataclass(frozen=True)
class QueryKeys:
    """A key factory rooted at one resource.

    Attributes:
        root: The segments every key from this factory starts with.
    """

    root: QueryKey

    def all(self) -> QueryKey:
        """The root key, which is a prefix of every other key from here.

        Returns:
            The root segments — pass this to
            :meth:`~tempestweb.query.QueryCache.invalidate` to reach everything
            about this resource.
        """
        return self.root

    def list(self, **params: object) -> QueryKey:
        """A key for a listing, parameterized.

        Args:
            **params: Query parameters — page, filters, sort. Sorted by name
                before joining, so argument order never splits the cache.

        Returns:
            The key, under :meth:`all`.
        """
        return (*self.root, "list", *_params(params))

    def detail(self, identifier: object, **params: object) -> QueryKey:
        """A key for a single record.

        Args:
            identifier: The record's id, rendered with ``str``.
            **params: Any extra parameters, sorted as in :meth:`list`.

        Returns:
            The key, under :meth:`all`.
        """
        return (*self.root, "detail", str(identifier), *_params(params))

    def sub(self, *segments: object, **params: object) -> QueryKey:
        """A key for anything the other two do not name.

        Args:
            *segments: Extra segments, rendered with ``str``.
            **params: Any parameters, sorted as in :meth:`list`.

        Returns:
            The key, under :meth:`all`.
        """
        return (*self.root, *(str(part) for part in segments), *_params(params))


def keys(*segments: str) -> QueryKeys:
    """Root a key factory at a resource.

    Args:
        *segments: The root segments, coarsest first — ``keys("admin", "users")``
            makes ``("admin", "users")`` invalidatable as one unit.

    Returns:
        The :class:`QueryKeys` factory.
    """
    return QueryKeys(tuple(segments))


def is_under(prefix: QueryKey, key: QueryKey) -> bool:
    """Report whether a key lives under a prefix.

    Segment-wise, never character-wise: ``("users",)`` is a prefix of
    ``("users", "list")`` and is **not** a prefix of ``("users-archive",)``.
    A ``startswith`` on joined strings would get that second one wrong, and it
    would get it wrong silently — invalidating a resource that merely shares a
    name.

    Args:
        prefix: The prefix to test against.
        key: The key to test.

    Returns:
        Whether ``key`` starts with ``prefix``. The empty prefix matches
        everything, which is how "invalidate the whole cache" is spelled.
    """
    return key[: len(prefix)] == prefix


def _params(params: dict[str, object]) -> QueryKey:
    """Render query parameters as sorted key segments.

    Args:
        params: The parameters to render.

    Returns:
        One ``name=value`` segment per parameter, sorted by name.
    """
    return tuple(f"{name}={params[name]}" for name in sorted(params))
