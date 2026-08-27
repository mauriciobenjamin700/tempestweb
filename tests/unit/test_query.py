"""The read side: staleness, prefix invalidation, rollback, and the two pages.

The case this module exists for is `test_invalidate_reaches_every_key_under_the_prefix`
and its negative twin `test_a_prefix_is_segment_wise_not_character_wise`. Prefix
invalidation done with `startswith` on a joined string quietly invalidates a
resource that merely shares a name, and nothing about that failure is visible
until a screen shows the wrong thing.

The rollback tests are the other half. The issue's own example undid a refused
mutation by invalidating — which is a round-trip to the network, not an undo, and
does nothing offline. `patch` hands back a rollback that restores the exact
entries it replaced, and `test_rollback_restores_what_was_there` fixes that.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

from tempestweb.query import (
    CACHE_TIME_MS,
    MAX_QUERY_ATTEMPTS,
    STALE_TIME_MS,
    CursorPage,
    OffsetPage,
    PageKeys,
    QueryCache,
    cursor_page,
    empty_cursor_page,
    empty_offset_page,
    is_cursor_page,
    is_offset_page,
    is_under,
    keys,
    offset_page,
    persist,
    remove_by_id,
    replace_where,
    restore,
    should_retry_query,
    upsert_by_id,
)

USERS = keys("users")


class Clock:
    """A clock a test moves by hand, in milliseconds."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, ms: float) -> None:
        self.now += ms


@dataclass
class Loader:
    """A loader counting how many times it actually ran."""

    value: object = "v1"
    calls: int = 0
    delay: float = 0.0
    fail_with: Exception | None = None

    async def __call__(self) -> object:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail_with is not None:
            raise self.fail_with
        return self.value


@dataclass
class FakeStorage:
    """A dictionary standing in for ``native.storage``."""

    data: dict[str, str] = field(default_factory=dict)
    fail_on_get: set[str] = field(default_factory=set)

    async def put(self, name: str, content: str) -> None:
        self.data[name] = content

    async def get(self, name: str) -> str:
        if name in self.fail_on_get:
            raise RuntimeError("not_found")
        return self.data[name]

    async def remove(self, name: str) -> None:
        self.data.pop(name, None)

    async def list_keys(self) -> list[str]:
        return list(self.data)


def _cache(clock: Clock | None = None, **kwargs: float) -> QueryCache:
    """Build a cache on a hand-driven clock."""
    return QueryCache(clock=clock or Clock(), **kwargs)


# --------------------------------------------------------------------------
# Keys and prefixes
# --------------------------------------------------------------------------


def test_keys_are_hierarchical() -> None:
    assert USERS.all() == ("users",)
    assert USERS.list(page=1) == ("users", "list", "page=1")
    assert USERS.detail(7) == ("users", "detail", "7")
    assert USERS.sub("stats") == ("users", "stats")


def test_parameter_order_does_not_split_the_cache() -> None:
    """The same query written two ways must be one key, or writes never meet."""
    assert USERS.list(page=1, size=20) == USERS.list(size=20, page=1)


def test_a_prefix_is_segment_wise_not_character_wise() -> None:
    """`startswith` on joined strings gets this wrong, and gets it wrong quietly."""
    assert is_under(("users",), ("users", "list"))
    assert not is_under(("users",), ("users-archive",))
    assert not is_under(("users", "list"), ("users",))
    assert is_under((), ("anything",))


# --------------------------------------------------------------------------
# Staleness — hit and miss
# --------------------------------------------------------------------------


async def test_a_fresh_entry_is_answered_without_running_the_loader() -> None:
    clock = Clock()
    cache = _cache(clock)
    loader = Loader()

    assert await cache.fetch(USERS.all(), loader) == "v1"
    assert await cache.fetch(USERS.all(), loader) == "v1"
    assert loader.calls == 1


async def test_an_entry_past_the_window_is_loaded_again() -> None:
    clock = Clock()
    cache = _cache(clock, stale_ms=1000.0)
    loader = Loader()

    await cache.fetch(USERS.all(), loader)
    clock.advance(1000.0)
    await cache.fetch(USERS.all(), loader)

    assert loader.calls == 2


async def test_the_window_can_be_overridden_per_read() -> None:
    clock = Clock()
    cache = _cache(clock, stale_ms=100_000.0)
    loader = Loader()

    await cache.fetch(USERS.all(), loader)
    clock.advance(500.0)
    await cache.fetch(USERS.all(), loader, stale_ms=100.0)

    assert loader.calls == 2


