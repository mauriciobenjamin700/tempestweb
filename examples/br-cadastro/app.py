"""Brazilian registration form — CPF/CNPJ, phone, address with masked inputs.

Demonstrates the full complement of BR-specific form components from
:mod:`tempest_core.components.brforms` paired with the real-time
validators from :mod:`tempest_core.validators`.

Two registration modes are offered via a segmented control:

* **Pessoa Física (PF)** — individual: CPF + phone + address.
* **Pessoa Jurídica (PJ)** — company: CNPJ + company name + phone + address.

Each field validates on change; a summary banner is shown only when the form
is submitted (and passes all checks), or when errors are present after a
submit attempt.

Run in either mode — the app never names the transport::

    tempestweb dev --mode wasm
    tempestweb dev --mode server
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Style, Widget
from tempest_core.components import (
    AddressInput,
    Banner,
    Card,
    CNPJInput,
    CPFInput,
    Divider,
    EmailInput,
    PhoneInput,
    SegmentedControl,
)
from tempest_core.style import Color, Edge, FontWeight
from tempest_core.validators import (
    validate_cnpj,
    validate_cpf,
    validate_email,
    validate_phone,
)
from tempest_core.widgets import Button, Column, Input, Text

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

#: The error-text color shared by every inline error message.
_ERROR_COLOR: Color = Color.from_hex("#ef4444")

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

#: Registered modes exposed by the segmented control.
_MODES: list[str] = ["Pessoa Física", "Pessoa Jurídica"]

#: Address field names reported by :class:`~tempest_core.components.AddressInput`.
_ADDRESS_FIELDS: tuple[str, ...] = (
    "cep",
    "street",
    "number",
    "complement",
    "neighborhood",
    "city",
    "state",
)


@dataclass
class AddressData:
    """Holds every sub-field of a Brazilian address.

    Attributes:
        cep: Postal code (CEP), e.g. ``"01310-100"``.
        street: Street or avenue name.
        number: House or building number.
        complement: Apartment, suite, etc.
        neighborhood: Bairro.
        city: City name.
        state: Two-letter state code (UF).
    """

    cep: str = ""
    street: str = ""
    number: str = ""
    complement: str = ""
    neighborhood: str = ""
    city: str = ""
    state: str = ""


@dataclass
class CadastroState:
    """Top-level application state for the BR registration form.

    Attributes:
        mode: Index into :data:`_MODES`; ``0`` = PF, ``1`` = PJ.
        cpf: CPF value (PF mode).
        cnpj: CNPJ value (PJ mode).
        company_name: Company/trade name (PJ mode).
        phone: Brazilian phone number.
        email: Contact e-mail.
        address: Nested address fields shared by both modes.
        errors: Per-field validation messages from the last submit attempt.
        submitted: Whether the last submit succeeded (all fields valid).
    """

    mode: int = 0
    cpf: str = ""
    cnpj: str = ""
    company_name: str = ""
    phone: str = ""
    email: str = ""
    address: AddressData = field(default_factory=AddressData)
    errors: dict[str, str] = field(default_factory=dict)
    submitted: bool = False


def make_state() -> CadastroState:
    """Build the initial, blank registration state.

    Returns:
        A fresh :class:`CadastroState` ready for the first render.
    """
    return CadastroState()


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_pf(s: CadastroState) -> dict[str, str]:
    """Validate all PF (individual) fields and return per-field error messages.

    Args:
        s: The current registration state.

    Returns:
        A mapping of field name → PT-BR error string for every failing field.
        An empty dict means all fields are valid.
    """
    errs: dict[str, str] = {}
    cpf_err = validate_cpf(s.cpf)
    if cpf_err:
        errs["cpf"] = cpf_err
    phone_err = validate_phone(s.phone)
    if phone_err:
        errs["phone"] = phone_err
    email_err = validate_email(s.email)
    if email_err:
        errs["email"] = email_err
    if not s.address.cep.strip():
        errs["cep"] = "CEP é obrigatório"
    if not s.address.street.strip():
        errs["street"] = "Rua é obrigatória"
    if not s.address.city.strip():
        errs["city"] = "Cidade é obrigatória"
    if not s.address.state.strip():
        errs["state"] = "UF é obrigatória"
    return errs


def _validate_pj(s: CadastroState) -> dict[str, str]:
    """Validate all PJ (company) fields and return per-field error messages.

    Args:
        s: The current registration state.

    Returns:
        A mapping of field name → PT-BR error string for every failing field.
        An empty dict means all fields are valid.
    """
    errs: dict[str, str] = {}
    cnpj_err = validate_cnpj(s.cnpj)
    if cnpj_err:
        errs["cnpj"] = cnpj_err
    if not s.company_name.strip():
        errs["company_name"] = "Razão social é obrigatória"
    phone_err = validate_phone(s.phone)
    if phone_err:
        errs["phone"] = phone_err
    email_err = validate_email(s.email)
    if email_err:
        errs["email"] = email_err
    if not s.address.cep.strip():
        errs["cep"] = "CEP é obrigatório"
    if not s.address.street.strip():
        errs["street"] = "Rua é obrigatória"
    if not s.address.city.strip():
        errs["city"] = "Cidade é obrigatória"
    if not s.address.state.strip():
        errs["state"] = "UF é obrigatória"
    return errs


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[CadastroState]) -> Widget:
    """Render the Brazilian registration form from the current state.

    Builds a :class:`~tempest_core.components.SegmentedControl` for PF/PJ
    mode switching, then the appropriate set of BR-document inputs
    (:class:`~tempest_core.components.CPFInput` or
    :class:`~tempest_core.components.CNPJInput`), followed by shared
    :class:`~tempest_core.components.PhoneInput`,
    :class:`~tempest_core.components.EmailInput` and
    :class:`~tempest_core.components.AddressInput` fields. A submit button
    triggers full validation and shows a status
    :class:`~tempest_core.components.Banner`.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The complete widget tree for the current state.
    """
    s = app.state
    is_pj = s.mode == 1

    # -- mode switch ----------------------------------------------------------
    def on_mode_select(index: int) -> None:
        """Switch between PF and PJ mode, clearing previous errors.

        Args:
            index: The selected segment index (0 = PF, 1 = PJ).
        """

        def mutate(st: CadastroState) -> None:
            st.mode = index
            st.errors = {}
            st.submitted = False

        app.set_state(mutate)

    mode_control = SegmentedControl(
        options=_MODES,
        selected=s.mode,
        on_select=on_mode_select,
        key="mode-control",
    )

    # -- document field (CPF or CNPJ) -----------------------------------------
    doc_widgets: list[Widget] = []

    if is_pj:

        def on_cnpj(value: str) -> None:
            """Update CNPJ and clear its error when the value changes.

            Args:
                value: The new masked CNPJ string.
            """

            def mutate(st: CadastroState) -> None:
                st.cnpj = value
                st.errors.pop("cnpj", None)
                st.submitted = False

            app.set_state(mutate)

        def on_company_name(value: str) -> None:
            """Update the company name and clear its error.

            Args:
                value: The new company name string.
            """

            def mutate(st: CadastroState) -> None:
                st.company_name = value
                st.errors.pop("company_name", None)
                st.submitted = False

            app.set_state(mutate)

        doc_widgets.append(
            CNPJInput(
                value=s.cnpj,
                label="CNPJ",
                placeholder="00.000.000/0000-00",
                error=s.errors.get("cnpj", ""),
                on_change=on_cnpj,
                key="cnpj-input",
            )
        )
        doc_widgets.append(
            Input(
                value=s.company_name,
                placeholder="Razão social",
                on_change=lambda ev: on_company_name(ev.value),
                key="company-name-input",
                style=Style(
                    padding=Edge.symmetric(vertical=10.0, horizontal=14.0),
                    radius=8.0,
                ),
            )
        )
        if "company_name" in s.errors:
            doc_widgets.append(
                Text(
                    content=s.errors["company_name"],
                    style=Style(font_size=12.0, color=_ERROR_COLOR),
                    key="company-name-error",
                )
            )
    else:

        def on_cpf(value: str) -> None:
            """Update CPF and clear its error when the value changes.

            Args:
                value: The new masked CPF string.
            """

            def mutate(st: CadastroState) -> None:
                st.cpf = value
                st.errors.pop("cpf", None)
                st.submitted = False

            app.set_state(mutate)

        doc_widgets.append(
            CPFInput(
                value=s.cpf,
                label="CPF",
                placeholder="000.000.000-00",
                error=s.errors.get("cpf", ""),
                on_change=on_cpf,
                key="cpf-input",
            )
        )

    # -- shared fields (phone + email) ----------------------------------------
    def on_phone(value: str) -> None:
        """Update the phone number and clear its error.

        Args:
            value: The new masked phone string.
        """

        def mutate(st: CadastroState) -> None:
            st.phone = value
            st.errors.pop("phone", None)
            st.submitted = False

        app.set_state(mutate)

    def on_email(value: str) -> None:
        """Update the e-mail address and clear its error.

        Args:
            value: The new e-mail string.
        """

        def mutate(st: CadastroState) -> None:
            st.email = value
            st.errors.pop("email", None)
            st.submitted = False

        app.set_state(mutate)

    phone_widget = PhoneInput(
        value=s.phone,
        label="Telefone",
        placeholder="(00) 00000-0000",
        error=s.errors.get("phone", ""),
        on_change=on_phone,
        key="phone-input",
    )

    email_widget = EmailInput(
        value=s.email,
        label="E-mail",
        placeholder="contato@empresa.com.br",
        error=s.errors.get("email", ""),
        on_change=on_email,
        key="email-input",
    )

    # -- address block --------------------------------------------------------
    addr = s.address

    def on_address(field_name: str, value: str) -> None:
        """Update one address sub-field and clear its error.

        Args:
            field_name: One of ``"cep"``, ``"street"``, ``"number"``,
                ``"complement"``, ``"neighborhood"``, ``"city"`` or ``"state"``.
            value: The new field value.
        """

        def mutate(st: CadastroState) -> None:
            setattr(st.address, field_name, value)
            st.errors.pop(field_name, None)
            st.submitted = False

        app.set_state(mutate)

    address_widget = AddressInput(
        cep=addr.cep,
        street=addr.street,
        number=addr.number,
        complement=addr.complement,
        neighborhood=addr.neighborhood,
        city=addr.city,
        state=addr.state,
        label="Endereço",
        on_change=on_address,
        key="address-input",
    )

    # -- submit ---------------------------------------------------------------
    def on_submit() -> None:
        """Validate all fields and update state accordingly.

        Runs the PF or PJ validator suite, stores errors and sets
        :attr:`CadastroState.submitted` to ``True`` only when every field
        passes.
        """
        errors = _validate_pj(s) if is_pj else _validate_pf(s)

        def mutate(st: CadastroState) -> None:
            st.errors = errors
            st.submitted = len(errors) == 0

        app.set_state(mutate)

    submit_btn = Button(label="Cadastrar", on_click=on_submit, key="submit-btn")

    # -- status banner --------------------------------------------------------
    banner_widgets: list[Widget] = []
    if s.submitted:
        banner_widgets.append(
            Banner(
                message="Cadastro realizado com sucesso!",
                tone="success",
                key="success-banner",
            )
        )
    elif s.errors:
        error_count = len(s.errors)
        banner_widgets.append(
            Banner(
                message=f"{error_count} campo(s) com erro — corrija e tente novamente.",
                tone="error",
                key="error-banner",
            )
        )

    # -- page title -----------------------------------------------------------
    title = Text(
        content="Cadastro — " + _MODES[s.mode],
        style=Style(font_size=20.0, font_weight=FontWeight.BOLD),
        key="page-title",
    )

    # -- assemble -------------------------------------------------------------
    form_children: list[Widget] = [
        mode_control,
        Divider(key="mode-divider"),
        *doc_widgets,
        phone_widget,
        email_widget,
        address_widget,
        Divider(key="submit-divider"),
        submit_btn,
        *banner_widgets,
    ]

    return Column(
        style=Style(gap=12.0, padding=Edge.all(20.0)),
        children=[
            title,
            Card(
                children=form_children,
                key="cadastro-card",
            ),
        ],
    )
