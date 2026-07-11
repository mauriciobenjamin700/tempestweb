# Cadastro Brasileiro (PF/PJ)

> 🚀 **O que você vai construir:** um formulário de cadastro completo para Pessoa Física e Pessoa Jurídica, com máscara automática de CPF, CNPJ, telefone e endereço, validadores BR em tempo real e um banner de status ao submeter.

---

## Por que esse exemplo importa?

Aplicações brasileiras precisam lidar com documentos fiscais, telefones no padrão nacional e endereços com CEP.
Fazer isso "na mão" (regex + `str.replace` espalhados pelo código) vira rapidamente uma fonte de bugs sutis e código duplicado.

O tempestweb oferece um conjunto de componentes prontos para esse cenário:

- **`CPFInput` / `CNPJInput`** — entrada com máscara e validação de dígitos verificadores;
- **`PhoneInput`** — máscara `(DDD) 9xxxx-xxxx` automática;
- **`AddressInput`** — grupo de campos de endereço (CEP, rua, número, complemento, bairro, cidade, UF);
- **`EmailInput`** — campo de e-mail com validação básica;
- **`SegmentedControl`** — troca de modo PF ↔ PJ com um clique;
- **`Banner`** — feedback visual de sucesso ou erro após submit.

Neste tutorial você vai aprender a:

- Usar `SegmentedControl` para alternar entre dois fluxos distintos no mesmo formulário;
- Conectar cada campo a um handler que limpa o erro específico ao digitar;
- Escrever funções de validação puras que retornam um `dict[str, str]` de erros;
- Exibir um `Banner` de sucesso ou erro condicionalmente no estado;
- Compor tudo dentro de um `Card` com `Divider`s para separar seções.

!!! note "Nota"
    Este exemplo roda **sem nenhuma alteração** nos dois modos — WASM (Pyodide no browser) e Servidor (FastAPI + WebSocket). A mesma função `view()` Python serve os dois.

---

## Pré-requisitos

Instale o tempestweb e confirme que o CLI está disponível:

```bash
pip install tempestweb
tempestweb --version
```

!!! tip "Dica"
    Já tem o tempestweb instalado? Certifique-se de estar na versão mais recente com `pip install -U tempestweb`.

---

## Estrutura do projeto

```
examples/
└── br-cadastro/
    └── app.py
```

Crie a pasta e o arquivo:

```bash
mkdir -p examples/br-cadastro
touch examples/br-cadastro/app.py
```

---

## Passo 1 — Imports e constantes

Abra `app.py` e escreva os imports. Note a separação clara: widgets genéricos vêm de `tempest_core.widgets`, componentes compostos (incluindo todos os inputs BR) vêm de `tempest_core.components`, e os validadores vêm de `tempest_core.validators`.

```python
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
```

Logo abaixo dos imports, defina as três constantes do módulo:

```python
#: A cor vermelha compartilhada por todas as mensagens de erro inline.
_ERROR_COLOR: Color = Color.from_hex("#ef4444")

#: Rótulos exibidos pelo SegmentedControl.
_MODES: list[str] = ["Pessoa Física", "Pessoa Jurídica"]

#: Nomes dos sub-campos gerenciados pelo AddressInput.
_ADDRESS_FIELDS: tuple[str, ...] = (
    "cep",
    "street",
    "number",
    "complement",
    "neighborhood",
    "city",
    "state",
)
```

**Por que constantes de módulo?**
`_ERROR_COLOR` e `_MODES` são usadas em vários pontos da `view()`. Mantê-las no topo evita literais repetidas e torna uma eventual troca de cor ou de label uma mudança de uma só linha.

---

## Passo 2 — Modelar o estado

O estado é dividido em dois dataclasses: `AddressData` para os sub-campos do endereço e `CadastroState` para todo o restante.

```python
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
```

!!! info "Por que `field(default_factory=...)`?"
    Dataclasses Python **não permitem** valores mutáveis (listas, dicts) como default literal — você receberia um `ValueError` em tempo de definição. `field(default_factory=AddressData)` e `field(default_factory=dict)` criam um novo objeto a cada instância, evitando o clássico bug de estado compartilhado entre instâncias.

**Ponto importante:** `errors` usa as mesmas chaves dos campos (`"cpf"`, `"phone"`, `"cep"` etc.). Isso permite que cada `Input` consulte seu erro específico com `s.errors.get("cpf", "")` sem nenhum mapeamento extra.

