# Generate a client from OpenAPI (`tempestweb gen api`)

!!! tip "What you'll learn"
    How to get a **typed client** — models + services — straight from your
    backend's `openapi.json`, with no hand-written `fetch` and no types drifting
    from the API. 🚀

If your backend is FastAPI (or anything exposing **OpenAPI 3.x**), `tempestweb
gen api` reads the spec and **generates the client for you**, the Tempest way:
one package per **route group** (the operation's `tag`), each with
**`@dataclass` models** and a **service class** whose methods call
[`native.http`](native-reference.md). It is the Python analog of
`tempest-react-sdk`'s `tempest gen api` (which emits Zod + TS).

## Why dataclasses (not pydantic)

!!! info "One client, three modes"
    The generated client runs in all three tempestweb modes — including **Mode C
    (transpile)**, which transcribes your Python to JavaScript. Transpile
    supports `@dataclass` but **not** pydantic (which needs a Python runtime). So
    models are emitted as dataclasses with a `from_dict` — identical behavior
    under WASM, server, and transpile.

## Generating

Point it at your running backend's `/openapi.json`, or at a saved file:

```bash
# from a running FastAPI server
tempestweb gen api http://127.0.0.1:8000/openapi.json --out api

# or from a file
tempestweb gen api ./openapi.json --out api
```

The `--out` flag picks the output directory (default: `./api`).

## What is generated

Each **tag** produces a package; a root `_runtime.py` and `__init__.py` complete
the client:

```text
api/
├── __init__.py          # re-exports each group as a submodule
├── _runtime.py          # ApiError + encode_query (shared)
├── machines/
│   ├── __init__.py      # re-exports schemas + the service
│   ├── schemas.py       # one @dataclass per model in the group
│   └── service.py       # MachinesService class (one method per route)
└── tunnels/
    ├── __init__.py
    ├── schemas.py
    └── service.py
```

### `schemas.py` — one `@dataclass` per model

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

!!! note "Required fields before optional ones"
    A schema's `required` fields come first (no default — dataclass rule);
    optional ones default to `None` (or `field(default_factory=list)` for
    arrays). Enums become `Literal[...]` aliases.

### `service.py` — one class per route group

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

Each method:

- **path params** become positional arguments interpolated into the URL;
- a **request body** that references a model becomes `body: <Model>` (serialized
  with `asdict`);
- **query params** become a `params: dict[str, Any] | None` appended to the URL;
- success responses become the typed model (single or `list[...]`);
- non-2xx responses raise `ApiError`.

## Using the client

Instantiate the service with the backend base URL and use it in your handlers:

```python
from api.machines import MachinesService, MachineCreateSchema

machines = MachinesService(base_url="https://api.example.com")


async def load() -> None:
    all_machines = await machines.list_machines()
    created = await machines.register_machine(MachineCreateSchema(name="home-1"))
    print(created.machine_token)
```

!!! tip "Per-request headers"
    Pass `headers={"X-Token": "..."}` to the constructor to send auth on every
    call — ideal for an admin token or `Authorization`.

## Regenerating

The client is **generated — do not edit by hand**. Every file opens with the
`# Generated by tempestweb gen api` banner. When the backend changes, run the
command again against the same `--out`; the files are rewritten.

!!! check "Recap"
    - `tempestweb gen api <openapi> --out api` generates a typed per-tag client.
    - Models are `@dataclass` (work in all three modes, transpile included).
    - Services call `native.http` and raise `ApiError` on failure.
    - Regenerate when the API changes — no drifting types.