async def test_force_skips_the_freshness_check() -> None:
    cache = _cache()
    loader = Loader()

    await cache.fetch(USERS.all(), loader)
    await cache.fetch(USERS.all(), loader, force=True)

    assert loader.calls == 2


async def test_is_stale_reports_before_anything_is_cached() -> None:
    clock = Clock()
    cache = _cache(clock, stale_ms=1000.0)

    assert cache.is_stale(USERS.all())
    await cache.fetch(USERS.all(), Loader())
    assert not cache.is_stale(USERS.all())
    clock.advance(1000.0)
    assert cache.is_stale(USERS.all())


async def test_an_entry_past_the_cache_window_is_dropped_entirely() -> None:
    clock = Clock()
    cache = _cache(clock, stale_ms=100.0, cache_ms=1000.0)

    await cache.fetch(USERS.all(), Loader())
    clock.advance(999.0)
    assert cache.get(USERS.all()) == "v1"
    clock.advance(1.0)
    assert cache.get(USERS.all()) is None


# --------------------------------------------------------------------------
# Single-flight
# --------------------------------------------------------------------------


async def test_concurrent_reads_of_one_key_share_a_single_load() -> None:
    cache = _cache()
    loader = Loader(delay=0.01)

    results = await asyncio.gather(
        cache.fetch(USERS.all(), loader),
        cache.fetch(USERS.all(), loader),
        cache.fetch(USERS.all(), loader),
    )

    assert results == ["v1", "v1", "v1"]
    assert loader.calls == 1


async def test_concurrent_reads_of_different_keys_do_not_share() -> None:
    cache = _cache()
    one = Loader(value="a", delay=0.01)
    two = Loader(value="b", delay=0.01)

    assert await asyncio.gather(
        cache.fetch(USERS.detail(1), one),
        cache.fetch(USERS.detail(2), two),
    ) == ["a", "b"]
    assert (one.calls, two.calls) == (1, 1)


async def test_a_failed_load_reaches_every_sharer_and_keeps_the_old_value() -> None:
    cache = _cache()
    await cache.fetch(USERS.all(), Loader(value="good"))

    boom = Loader(delay=0.01, fail_with=RuntimeError("network down"))
    with pytest.raises(RuntimeError, match="network down"):
        await asyncio.gather(
            cache.fetch(USERS.all(), boom, force=True),
            cache.fetch(USERS.all(), boom, force=True),
        )

    assert boom.calls == 1
    assert cache.get(USERS.all()) == "good"


async def test_a_load_that_fails_can_be_retried() -> None:
    """The in-flight slot must be released, or the key is poisoned forever."""
    cache = _cache()
    with pytest.raises(RuntimeError):
        await cache.fetch(USERS.all(), Loader(fail_with=RuntimeError("boom")))

    assert await cache.fetch(USERS.all(), Loader(value="second")) == "second"


# --------------------------------------------------------------------------
# Invalidation by prefix — the case that goes wrong by hand
# --------------------------------------------------------------------------


async def test_invalidate_reaches_every_key_under_the_prefix() -> None:
    clock = Clock()
    cache = _cache(clock, stale_ms=1000.0)
    for key in (USERS.list(page=1), USERS.list(page=2), USERS.detail(7)):
        await cache.fetch(key, Loader())

    assert cache.invalidate(USERS.all()) == 3

    assert cache.is_stale(USERS.list(page=1))
    assert cache.is_stale(USERS.list(page=2))
    assert cache.is_stale(USERS.detail(7))


async def test_invalidate_keeps_the_values_on_screen() -> None:
    """Stale is not empty: the last good answer stays while the refetch runs."""
    cache = _cache(stale_ms=1000.0)
    await cache.fetch(USERS.list(page=1), Loader(value="rows"))

    cache.invalidate(USERS.all())

    assert cache.get(USERS.list(page=1)) == "rows"
    assert cache.is_stale(USERS.list(page=1))


async def test_invalidate_leaves_a_sibling_resource_alone() -> None:
    cache = _cache(stale_ms=1000.0)
    orders = keys("orders")
    await cache.fetch(USERS.list(), Loader())
    await cache.fetch(orders.list(), Loader())

    cache.invalidate(USERS.all())

    assert cache.is_stale(USERS.list())
    assert not cache.is_stale(orders.list())


async def test_drop_removes_instead_of_marking() -> None:
    cache = _cache()
    await cache.fetch(USERS.list(page=1), Loader())
    await cache.fetch(USERS.list(page=2), Loader())

    assert cache.drop(USERS.all()) == 2
    assert cache.get(USERS.list(page=1)) is None
    assert cache.keys == ()


