"""Regenerate the Mode C component-parity fixture from the real core.

Run as a module to (re)write the golden::

    python -m tests.conformance._transpile_components

The Mode C components are hand-authored in ``client/transpile/components.js``:
the composition is rewritten per component, and the *output* of the core's pure
style resolvers travels as a generated table. Nothing checks that a rewrite is
faithful — so this fixture pins the expected IR, built from the **real** core
over a matrix of props, and a JS test diffs the hand-authored builder against it
(order- and key-agnostic).

The matrix matters: a single sample per component would pin the happy path and
let every variant, scheme, size and elevation drift silently, which is exactly
how a resolved style goes wrong.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tempest_core import (
    Accordion,
    AddressInput,
    Alert,
    AppBar,
    Avatar,
    Badge,
    Banner,
    Breadcrumb,
    Burger,
    Button,
    Card,
    Chip,
    CNPJInput,
    ConfidenceBadge,
    CPFInput,
    Divider,
    Drawer,
    EmailInput,
    EmptyState,
    Footer,
    Grid,
    Header,
    HStack,
    ListTile,
    MetricCard,
    NavBar,
    PasswordInput,
    PhoneInput,
    ProgressStepper,
    RadioGroup,
    Rating,
    Scaffold,
    SearchBar,
    SegmentedControl,
    Sidebar,
    Stat,
    StatCard,
    Stepper,
    StyledContainer,
    Surface,
    Tabs,
    Tag,
    Text,
    Theme,
    ThemeMode,
    VStack,
    build,
)
from tempestweb.components import (
    EmailField,
    LoginForm,
    PasswordField,
    SignupForm,
    TextField,
)
from tempestweb.runtime.wasm import serialize_node

FIXTURES_DIR: Path = Path(__file__).resolve().parents[1] / "fixtures"
COMPONENTS_FIXTURE: Path = FIXTURES_DIR / "transpile_component_samples.json"


def _noop(_: int) -> None:
    """Absorb a selection callback.

    Args:
        _: The selected index.
    """
    return None


def _noop_event(_: Any) -> None:
    """Absorb a value-change callback.

    Args:
        _: The change event the widget reports.
    """
    return None


def _noop_pair(_field: str, _value: str) -> None:
    """Absorb an address-block change callback.

    Args:
        _field: The address field that changed.
        _value: The field's new value.
    """
    return None


def _cases() -> dict[str, Any]:
    """Return the sample component builds keyed by a scenario name.

    Returns:
        A scenario name → component instance map covering, per component, the
        axes that change its resolved style: variant, color scheme, size,
        elevation, the token steps, and the presence of each optional slot.
    """
    child = Text(content="a", key="a")
    cases: dict[str, Any] = {
        "hstack_default": HStack(children=[child]),
        "hstack_lg_between": HStack(children=[], gap="lg", justify="space-between"),
        "hstack_float": HStack(children=[], gap=8.0),
        "vstack_sm": VStack(children=[child], gap="sm"),
        "vstack_start": VStack(children=[child], align="start"),
        "card_default": Card(children=[child]),
        "card_filled_primary": Card(
            children=[child], variant="filled", color_scheme="primary"
        ),
        "card_outlined_error_flat": Card(
            children=[child], variant="outlined", color_scheme="error", elevation=0
        ),
        "card_elevated_level_4": Card(children=[child], elevation=4),
        "card_steps": Card(
            children=[child], padding_step="lg", radius_step="xl", gap_step="none"
        ),
        "divider_default": Divider(),
        "divider_token_thickness": Divider(thickness="xs"),
        "divider_tinted": Divider(color_scheme="primary"),
        "chip_static": Chip(label="tag"),
        "chip_selected": Chip(label="tag", selected=True),
        "chip_clickable_lg_success": Chip(
            label="tag", on_click=lambda: None, size="lg", color_scheme="success"
        ),
        "segmented_default": SegmentedControl(options=["a", "b"], on_select=_noop),
        "segmented_second_lg": SegmentedControl(
            options=["a", "b", "c"], selected=1, on_select=_noop, size="lg"
        ),
        "segmented_secondary": SegmentedControl(
            options=["a"], on_select=_noop, color_scheme="secondary"
        ),
        "appbar_title_only": AppBar(title="Home"),
        "appbar_filled_with_slots": AppBar(
            title="Home",
            variant="filled",
            leading=Button(label="<", on_click=lambda: None, key="back"),
            actions=[Button(label="+", on_click=lambda: None, key="add")],
        ),
        "appbar_outlined_primary_level_2": AppBar(
            title="Home", variant="outlined", color_scheme="primary", elevation=2
        ),
        "radio_default": RadioGroup(options=["a", "b"], on_select=_noop),
        "radio_second_sm_warning": RadioGroup(
            options=["a", "b"],
            selected=1,
            on_select=_noop,
            size="sm",
            color_scheme="warning",
        ),
        "scaffold_body_only": Scaffold(body=child),
        "scaffold_full": Scaffold(
            app_bar=AppBar(title="Home"), body=child, bottom_bar=Divider()
        ),
        "scaffold_scroll": Scaffold(body=child, scroll=True),
        "scaffold_empty": Scaffold(),
        "surface_default": Surface(child=child),
        "surface_filled_primary": Surface(
            child=child, variant="filled", color_scheme="primary"
        ),
        "surface_outlined_error_flat": Surface(
            child=child, variant="outlined", color_scheme="error", elevation=0
        ),
        "surface_radius_lg": Surface(child=child, radius_step="lg"),
        "surface_empty": Surface(),
        "styled_container_default": StyledContainer(child=child),
        "styled_container_step_lg": StyledContainer(child=child, padding="lg"),
        "styled_container_float": StyledContainer(child=child, padding=6.0),
        "grid_three_in_two": Grid(children=[child, child, child]),
        "grid_full_rows": Grid(children=[child, child, child, child]),
        "grid_single_column": Grid(children=[child, child], columns=1),
        "grid_four_in_three_token_gap": Grid(
            children=[child, child, child, child], columns=3, gap="md"
        ),
        "grid_empty": Grid(),
        "sidebar_default": Sidebar(children=[child]),
        "sidebar_filled_primary_wide": Sidebar(
            children=[child], width=320.0, variant="filled", color_scheme="primary"
        ),
        "sidebar_outlined_level_3": Sidebar(
            children=[child], variant="outlined", elevation=3
        ),
        "drawer_closed": Drawer(children=[child]),
        "drawer_open": Drawer(open=True, children=[child]),
        "drawer_open_filled_secondary": Drawer(
            open=True,
            children=[child],
            width=200.0,
            variant="filled",
            color_scheme="secondary",
        ),
        "burger_default": Burger(on_click=lambda: None),
        "burger_solid_primary_lg": Burger(
            on_click=lambda: None, variant="solid", color_scheme="primary", size="lg"
        ),
        "header_title_only": Header(title="Reports"),
        "header_with_subtitle": Header(title="Reports", subtitle="last 30 days"),
        "header_tinted": Header(title="Reports", color_scheme="primary"),
        "header_neutral_scheme": Header(title="Reports", color_scheme="neutral"),
        "footer_default": Footer(children=[child]),
        "footer_filled_primary": Footer(
            children=[child], variant="filled", color_scheme="primary"
        ),
        "footer_outlined_flat": Footer(
            children=[child], variant="outlined", elevation=0
        ),
        "navbar_first_active": NavBar(items=["a", "b", "c"], on_select=_noop),
        "navbar_second_active_lg": NavBar(
            items=["a", "b", "c"], active=1, on_select=_noop, size="lg"
        ),
        "navbar_secondary_scheme": NavBar(
            items=["a", "b"], on_select=_noop, color_scheme="secondary"
        ),
        "breadcrumb_presentational": Breadcrumb(items=["home", "docs", "ui"]),
        "breadcrumb_navigable": Breadcrumb(
            items=["home", "docs", "ui"], on_select=_noop
        ),
        "breadcrumb_single": Breadcrumb(items=["home"], on_select=_noop),
        "breadcrumb_custom_separator": Breadcrumb(items=["a", "b"], separator="›"),
        "listtile_title_only": ListTile(title="Maria"),
        "listtile_with_subtitle": ListTile(title="Maria", subtitle="admin"),
        "listtile_with_slots": ListTile(
            title="Maria",
            subtitle="admin",
            leading=Avatar(initials="MB", key="lead"),
            trailing=Button(label="→", on_click=lambda: None, key="go"),
        ),
        "listtile_tinted": ListTile(title="Maria", color_scheme="primary"),
        "listtile_neutral_scheme": ListTile(title="Maria", color_scheme="neutral"),
        "avatar_default": Avatar(initials="MB"),
        "avatar_large_secondary": Avatar(
            initials="MB", size=64.0, color_scheme="secondary"
        ),
        "avatar_neutral": Avatar(initials="MB", color_scheme="neutral"),
        "avatar_unknown_scheme": Avatar(initials="MB", color_scheme="brand"),
        "tag_default": Tag(label="python"),
        "tag_lg_success": Tag(label="python", size="lg", color_scheme="success"),
        "rating_presentational": Rating(value=3),
        "rating_interactive": Rating(value=2, on_rate=_noop),
        "rating_three_stars": Rating(value=1, max_stars=3, color_scheme="warning"),
        "stepper_default": Stepper(on_change=_noop),
        "stepper_bounded": Stepper(
            value=5, step=2, min_value=0, max_value=10, on_change=_noop
        ),
        "searchbar_empty": SearchBar(on_change=_noop_event),
        "searchbar_with_value_and_clear": SearchBar(
            value="cat", on_change=_noop_event, on_clear=lambda: None
        ),
        "searchbar_empty_with_clear": SearchBar(
            on_change=_noop_event, on_clear=lambda: None
        ),
        "searchbar_outline_sm_primary": SearchBar(
            on_change=_noop_event,
            field_variant="outline",
            size="sm",
            color_scheme="primary",
        ),
        "banner_default": Banner(message="saved"),
        "banner_success_tone": Banner(message="saved", tone="success"),
        "banner_unknown_tone": Banner(message="saved", tone="fuchsia"),
        "banner_solid_scheme": Banner(
            message="saved", variant="solid", color_scheme="error"
        ),
        "banner_left_accent_with_action": Banner(
            message="saved",
            variant="left_accent",
            action=Button(label="undo", on_click=lambda: None, key="undo"),
        ),
        "alert_title_only": Alert(title="Heads up"),
        "alert_body_and_glyph": Alert(title="Heads up", body="check it", glyph="!"),
        "alert_left_accent_error": Alert(
            title="Heads up", variant="left_accent", color_scheme="error"
        ),
        "alert_top_accent_with_dismiss": Alert(
            title="Heads up",
            variant="top_accent",
            color_scheme="success",
            dismiss=Button(label="x", on_click=lambda: None, key="close"),
        ),
        "badge_default": Badge(label="3"),
        "badge_subtle_info_md": Badge(
            label="3", variant="subtle", color_scheme="info", size="md"
        ),
        "badge_outline_warning_lg": Badge(
            label="NEW", variant="outline", color_scheme="warning", size="lg"
        ),
        "badge_success_tone": Badge(label="3", tone="success"),
        "badge_unknown_tone": Badge(label="3", tone="fuchsia"),
        "emptystate_default": EmptyState(title="Nothing here"),
        "emptystate_full": EmptyState(
            title="Nothing here",
            subtitle="add the first one",
            glyph="◍",
            action=Button(label="add", on_click=lambda: None, key="add"),
        ),
        "stat_plain": Stat(label="revenue", value="R$ 1.2M"),
        "stat_delta_up": Stat(label="revenue", value="R$ 1.2M", delta="+12%"),
        "stat_delta_down": Stat(
            label="revenue", value="R$ 1.2M", delta="-3%", delta_up=False
        ),
        "progress_stepper_first": ProgressStepper(steps=["a", "b", "c"]),
        "progress_stepper_second": ProgressStepper(steps=["a", "b", "c"], current=1),
        "progress_stepper_single": ProgressStepper(steps=["a"]),
        "progress_stepper_secondary": ProgressStepper(
            steps=["a", "b"], current=1, color_scheme="secondary"
        ),
        "metric_card_plain": MetricCard(label="users", value="1.2k"),
        "metric_card_delta": MetricCard(label="users", value="1.2k", delta="+8%"),
        "metric_card_trailing": MetricCard(
            label="users",
            value="1.2k",
            trailing=Text(content="~", key="spark"),
        ),
        "metric_card_filled_primary": MetricCard(
            label="users", value="1.2k", variant="filled", color_scheme="primary"
        ),
        "stat_card_default": StatCard(label="users", value="1.2k"),
        "stat_card_delta_down": StatCard(
            label="users", value="1.2k", delta="-2%", delta_up=False
        ),
        "confidence_badge_high": ConfidenceBadge(confidence=0.92),
        "confidence_badge_mid": ConfidenceBadge(confidence=0.61),
        "confidence_badge_low": ConfidenceBadge(confidence=0.2),
        "confidence_badge_labelled": ConfidenceBadge(confidence=0.92, label="cat"),
        "confidence_badge_custom_thresholds": ConfidenceBadge(
            confidence=0.61, high=0.6, mid=0.3
        ),
        "accordion_closed": Accordion(title="Details", on_toggle=lambda: None),
        "accordion_open": Accordion(
            title="Details", open=True, children=[child], on_toggle=lambda: None
        ),
        "accordion_outlined_primary": Accordion(
            title="Details",
            variant="outlined",
            color_scheme="primary",
            on_toggle=lambda: None,
        ),
        "accordion_open_elevated_error": Accordion(
            title="Details",
            open=True,
            children=[child],
            variant="elevated",
            color_scheme="error",
            on_toggle=lambda: None,
        ),
        "tabs_default": Tabs(tabs=["a", "b"], on_select=_noop),
        "tabs_second_lg": Tabs(
            tabs=["a", "b", "c"], active=1, on_select=_noop, size="lg"
        ),
        "tabs_secondary_sm": Tabs(
            tabs=["a"], on_select=_noop, color_scheme="secondary", size="sm"
        ),
        "tabs_empty": Tabs(tabs=[], on_select=_noop),
        "tabs_active_out_of_range": Tabs(tabs=["a", "b"], active=7, on_select=_noop),
        "email_input_default": EmailInput(on_change=_noop_event),
        "email_input_value_and_error": EmailInput(
            value="a@b.c",
            error="inválido",
            placeholder="seu e-mail",
            on_change=_noop_event,
        ),
        "email_input_filled_lg_unlabelled": EmailInput(
            label="",
            field_variant="filled",
            size="lg",
            color_scheme="secondary",
            on_change=_noop_event,
        ),
        "password_input_default": PasswordInput(on_change=_noop_event),
        "password_input_flushed_sm_error": PasswordInput(
            value="hunter2",
            error="curta demais",
            field_variant="flushed",
            size="sm",
            on_change=_noop_event,
        ),
        "phone_input_default": PhoneInput(on_change=_noop_event),
        "phone_input_value_filled": PhoneInput(
            value="(11) 99999-1234", field_variant="filled", on_change=_noop_event
        ),
        "cpf_input_default": CPFInput(on_change=_noop_event),
        "cpf_input_error_lg": CPFInput(
            value="529.982.247-25",
            error="CPF inválido",
            size="lg",
            on_change=_noop_event,
        ),
        "cnpj_input_default": CNPJInput(on_change=_noop_event),
        "cnpj_input_outline_error_scheme": CNPJInput(
            value="11.222.333/0001-81",
            error="CNPJ inválido",
            color_scheme="error",
            on_change=_noop_event,
        ),
        "address_input_default": AddressInput(on_change=_noop_pair),
        "address_input_filled_values": AddressInput(
            cep="01001-000",
            street="Praça da Sé",
            number="1",
            complement="lado ímpar",
            neighborhood="Sé",
            city="São Paulo",
            state="SP",
            field_variant="filled",
            on_change=_noop_pair,
        ),
        "address_input_unlabelled_sm": AddressInput(
            label="", size="sm", on_change=_noop_pair
        ),
        "text_field_default": TextField(on_change=_noop_event),
        "text_field_labelled_error": TextField(
            value="Ana",
            label="Nome",
            placeholder="seu nome",
            error="obrigatório",
            key="name",
            on_change=_noop_event,
        ),
        "email_field_default": EmailField(on_change=_noop_event),
        "email_field_keyed_error": EmailField(
            value="a@b.c", error="inválido", key="signup-email", on_change=_noop_event
        ),
        "email_field_unlabelled": EmailField(label="", on_change=_noop_event),
        "password_field_default": PasswordField(on_change=_noop_event),
        "password_field_labelled_error": PasswordField(
            value="x",
            label="Confirmar senha",
            error="não confere",
            key="signup-confirm",
            on_change=_noop_event,
        ),
        "login_form_default": LoginForm(
            on_email_change=_noop_event,
            on_password_change=_noop_event,
            on_submit=lambda: None,
        ),
        "login_form_title_errors_keyed": LoginForm(
            email="a@b.c",
            password="x",
            email_error="inválido",
            password_error="curta",
            title="Entrar",
            submit_label="Continuar",
            key="auth",
            on_email_change=_noop_event,
            on_password_change=_noop_event,
            on_submit=lambda: None,
        ),
        "signup_form_default": SignupForm(
            on_email_change=_noop_event,
            on_password_change=_noop_event,
            on_confirm_change=_noop_event,
            on_submit=lambda: None,
        ),
        "signup_form_full": SignupForm(
            email="a@b.c",
            password="x",
            confirm="y",
            confirm_error="não confere",
            title="Criar conta",
            key="reg",
            on_email_change=_noop_event,
            on_password_change=_noop_event,
            on_confirm_change=_noop_event,
            on_submit=lambda: None,
        ),
    }
    return cases


#: One representative case per component that namespaces an inner key under its
#: own. Each gets a ``__keyed`` twin built with an explicit ``key``, because the
#: unkeyed build hides the namespacing: ``Accordion()`` emits
#: ``accordion-header`` either way, while ``Accordion(key="faq-3")`` emits
#: ``faq-3-header`` only when the builder actually derives it. That hole is how a
#: hand-written port kept literal child keys through a whole release.
KEYED_TWINS: tuple[str, ...] = (
    "accordion_open",
    "address_input_default",
    "alert_title_only",
    "appbar_title_only",
    "avatar_default",
    "banner_default",
    "breadcrumb_navigable",
    "card_default",
    "cnpj_input_default",
    "cpf_input_default",
    "email_field_keyed_error",
    "email_input_value_and_error",
    "emptystate_full",
    "grid_three_in_two",
    "header_title_only",
    "listtile_with_subtitle",
    "login_form_default",
    "metric_card_delta",
    "navbar_first_active",
    "password_field_default",
    "password_input_flushed_sm_error",
    "phone_input_default",
    "progress_stepper_second",
    "radio_default",
    "rating_three_stars",
    "scaffold_body_only",
    "searchbar_with_value_and_clear",
    "segmented_second_lg",
    "signup_form_default",
    "stat_plain",
    "stat_card_default",
    "stepper_bounded",
    "tabs_second_lg",
    "text_field_default",
)


def build_samples() -> dict[str, Any]:
    """Build each sample to its serialized IR (the component's own key dropped).

    The component's own root key is dropped so the fixture pins the *shape and
    style* the builder must reproduce, not the core's incidental keying. The wire
    serializer is the runtime's own, so a handler prop is ``null`` here exactly as
    it is on the wire — which is what the JS builders emit.

    Every entry in :data:`KEYED_TWINS` is built a second time with an explicit
    ``key``, under a ``__keyed`` name. Only the root key is dropped, so the twin
    pins what the unkeyed build cannot: that each *inner* key is namespaced under
    the caller's, the way ``Component.child_key`` does.

    **Every** case is also built a second time in dark mode, under a ``__dark``
    name. That twin is the whole guard for tempestweb#106: the Mode C tables were
    baked from the default theme, so a component rendered light whatever the app
    asked — and a light-only matrix could not see it, because light is what it
    compared against. A component whose port forgets to pass the theme down to a
    child now fails here, on that child's colour.

    Returns:
        A scenario → serialized IR node map.
    """
    cases = _cases()
    samples: dict[str, Any] = {}
    for name, widget in cases.items():
        node = serialize_node(build(widget))
        node["key"] = None
        samples[name] = node
        samples[f"{name}__dark"] = _dark_sample(widget)
    for name in KEYED_TWINS:
        twin = serialize_node(build(cases[name].model_copy(update={"key": "k9"})))
        twin["key"] = None
        samples[f"{name}__keyed"] = twin
    return samples


def _dark_sample(widget: Any) -> dict[str, Any]:  # noqa: ANN401 — any core component
    """Build one case again in dark mode, serialized like its light twin.

    Args:
        widget: The component instance the light sample was built from.

    Returns:
        The serialized IR node, with the root key dropped.
    """
    dark = widget.model_copy(update={"theme": Theme(mode=ThemeMode.DARK)})
    node = serialize_node(build(dark))
    node["key"] = None
    return node


def render_fixture_text() -> str:
    """Render the component-parity fixture as canonical JSON text."""
    return (
        json.dumps(build_samples(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )


def write_fixture() -> Path:
    """Write the component-parity fixture to disk and return its path."""
    COMPONENTS_FIXTURE.write_text(render_fixture_text(), encoding="utf-8")
    return COMPONENTS_FIXTURE


def main() -> None:
    """Regenerate the component-parity fixture and print its path."""
    print(f"wrote {write_fixture()}")


if __name__ == "__main__":
    main()
