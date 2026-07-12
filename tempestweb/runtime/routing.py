"""URL ↔ navigation-stack mapping for the browser router.

The client reports the browser URL as a ``navigate`` event and pushes the app's
top route back as a URL. tempest-core's :class:`~tempest_core.navigation.Route`
already carries typed ``params``; these helpers round-trip those params (and any
query string) through the URL so a deep link or a page reload reconstructs the
same route — not just its path.

- :func:`path_to_routes` parses a URL (``/shop/item?ref=home&page=2``) into the
  nav stack, attaching the parsed query string to the linked (top) route's
  ``params``.
- :func:`route_to_path` serializes a route back to a URL, encoding its ``params``
  as the query string.
- :func:`match_path` extracts path parameters from a ``:name`` pattern (e.g.
  ``/users/:id`` against ``/users/42`` -> ``{"id": "42"}``).

Query/path values are strings (that is all a URL carries); richer typing is the
app's job after it reads ``app.nav.top.params``.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit

from tempest_core import Route
from tempest_core.navigation import routes_from_path

__all__ = ["match_path", "path_to_routes", "route_to_path"]


def path_to_routes(url: str) -> list[Route]:
    """Resolve a URL (path + optional query) into a navigation stack.

    The path builds the cumulative back stack (via
    :func:`~tempest_core.navigation.routes_from_path`); the query string, when
    present, is parsed into the **top** route's ``params`` so the linked screen
    receives them.

    Args:
        url: The browser URL, e.g. ``"/shop/item?ref=home"`` or ``"/"``.

    Returns:
        A non-empty list of routes from the root to the linked screen; the top
        route carries the parsed query params (empty when there is no query).
    """
    parts = urlsplit(url)
    routes = routes_from_path(parts.path)
    query = dict(parse_qsl(parts.query))
    if query:
        top = routes[-1]
        routes[-1] = Route(name=top.name, params={**top.params, **query})
    return routes


def route_to_path(route: Route) -> str:
    """Serialize a route to a URL path, encoding ``params`` as the query string.

    Args:
        route: The route to serialize (typically ``app.nav.top``).

    Returns:
        ``route.name`` when it has no params, else ``name?k=v&...`` with the
        params URL-encoded (values coerced to ``str``).
    """
    if not route.params:
        return route.name
    query = urlencode({key: str(value) for key, value in route.params.items()})
    return f"{route.name}?{query}"


def match_path(pattern: str, path: str) -> dict[str, str] | None:
    """Extract path parameters from a ``:name`` pattern, or ``None`` on mismatch.

    Segment counts must match; a ``:name`` segment captures the corresponding
    path segment, a literal segment must be equal. Example: ``match_path(
    "/users/:id", "/users/42")`` -> ``{"id": "42"}``; ``match_path("/users/:id",
    "/posts/42")`` -> ``None``.

    Args:
        pattern: The route pattern with ``:name`` placeholders.
        path: The concrete path to match (query string, if any, is ignored).

    Returns:
        A mapping of placeholder name to captured segment, or ``None`` when the
        path does not match the pattern.
    """
    pattern_segments = [seg for seg in pattern.split("/") if seg]
    path_segments = [seg for seg in urlsplit(path).path.split("/") if seg]
    if len(pattern_segments) != len(path_segments):
        return None
    params: dict[str, str] = {}
    for pattern_seg, path_seg in zip(pattern_segments, path_segments, strict=True):
        if pattern_seg.startswith(":"):
            params[pattern_seg[1:]] = path_seg
        elif pattern_seg != path_seg:
            return None
    return params