async def test_the_empty_prefix_reaches_everything() -> None:
    cache = _cache()
    await cache.fetch(USERS.list(), Loader())
    await cache.fetch(keys("orders").list(), Loader())

    assert cache.drop(()) == 2


# --------------------------------------------------------------------------
# Optimistic patch and rollback
# --------------------------------------------------------------------------

ROWS = ({"id": 1, "name": "Ana"}, {"id": 2, "name": "Bia"})


async def test_patch_applies_to_every_entry_under_the_prefix() -> None:
    """A rename must reach page 2, not only the page the user was looking at."""
    cache = _cache()
    await cache.fetch(USERS.list(page=1), Loader(value=ROWS))
    await cache.fetch(USERS.list(page=2), Loader(value=ROWS))

    cache.patch(
        USERS.all(),
        lambda rows: upsert_by_id(rows, {"id": 2, "name": "Beatriz"}),  # type: ignore[arg-type]
    )

    for page in (1, 2):
        cached = cache.get(USERS.list(page=page))
        assert isinstance(cached, tuple)
        assert cached[1] == {"id": 2, "name": "Beatriz"}


async def test_rollback_restores_what_was_there() -> None:
    """The undo the issue's example lacked: no network, no refetch, exact."""
    cache = _cache()
    await cache.fetch(USERS.list(), Loader(value=ROWS))

    rollback = cache.patch(
        USERS.all(),
        lambda rows: upsert_by_id(rows, {"id": 2, "name": "Beatriz"}),  # type: ignore[arg-type]
    )
    rollback()

    assert cache.get(USERS.list()) == ROWS


async def test_rollback_is_idempotent() -> None:
    cache = _cache()
    await cache.fetch(USERS.list(), Loader(value=ROWS))
    rollback = cache.patch(USERS.all(), lambda rows: ())
    rollback()
    rollback()

    assert cache.get(USERS.list()) == ROWS


async def test_rollback_does_not_revive_a_freshness_change() -> None:
    """A patch keeps the entry's timestamp, so the undo cannot make it fresh."""
    clock = Clock()
    cache = _cache(clock, stale_ms=1000.0)
    await cache.fetch(USERS.list(), Loader(value=ROWS))
    clock.advance(1000.0)

    rollback = cache.patch(USERS.all(), lambda rows: ())
    rollback()

    assert cache.is_stale(USERS.list())


async def test_the_optimistic_block_rolls_back_when_the_body_raises() -> None:
    cache = _cache()
    await cache.fetch(USERS.list(), Loader(value=ROWS))

    with (
        pytest.raises(RuntimeError, match="server said no"),
        cache.optimistic(
            USERS.all(),
            lambda rows: remove_by_id(rows, 1),  # type: ignore[arg-type]
        ),
    ):
        raise RuntimeError("server said no")

    assert cache.get(USERS.list()) == ROWS


async def test_the_optimistic_block_keeps_the_change_when_the_body_succeeds() -> None:
    cache = _cache()
    await cache.fetch(USERS.list(), Loader(value=ROWS))

    with cache.optimistic(
        USERS.all(),
        lambda rows: remove_by_id(rows, 1),  # type: ignore[arg-type]
    ):
        pass

    cached = cache.get(USERS.list())
    assert isinstance(cached, tuple)
    assert len(cached) == 1


async def test_a_patch_that_raises_halfway_leaves_nothing_half_applied() -> None:
    """Two entries showing two different truths is worse than no change."""
    cache = _cache()
    await cache.fetch(USERS.list(page=1), Loader(value=ROWS))
    await cache.fetch(USERS.list(page=2), Loader(value="not a list"))

    def patcher(value: object) -> object:
        if not isinstance(value, tuple):
            raise TypeError("this entry is not a list of rows")
        return ()

    with pytest.raises(TypeError):
        cache.patch(USERS.all(), patcher)

    assert cache.get(USERS.list(page=1)) == ROWS
    assert cache.get(USERS.list(page=2)) == "not a list"


# --------------------------------------------------------------------------
# Optimistic helpers
# --------------------------------------------------------------------------


def test_upsert_replaces_in_place_and_appends_what_is_new() -> None:
    replaced = upsert_by_id(ROWS, {"id": 1, "name": "Ana Maria"})
    assert replaced[0] == {"id": 1, "name": "Ana Maria"}
    assert replaced[1] == ROWS[1]

    appended = upsert_by_id(ROWS, {"id": 3, "name": "Caio"})
    assert len(appended) == 3
    assert appended[-1]["id"] == 3  # type: ignore[index]