---

## Passo 3 — Funções de validação puras

As funções de validação ficam **fora** da `view()`. Elas recebem o estado e devolvem um dict de erros — sem efeitos colaterais, fáceis de testar isoladamente.

```python
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
```

!!! tip "Dica — validators do core"
    `validate_cpf`, `validate_cnpj`, `validate_phone` e `validate_email` já implementam os algoritmos oficiais dos dígitos verificadores e retornam uma string de erro em PT-BR (ou `""` quando válido). Você não precisa reimplementar nada.

---

## Passo 4 — A função `view()`

Toda a lógica de renderização vive em `view(app)`. Vamos construí-la em partes.

### 4a — Controle de modo (SegmentedControl)

```python
def view(app: App[CadastroState]) -> Widget:
    """Render the Brazilian registration form from the current state."""
    s = app.state
    is_pj = s.mode == 1

    # -- mode switch ----------------------------------------------------------
    def on_mode_select(index: int) -> None:
        """Switch between PF and PJ mode, clearing previous errors."""

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
```

O `SegmentedControl` renderiza dois botões horizontais. Quando o usuário clica, `on_mode_select` recebe o índice (0 ou 1), zera os erros acumulados e marca `submitted = False` — evitando que um banner de erro do modo anterior apareça no novo modo.

!!! note "Nota — mutação funcional"
    `app.set_state(mutate)` recebe uma **função** que altera o estado. Isso garante que as atualizações sejam atômicas e que o reconciliador receba sempre o snapshot mais recente antes de recalcular o diff. Veja mais em [Tutorial — Estado](../tutorial/state.md).

### 4b — Campo de documento (CPF ou CNPJ)

O bloco de documento é condicional: PJ exibe `CNPJInput` + campo de razão social; PF exibe apenas `CPFInput`.

```python
    # -- document field (CPF or CNPJ) -----------------------------------------
    doc_widgets: list[Widget] = []

    if is_pj:

        def on_cnpj(value: str) -> None:
            """Update CNPJ and clear its error when the value changes."""

            def mutate(st: CadastroState) -> None:
                st.cnpj = value
                st.errors.pop("cnpj", None)
                st.submitted = False

            app.set_state(mutate)

        def on_company_name(value: str) -> None:
            """Update the company name and clear its error."""

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
            """Update CPF and clear its error when the value changes."""

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
```

💡 O padrão `st.errors.pop("campo", None)` limpa o erro **do campo específico** assim que o usuário começa a corrigir, sem apagar os erros dos demais campos que ainda não foram tocados.

### 4c — Campos compartilhados (telefone e e-mail)

```python
    # -- shared fields (phone + email) ----------------------------------------
    def on_phone(value: str) -> None:
        """Update the phone number and clear its error."""

        def mutate(st: CadastroState) -> None:
            st.phone = value
            st.errors.pop("phone", None)
            st.submitted = False

        app.set_state(mutate)

    def on_email(value: str) -> None:
        """Update the e-mail address and clear its error."""

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
```

`PhoneInput` e `EmailInput` funcionam exatamente como `CPFInput`/`CNPJInput`: recebem `value`, `label`, `placeholder`, `error` e `on_change`. O padrão é idêntico — consistência intencional.

### 4d — Bloco de endereço

```python
    # -- address block --------------------------------------------------------
    addr = s.address

    def on_address(field_name: str, value: str) -> None:
        """Update one address sub-field and clear its error."""

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
```

`AddressInput` recebe um único `on_change(field_name, value)` para todos os seus sub-campos. O `setattr(st.address, field_name, value)` usa o nome do campo como chave dinâmica — é por isso que `_ADDRESS_FIELDS` documenta os nomes possíveis.

### 4e — Submit e banner de status

```python
    # -- submit ---------------------------------------------------------------
    def on_submit() -> None:
        """Validate all fields and update state accordingly."""
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
```

O `Banner` aceita `tone="success"` (verde) ou `tone="error"` (vermelho). A condição `elif s.errors` só exibe o banner de erro **após uma tentativa de submit** — enquanto o usuário preenche o formulário pela primeira vez, nenhum banner aparece.

