"""Tests for the layout presets (``tempestweb.presets``).

A preset's contract has two halves: the widget tree it composes, and the layout
roles it stamps for ``client/layouts.js`` to style. These tests pin both — a
missing role is a screen that silently loses its responsive behaviour, which no
type checker catches.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tempest_core import Node, Text, Widget, build
from tempestweb.presets import (
    FormField,
    FormSection,
    Kpi,
    NavItem,
    Section,
    TableColumn,
    admin_shell,
    auth_page,
    dashboard_page,
    data_table,
    form_page,
    list_page,
    roles,
    settings_page,
)
from tempestweb.runtime.serialize import node_to_wire

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "presets_admin_shell.json"


def _roles(node: Node) -> list[str]:
    """Collect every layout role in a built tree, in document order.

    Args:
        node: The root of a built IR tree.

    Returns:
        The ``data-tw-layout`` values found, depth-first.
    """
    found: list[str] = []
    attrs = node.props.get("attrs") or {}
    role = attrs.get(roles.LAYOUT_ATTR)
    if role is not None:
        found.append(str(role))
    for child in node.children:
        found.extend(_roles(child))
    return found


def _find(node: Node, key: str) -> Node | None:
    """Find the first node with ``key`` in a built tree.

    Args:
        node: The root to search from.
        key: The widget key to look for.

    Returns:
        The matching node, or ``None``.
    """
    if node.key == key:
        return node
    for child in node.children:
        hit = _find(child, key)
        if hit is not None:
            return hit
    return None


def _text(widget: str = "x") -> Widget:
    """Build a throwaway widget to stand in for app content.

    Args:
        widget: The text content.

    Returns:
        A keyed :class:`~tempest_core.widgets.Text`.
    """
    return Text(content=widget, key=f"content-{widget}")


def test_admin_shell_emits_the_shell_roles() -> None:
    """The shell tags each region so the sheet can lay the grid out."""
    tree = build(
        admin_shell(
            title="Painel",
            nav=[NavItem("Visão geral", "overview")],
            active="overview",
            on_navigate=lambda _value: None,
            body=_text(),
            on_toggle_sidebar=lambda: None,
        )
    )
    found = _roles(tree)
    assert found[0] == roles.SHELL
    for role in (
        roles.SHELL_SIDEBAR,
        roles.SHELL_HEADER,
        roles.SHELL_MAIN,
        roles.SHELL_SCRIM,
        roles.NAV_ITEM,
    ):
        assert role in found, role


def test_admin_shell_marks_the_active_nav_entry() -> None:
    """The current entry carries data-tw-active so the highlight survives a rebuild."""
    tree = build(
        admin_shell(
            title="Painel",
            nav=[NavItem("Visão geral", "overview"), NavItem("Usuários", "users")],
            active="users",
            on_navigate=lambda _value: None,
            body=_text(),
        )
    )
    current = _find(tree, "tw-nav-users")
    other = _find(tree, "tw-nav-overview")
    assert current is not None and other is not None
    assert current.props["attrs"]["data-tw-active"] == "true"
    assert other.props["attrs"]["data-tw-active"] == "false"


def test_admin_shell_without_a_toggle_has_no_burger_or_scrim() -> None:
    """An app with no small-screen story gets neither control, not a dead one."""
    tree = build(
        admin_shell(
            title="Painel",
            nav=[NavItem("Visão geral", "overview")],
            active="overview",
            on_navigate=lambda _value: None,
            body=_text(),
        )
    )
    found = _roles(tree)
    assert roles.SHELL_SCRIM not in found
    assert roles.SHELL_BURGER not in found


def test_admin_shell_sidebar_mirrors_the_open_flag() -> None:
    """The overlay's state is data, so the sheet can react to it."""
    closed = build(
        admin_shell(
            title="P",
            nav=[],
            active="",
            on_navigate=lambda _v: None,
            body=_text(),
            on_toggle_sidebar=lambda: None,
        )
    )
    opened = build(
        admin_shell(
            title="P",
            nav=[],
            active="",
            on_navigate=lambda _v: None,
            body=_text(),
            sidebar_open=True,
            on_toggle_sidebar=lambda: None,
        )
    )
    closed_sidebar = _find(closed, "tw-shell-sidebar")
    opened_sidebar = _find(opened, "tw-shell-sidebar")
    assert closed_sidebar is not None and opened_sidebar is not None
    assert closed_sidebar.props["attrs"]["data-tw-open"] == "false"
    assert opened_sidebar.props["attrs"]["data-tw-open"] == "true"