def test_a_row_with_no_id_is_appended_not_dropped() -> None:
    assert len(upsert_by_id(ROWS, {"name": "sem id"})) == 3


def test_two_rows_with_no_id_are_two_rows() -> None:
    rows = upsert_by_id(upsert_by_id((), {"name": "a"}), {"name": "b"})
    assert len(rows) == 2


def test_remove_is_a_no_op_for_an_id_that_is_not_there() -> None:
    assert remove_by_id(ROWS, 99) == ROWS


def test_remove_leaves_a_row_that_has_no_id_alone() -> None:
    assert remove_by_id(({"name": "x"},), None) == ({"name": "x"},)


def test_an_object_row_works_like_a_mapping_row() -> None:
    @dataclass(frozen=True)
    class Row:
        id: int
        name: str

    rows = (Row(1, "Ana"), Row(2, "Bia"))
    assert remove_by_id(rows, 1) == (Row(2, "Bia"),)
    assert upsert_by_id(rows, Row(2, "Beatriz"))[1] == Row(2, "Beatriz")


def test_replace_where_covers_what_the_id_helpers_do_not() -> None:
    rows = ({"a": 1, "b": 1}, {"a": 1, "b": 2})
    replaced = replace_where(rows, lambda row: row["b"] == 2, {"a": 9, "b": 9})  # type: ignore[index]
    assert replaced == ({"a": 1, "b": 1}, {"a": 9, "b": 9})


def test_replace_where_refuses_a_non_callable() -> None:
    with pytest.raises(TypeError):
        replace_where(ROWS, "not callable", {})


# --------------------------------------------------------------------------
# Pagination — both shapes
# --------------------------------------------------------------------------


def test_offset_page_reads_and_computes() -> None:
    page = offset_page({"items": [1, 2], "total": 5, "page": 2, "page_size": 2})

    assert page.items == (1, 2)
    assert page.pages == 3
    assert page.has_next
    assert page.has_previous


def test_the_last_offset_page_has_no_next() -> None:
    page = offset_page({"items": [5], "total": 5, "page": 3, "page_size": 2})
    assert not page.has_next
    assert page.has_previous


def test_an_offset_page_with_no_size_does_not_divide_by_zero() -> None:
    page = offset_page({"items": [], "total": 10})
    assert page.pages == 0
    assert not page.has_next


def test_cursor_page_reads_the_cursor() -> None:
    assert cursor_page({"items": [1], "next_cursor": "abc"}).has_next
    assert not cursor_page({"items": [1], "next_cursor": None}).has_next
    assert not cursor_page({"items": [1], "next_cursor": ""}).has_next


def test_a_malformed_page_renders_empty_instead_of_raising() -> None:
    page = offset_page({"items": "not a list", "total": "many"})
    assert page == OffsetPage(items=(), total=0, page=1, page_size=0)


def test_a_boolean_total_is_not_a_total_of_one() -> None:
    assert offset_page({"items": [], "total": True}).total == 0


def test_the_two_shapes_are_told_apart() -> None:
    offset = {"items": [], "total": 0}
    cursor = {"items": [], "next_cursor": None}

    assert is_offset_page(offset) and not is_cursor_page(offset)
    assert is_cursor_page(cursor) and not is_offset_page(cursor)
    assert not is_offset_page("not a page")


def test_page_keys_can_be_overridden_for_another_server() -> None:
    payload = {"results": [1], "count": 9, "pagina": 2, "tamanho": 3}
    page = offset_page(
        payload,
        page_keys=PageKeys(
            items="results", total="count", page="pagina", page_size="tamanho"
        ),
    )
    assert (page.items, page.total, page.page, page.pages) == ((1,), 9, 2, 3)


def test_the_empty_pages_are_safe_to_render() -> None:
    assert empty_offset_page(page=2, page_size=10) == OffsetPage(
        items=(), total=0, page=2, page_size=10
    )
    assert empty_cursor_page() == CursorPage()
    assert not empty_offset_page().has_next


# --------------------------------------------------------------------------
# Retry policy
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("attempt", "status", "expected"),
    [
        (1, None, True),
        (1, 503, True),
        (1, 429, True),
        (1, 404, False),
        (1, 403, False),
        (1, 200, False),
        (MAX_QUERY_ATTEMPTS, None, False),
        (MAX_QUERY_ATTEMPTS, 503, False),
    ],
)
def test_only_a_later_is_retried_and_only_so_many_times(
    attempt: int, status: int | None, expected: bool
) -> None:
    assert should_retry_query(attempt, status) is expected