!!! warning "Aviso — captura do `s` no closure"
    Note que `on_submit` captura `s` (o snapshot atual) e `is_pj` do escopo externo da `view()`. Isso é correto: quando `on_submit` for chamado, ele lerá `s` e `is_pj` do momento da renderização mais recente, que é exatamente o que queremos.

### 4f — Montagem final

```python
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
```

O `*doc_widgets` (splat) insere zero, um ou dois widgets dinamicamente — sem nenhum `if` extra no assembly final. O `Card` agrupa todos os campos com espaçamento e borda visual; o `Column` externo adiciona padding à página inteira.

---

## O arquivo completo

Aqui está o `app.py` completo, pronto para copiar:

```python
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
    tempestweb run --mode server
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
    """Render the Brazilian registration form from the current state."""
    s = app.state
    is_pj = s.mode == 1

    # -- mode switch ----------------------------------------------------------
    def on_mode_select(index: int) -> None:
        """Switch between PF and PJ mode, clearing previous errors."""

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
            """Update CNPJ and clear its error when the value changes."""

            def mutate(st: CadastroState) -> None:
                st.cnpj = value
                st.errors.pop("cnpj", None)
                st.submitted = False

            app.set_state(mutate)

        def on_company_name(value: str) -> None:
            """Update the company name and clear its error."""

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
            """Update CPF and clear its error when the value changes."""

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
        """Update the phone number and clear its error."""

        def mutate(st: CadastroState) -> None:
            st.phone = value
            st.errors.pop("phone", None)
            st.submitted = False

        app.set_state(mutate)

    def on_email(value: str) -> None:
        """Update the e-mail address and clear its error."""

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
        """Update one address sub-field and clear its error."""

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
        """Validate all fields and update state accordingly."""
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
```

---

## Passo 5 — Executar o app

### Modo WASM (Pyodide no browser)

```bash
tempestweb dev --mode wasm --path examples/br-cadastro
```

O CLI inicia um servidor local, abre o browser e carrega o Pyodide. Toda a lógica Python roda **dentro do browser** — nenhum roundtrip ao servidor.

### Modo Servidor (FastAPI + WebSocket)

```bash
tempestweb run --mode server --path examples/br-cadastro
```

O Python roda no servidor. O browser recebe patches de UI via WebSocket. A experiência para o usuário final é idêntica.

!!! check "Verificação"
    Após abrir o app no browser:

    1. Tente clicar em **Cadastrar** com os campos vazios — o banner de erro deve aparecer com a contagem de campos inválidos.
    2. Preencha um CPF inválido (ex.: `111.111.111-11`) — a mensagem de erro inline deve aparecer abaixo do campo ao submeter.
    3. Troque para **Pessoa Jurídica** — os campos de CPF desaparecem e CNPJ + razão social surgem; os erros anteriores são limpos.
    4. Preencha todos os campos corretamente e clique em **Cadastrar** — o banner verde de sucesso deve aparecer.

---

## Recapitulando

Neste tutorial você construiu um formulário de cadastro BR completo. Veja o que aprendeu:

- ✅ **`SegmentedControl`** alterna entre fluxos distintos (PF/PJ) limpando estado obsoleto no `on_select`.
- ✅ **`CPFInput` / `CNPJInput` / `PhoneInput` / `EmailInput`** seguem a mesma interface: `value`, `label`, `placeholder`, `error`, `on_change` — fáceis de combinar.
- ✅ **`AddressInput`** delega para um único callback `on_change(field_name, value)`, tornando o handler genérico via `setattr`.
- ✅ **Validação pura** fora da `view()` retorna `dict[str, str]` — testável isoladamente, sem efeitos colaterais.
- ✅ O padrão `st.errors.pop("campo", None)` limpa erros **por campo** ao digitar, sem afetar os demais.
- ✅ **`Banner`** com `tone="success"` ou `tone="error"` fornece feedback visual de submit sem nenhum widget extra.
- ✅ **`*doc_widgets` (splat)** injeta widgets condicionais no assembly final sem `if`s adicionais.

---

## Próximos passos

- Explore outros exemplos de formulário: [Conversor de Temperatura](./temperature-converter.md) mostra validação em tempo real sem submit explícito.
- Veja a [Data Table](./data-table.md) para exibir os cadastros após persistência.
- Aprenda os fundamentos em [Tutorial — Introdução](../tutorial/index.md) e [Tutorial — Estado](../tutorial/state.md).