def test_dashboard_page_grids_kpis_and_sections() -> None:
    """KPIs and sections each get their own reflowing grid."""
    tree = build(
        dashboard_page(
            title="Visão geral",
            kpis=[Kpi("Receita", "R$ 82k", delta="+12%", tone="success")],
            sections=[Section("Vendas", _text("chart"), span="full")],
        )
    )
    found = _roles(tree)
    assert found[0] == roles.PAGE
    assert roles.KPI_GRID in found
    assert roles.SECTION_GRID in found
    section = _find(tree, "tw-dashboard-sections-0")
    assert section is not None
    assert section.props["attrs"]["data-tw-span"] == "full"


def test_dashboard_page_omits_empty_regions() -> None:
    """No KPIs and no sections means no empty grids in the DOM."""
    found = _roles(build(dashboard_page(title="Vazio")))
    assert roles.KPI_GRID not in found
    assert roles.SECTION_GRID not in found


def test_data_table_tags_head_rows_and_cells() -> None:
    """The table's parts are tagged so the sheet owns sticky, zebra and scroll."""
    tree = build(
        data_table(
            columns=[TableColumn("Nome"), TableColumn("Saldo", align="end")],
            rows=[["Ana", "R$ 10"], ["Bo", "R$ 4"]],
        )
    )
    found = _roles(tree)
    assert found[0] == roles.TABLE_SCROLL
    assert found.count(roles.TABLE_ROW) == 2
    assert found.count(roles.TABLE_HEADER_CELL) == 2
    assert found.count(roles.TABLE_CELL) == 4
    aligned = _find(tree, "tw-table-th-1")
    assert aligned is not None
    assert aligned.props["attrs"]["data-tw-align"] == "end"


def test_data_table_accepts_widgets_as_cells() -> None:
    """A cell can be a widget (a badge, a row menu), not only text."""
    tree = build(data_table(columns=[TableColumn("Status")], rows=[[_text("badge")]]))
    assert _find(tree, "content-badge") is not None


def test_list_page_renders_an_empty_state_instead_of_an_empty_table() -> None:
    """No matches is a normal outcome, so it gets a designed screen."""
    tree = build(
        list_page(
            title="Usuários",
            columns=[TableColumn("Nome")],
            rows=[],
            empty_title="Nenhum usuário",
        )
    )
    found = _roles(tree)
    assert roles.TABLE not in found
    assert _find(tree, "tw-list-empty") is not None


def test_list_page_paginates_only_when_there_is_more_than_one_page() -> None:
    """A single page of results shows no pagination control."""
    single = build(
        list_page(
            title="U",
            columns=[TableColumn("Nome")],
            rows=[["Ana"]],
            page_count=1,
            on_page=lambda _page: None,
        )
    )
    many = build(
        list_page(
            title="U",
            columns=[TableColumn("Nome")],
            rows=[["Ana"]],
            page=2,
            page_count=5,
            on_page=lambda _page: None,
        )
    )
    assert _find(single, "tw-list-pagination") is None
    label = _find(many, "tw-list-pagination-label")
    assert label is not None
    assert label.props["content"] == "Página 2 de 5"


def test_list_page_pagination_clamps_at_the_ends() -> None:
    """Prev on page 1 and next on the last page stay inert instead of overflowing."""
    seen: list[int] = []
    tree = build(
        list_page(
            title="U",
            columns=[TableColumn("Nome")],
            rows=[["Ana"]],
            page=1,
            page_count=2,
            on_page=seen.append,
        )
    )
    prev = _find(tree, "tw-list-pagination-prev")
    nxt = _find(tree, "tw-list-pagination-next")
    assert prev is not None and nxt is not None
    prev.props["on_click"]()
    assert seen == []
    nxt.props["on_click"]()
    assert seen == [2]


def test_list_page_search_hands_back_plain_text() -> None:
    """The caller filters on a string; the widget's event type stays internal."""
    typed: list[str] = []
    tree = build(
        list_page(
            title="U",
            columns=[TableColumn("Nome")],
            rows=[["Ana"]],
            search="an",
            on_search=typed.append,
        )
    )
    search = _find(tree, "tw-list-search")
    assert search is not None
    field = search.children[0]
    field.props["on_change"](_change_event("ana"))
    assert typed == ["ana"]


def _change_event(value: str) -> Any:  # noqa: ANN401 - the core's event model
    """Build the text-change event a SearchBar reports.

    Args:
        value: The new text.

    Returns:
        The event instance.
    """
    from tempest_core import TextChangeEvent

    return TextChangeEvent(value=value)


def test_form_page_grids_fields_and_spans_full_width_ones() -> None:
    """Fields flow in a grid; a full-span field takes the whole row."""
    tree = build(
        form_page(
            title="Novo usuário",
            fields=[
                FormField("Nome", _text("nome")),
                FormField("Bio", _text("bio"), span="full"),
            ],
            actions=[_text("salvar")],
        )
    )
    found = _roles(tree)
    assert roles.FORM_GRID in found
    assert found.count(roles.FORM_FIELD) == 2
    assert roles.FORM_ACTIONS in found
    wide = _find(tree, "tw-form-f1")
    assert wide is not None
    assert wide.props["attrs"]["data-tw-span"] == "full"


