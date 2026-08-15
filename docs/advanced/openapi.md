# Gerar um cliente do OpenAPI (`tempestweb gen api`)

!!! tip "O que você vai aprender"
    A tirar um **cliente tipado** — models + serviços — direto do `openapi.json`
    do seu backend, sem escrever `fetch` na mão nem manter tipos sincronizados
    com a API. 🚀

Se o seu backend é FastAPI (ou qualquer API que exponha um **OpenAPI 3.x**), o
`tempestweb gen api` lê o spec e **gera o cliente pra você**, no padrão da
Tempest: um pacote por **grupo de rotas** (a `tag` da operação), cada um com
**models `@dataclass`** e uma **classe de serviço** cujos métodos chamam
[`native.http`](native-reference.md). É o análogo, em Python, do
`tempest gen api` do `tempest-react-sdk` (que emite Zod + TS).

## Por que dataclasses (e não pydantic)

!!! info "Um cliente, três modos"
    O cliente gerado roda nos três modos do tempestweb — inclusive o **Modo C
    (transpile)**, que transcreve seu Python pra JavaScript. O transpile suporta
    `@dataclass`, mas **não** pydantic (que precisa de runtime Python). Por isso
    os models saem como dataclasses com um `from_dict` — funcionam igual em WASM,
    server e transpile.

## Gerando

Aponte pro `/openapi.json` do backend rodando, ou pra um arquivo salvo:

```bash
# a partir de um servidor FastAPI rodando
tempestweb gen api http://127.0.0.1:8000/openapi.json --out api

# ou a partir de um arquivo
tempestweb gen api ./openapi.json --out api
```

A flag `--out` escolhe o diretório de saída (default: `./api`).

## O que é gerado

Para cada **tag** sai um pacote; um `_runtime.py` e um `__init__.py` na raiz
completam o cliente:

```text
api/
├── __init__.py          # re-exporta cada grupo como submódulo
├── _runtime.py          # ApiError + encode_query (compartilhados)
├── machines/
│   ├── __init__.py      # re-exporta schemas + o serviço
│   ├── schemas.py       # @dataclass de cada model do grupo
│   └── service.py       # classe MachinesService (1 método por rota)
└── tunnels/
    ├── __init__.py
    ├── schemas.py
    └── service.py
```

### `schemas.py` — um `@dataclass` por model

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class MachineResponseSchema:
    """Generated from the OpenAPI component."""

    id: str
    name: str
    machine_token: str
    is_active: bool
    created_at: str
    updated_at: str
    last_seen_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MachineResponseSchema":
        """Build the model from a decoded JSON object."""
        return cls(
            id=data.get("id"),
            name=data.get("name"),
            machine_token=data.get("machine_token"),
            is_active=data.get("is_active"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            last_seen_at=data.get("last_seen_at"),
        )
```

!!! note "Campos obrigatórios antes dos opcionais"
    Os campos `required` do schema vêm primeiro (sem default — regra de
    dataclass); os opcionais recebem `None` (ou `field(default_factory=list)`
    para arrays). Enums viram aliases `Literal[...]`.

### `service.py` — uma classe por grupo de rotas

```python
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from tempestweb.native.http import request

from .._runtime import ApiError, encode_query as _encode_query
from .schemas import MachineCreateSchema, MachineResponseSchema


class MachinesService:
    """Generated service for the "machines" routes."""

    def __init__(self, base_url: str = "", headers: dict[str, str] | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = headers or {}

    async def list_machines(self) -> list[MachineResponseSchema]:
        """GET /api/machines — List Machines"""
        url = f"{self._base_url}/api/machines"
        response = await request("GET", url, headers=self._headers)
        if not response.ok:
            raise ApiError(response.status, response.text, response.json_body)
        return [MachineResponseSchema.from_dict(item) for item in response.json_body]

    async def register_machine(self, body: MachineCreateSchema) -> MachineResponseSchema:
        """POST /api/machines — Register Machine"""
        url = f"{self._base_url}/api/machines"
        response = await request("POST", url, json=asdict(body), headers=self._headers)
        if not response.ok:
            raise ApiError(response.status, response.text, response.json_body)
        return MachineResponseSchema.from_dict(response.json_body)
```

Cada método:

- **path params** viram argumentos posicionais interpolados na URL;
- **request body** que referencia um model vira `body: <Model>` (serializado com
  `asdict`);
- **query params** viram um `params: dict[str, Any] | None` anexado à URL;
- respostas de sucesso viram o model tipado (single ou `list[...]`);
- respostas fora de 2xx levantam `ApiError`.

## Usando o cliente

Instancie o serviço com a base do backend e use dentro dos seus handlers:

```python
from api.machines import MachinesService, MachineCreateSchema

machines = MachinesService(base_url="https://api.exemplo.com")


async def carregar() -> None:
    todas = await machines.list_machines()
    nova = await machines.register_machine(MachineCreateSchema(name="casa-1"))
    print(nova.machine_token)
```

!!! tip "Headers por requisição"
    Passe `headers={"X-Token": "..."}` no construtor pra enviar autenticação em
    toda chamada — ideal pra um token de admin ou `Authorization`.

## Regenerando

O cliente é **gerado — não edite à mão**. Cada arquivo abre com o banner
`# Generated by tempestweb gen api`. Quando o backend muda, rode o comando de
novo apontando pro mesmo `--out`; os arquivos são reescritos.

!!! check "Recapitulando"
    - `tempestweb gen api <openapi> --out api` gera um cliente tipado por tag.
    - Models são `@dataclass` (funcionam nos três modos, inclusive transpile).
    - Serviços chamam `native.http` e levantam `ApiError` em falha.
    - Regenere quando a API mudar — nada de tipos à deriva.