def test_the_windows_are_ordered_so_a_stale_answer_survives_its_refetch() -> None:
    assert STALE_TIME_MS < CACHE_TIME_MS


# --------------------------------------------------------------------------
# Persistence — on the store the app already has
# --------------------------------------------------------------------------


async def test_a_cache_survives_a_reload() -> None:
    storage = FakeStorage()
    cache = _cache()
    await cache.fetch(USERS.list(page=1), Loader(value=[{"id": 1}]))
    await cache.fetch(USERS.detail(1), Loader(value={"id": 1}))

    assert (await persist(cache, storage)).written == 2

    revived = _cache()
    assert (await restore(revived, storage)).restored == 2
    assert revived.get(USERS.list(page=1)) == [{"id": 1}]
    assert revived.get(USERS.detail(1)) == {"id": 1}


async def test_an_unserializable_entry_is_skipped_not_fatal() -> None:
    storage = FakeStorage()
    cache = _cache()
    await cache.fetch(USERS.list(), Loader(value={"ok": 1}))
    await cache.fetch(USERS.detail(1), Loader(value=object()))

    result = await persist(cache, storage)

    assert (result.written, result.skipped) == (1, 1)
    assert len(storage.data) == 1


async def test_restore_ignores_keys_the_app_stored_for_something_else() -> None:
    storage = FakeStorage(data={"user-draft": "whatever"})
    cache = _cache()
    await cache.fetch(USERS.list(), Loader(value=[1]))
    await persist(cache, storage)

    revived = _cache()
    assert (await restore(revived, storage)).restored == 1
    assert storage.data["user-draft"] == "whatever"


async def test_a_record_that_no_longer_parses_is_discarded_not_replayed() -> None:
    storage = FakeStorage(data={'tw-query:["users"]': "{ not json"})
    cache = _cache()

    result = await restore(cache, storage)

    assert (result.restored, result.discarded) == (0, 1)
    assert storage.data == {}


async def test_a_record_that_cannot_be_read_is_discarded() -> None:
    storage = FakeStorage(
        data={'tw-query:["users"]': "{}"}, fail_on_get={'tw-query:["users"]'}
    )
    assert (await restore(_cache(), storage)).discarded == 1


async def test_restored_entries_land_fresh() -> None:
    """Reviving them stale would send the boot screen straight to the network."""
    clock = Clock()
    storage = FakeStorage()
    cache = _cache(clock, stale_ms=1000.0)
    await cache.fetch(USERS.list(), Loader(value=[1]))
    await persist(cache, storage)

    clock.advance(10_000.0)
    revived = QueryCache(clock=clock, stale_ms=1000.0)
    await restore(revived, storage)

    assert not revived.is_stale(USERS.list())


# --------------------------------------------------------------------------
# Observability
# --------------------------------------------------------------------------


async def test_a_listener_is_told_about_every_change() -> None:
    cache = _cache()
    seen: list[int] = []
    unsubscribe = cache.on_change(lambda: seen.append(1))

    await cache.fetch(USERS.list(), Loader())
    cache.invalidate(USERS.all())
    cache.drop(USERS.all())
    assert len(seen) == 3

    unsubscribe()
    await cache.fetch(USERS.list(), Loader())
    assert len(seen) == 3


def test_an_invalidate_that_matches_nothing_says_nothing() -> None:
    cache = _cache()
    seen: list[int] = []
    cache.on_change(lambda: seen.append(1))

    assert cache.invalidate(USERS.all()) == 0
    assert cache.drop(USERS.all()) == 0
    assert seen == []


# --------------------------------------------------------------------------
# Mode support — pinned, because the docs claim it
# --------------------------------------------------------------------------


def test_mode_c_refuses_the_import_with_a_named_error() -> None:
    from tempestweb.transpile import TranspileError, generate

    source = (
        "from dataclasses import dataclass, field\n"
        "from tempest_core import App, Column, Text, Widget\n"
        "from tempestweb.query import QueryCache\n"
        "@dataclass\n"
        "class State:\n"
        "    rows: list[str] = field(default_factory=list)\n"
        "def view(app: App[State]) -> Widget:\n"
        '    return Column(key="b", children=[Text(key="t", content="hi")])\n'
    )
    with pytest.raises(TranspileError) as caught:
        generate(source, filename="app.py")

    assert "tempestweb.query" in str(caught.value)