def test_form_field_shows_the_error_instead_of_the_help_line() -> None:
    """An invalid field must not bury its error under a hint."""
    tree = build(
        form_page(
            title="F",
            fields=[FormField("Email", _text("e"), help="Seu email", error="Inválido")],
        )
    )
    assert _find(tree, "tw-form-f0-error") is not None
    assert _find(tree, "tw-form-f0-help") is None


def test_settings_page_groups_fields_into_sections() -> None:
    """A settings screen is a form whose fields are always grouped."""
    tree = build(
        settings_page(
            title="Ajustes",
            sections=[FormSection("Conta", [FormField("Email", _text("e"))])],
        )
    )
    assert _find(tree, "tw-settings-s0") is not None
    assert roles.FORM_GRID in _roles(tree)


def test_form_page_puts_loose_fields_before_the_sections() -> None:
    """Passing ``fields`` and ``sections`` together keeps the loose ones first.

    The docstring of ``form_page`` promises this order and nothing verified it —
    the other two form tests pass one or the other, never both. The order is
    what makes a "a few fields, then grouped settings" screen read top-down, and
    silently flipping it would look like a styling bug rather than a code one.
    """
    tree = build(
        form_page(
            title="Novo usuário",
            fields=[FormField("Nome", _text("nome"))],
            sections=[FormSection("Conta", [FormField("Email", _text("e"))])],
        )
    )
    keys = [child.key for child in tree.children]
    assert "tw-form-grid" in keys, keys
    assert "tw-form-s0" in keys, keys
    assert keys.index("tw-form-grid") < keys.index("tw-form-s0"), keys
    assert _find(tree, "tw-form-f0") is not None
    assert _find(tree, "tw-form-s0-f0") is not None


def test_settings_page_renders_the_same_tree_as_an_equivalent_form_page() -> None:
    """``settings_page`` is a facade: same layout, different signature and key.

    Documented as identical rendering, so the guard is that the two trees match
    role for role. If someone later gives settings its own layout role, this
    fails and the docs have to be updated with it — which is the point.
    """
    sections = [FormSection("Conta", [FormField("Email", _text("e"))])]
    actions = [_text("salvar")]
    as_form = build(form_page(title="X", sections=sections, actions=actions))
    as_settings = build(settings_page(title="X", sections=sections, actions=actions))
    assert _roles(as_settings) == _roles(as_form)
    assert as_settings.key == "tw-settings"
    assert as_form.key == "tw-form"


def test_auth_page_centres_a_capped_card() -> None:
    """The auth screen is one card the sheet centres and caps."""
    found = _roles(build(auth_page(title="Entrar", body=_text("form"))))
    assert found[0] == roles.AUTH
    assert roles.AUTH_CARD in found


def test_presets_never_emit_an_unknown_role() -> None:
    """Every role a preset stamps must be part of the documented vocabulary."""
    trees = [
        build(
            admin_shell(
                title="P",
                nav=[NavItem("A", "a")],
                active="a",
                on_navigate=lambda _v: None,
                body=_text(),
                on_toggle_sidebar=lambda: None,
            )
        ),
        build(
            dashboard_page(
                title="D", kpis=[Kpi("K", "1")], sections=[Section("S", _text())]
            )
        ),
        build(
            list_page(
                title="L",
                columns=[TableColumn("N")],
                rows=[["a"]],
                search="",
                on_search=lambda _t: None,
                page_count=2,
                on_page=lambda _p: None,
            )
        ),
        build(
            form_page(title="F", fields=[FormField("N", _text())], actions=[_text("s")])
        ),
        build(auth_page(title="A", body=_text())),
    ]
    for tree in trees:
        for role in _roles(tree):
            assert role in roles.ROLES, role


def test_admin_shell_fixture_matches_the_presets() -> None:
    """The golden the jsdom test mounts must stay what the presets produce.

    ``tests/fixtures/presets_admin_shell.json`` is what
    ``tests/client/layouts.test.js`` renders to prove the roles survive into the
    DOM. Regenerating it by hand is how the two halves drift; this test fails the
    moment the tree changes shape.
    """
    tree = admin_shell(
        title="Painel",
        brand="ACME",
        nav=[
            NavItem("Visão geral", "overview"),
            NavItem("Usuários", "users", badge="3"),
        ],
        active="users",
        on_navigate=lambda _value: None,
        on_toggle_sidebar=lambda: None,
        body=list_page(
            title="Usuários",
            subtitle="12 ativos",
            columns=[TableColumn("Nome"), TableColumn("Saldo", align="end")],
            rows=[["Ana", "R$ 10"], ["Bo", "R$ 4"]],
            search="",
            on_search=lambda _text: None,
        ),
    )
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert node_to_wire(build(tree)) == expected
