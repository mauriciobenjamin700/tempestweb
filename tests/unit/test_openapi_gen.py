"""Unit tests for the ``tempestweb gen api`` OpenAPI client generator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tempestweb.cli.commands.gen import GenError, generate_api
from tempestweb.cli.openapi import generate, load_spec
from tempestweb.cli.openapi.load import SpecLoadError

_SPEC: dict[str, Any] = {
    "openapi": "3.1.0",
    "paths": {
        "/api/users": {
            "get": {
                "tags": ["users"],
                "operationId": "list_users",
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"$ref": "#/components/schemas/User"},
                                }
                            }
                        }
                    }
                },
            },
            "post": {
                "tags": ["users"],
                "operationId": "create_user",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/UserCreate"}
                        }
                    }
                },
                "responses": {
                    "201": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/User"}
                            }
                        }
                    }
                },
            },
        },
        "/api/users/{user_id}": {
            "get": {
                "tags": ["users"],
                "operationId": "get_user",
                "parameters": [
                    {
                        "name": "user_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    },
                    {
                        "name": "expand",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "boolean"},
                    },
                ],
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/User"}
                            }
                        }
                    }
                },
            }
        },
    },
    "components": {
        "schemas": {
            "Role": {"type": "string", "enum": ["admin", "member"]},
            "User": {
                "type": "object",
                "required": ["id", "email"],
                "properties": {
                    "id": {"type": "integer"},
                    "email": {"type": "string", "format": "email"},
                    "role": {"$ref": "#/components/schemas/Role"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "bio": {"type": "string", "nullable": True},
                },
            },
            "UserCreate": {
                "type": "object",
                "required": ["email"],
                "properties": {
                    "email": {"type": "string"},
                    "name": {"type": "string"},
                },
            },
        }
    },
}


def test_groups_by_tag() -> None:
    """Operations sharing a tag land in one package."""
    files, tags = generate(_SPEC)
    assert tags == ["users"]
    assert "users/schemas.py" in files
    assert "users/service.py" in files
    assert "users/__init__.py" in files
    assert "_runtime.py" in files


def test_dataclass_field_ordering_and_defaults() -> None:
    """Required fields precede optional ones; arrays default to a factory."""
    files, _ = generate(_SPEC)
    schemas = files["users/schemas.py"]
    assert "id: int" in schemas
    assert "email: str" in schemas
    assert "bio: str | None = None" in schemas
    assert "tags: list[str] = field(default_factory=list)" in schemas
    assert schemas.index("id: int") < schemas.index("bio: str | None = None")


def test_optional_scalar_field_admits_none() -> None:
    """A property the spec does not require is typed ``T | None``, never ``T``.

    ``role: Role = None`` type-checked as an assignment error in every project
    that imported the client — the annotation promised a value the API never
    guaranteed.
    """
    schemas = generate(_SPEC)[0]["users/schemas.py"]
    assert "role: Role | None = None" in schemas
    assert "role: Role = None" not in schemas


def test_enum_becomes_literal_alias() -> None:
    """A string enum component becomes a double-quoted ``Literal`` alias."""
    files, _ = generate(_SPEC)
    schemas = files["users/schemas.py"]
    assert 'Role = Literal["admin", "member"]' in schemas


def test_required_properties_are_read_by_key() -> None:
    """``from_dict`` indexes required properties and ``.get``s optional ones.

    ``data.get(...)`` is typed ``Any | None``, so every required field of every
    model used to be an ``arg-type`` error at the call site — and a truncated
    response built the dataclass with ``None`` under a non-optional annotation.
    """
    schemas = generate(_SPEC)[0]["users/schemas.py"]
    assert 'id=data["id"]' in schemas
    assert 'email=data["email"]' in schemas
    assert 'bio=data.get("bio")' in schemas


def test_generated_modules_carry_no_unused_noqa() -> None:
    """The emitter never writes a pragma, so RUF100 has nothing to report."""
    files, _ = generate(_SPEC)
    for contents in files.values():
        assert "noqa" not in contents


def test_service_method_shapes() -> None:
    """Service methods carry path/body/query args and typed returns."""
    service = generate(_SPEC)[0]["users/service.py"]
    assert "class UsersService:" in service
    assert "@dataclass" in service
    assert "async def list_users(self) -> list[User]:" in service
    assert "return [User.from_dict(item) for item in response.json_body]" in service
    assert "async def create_user(self, body: UserCreate) -> User:" in service
    assert "json=body.to_dict()" in service
    assert "async def get_user(" in service
    assert "user_id: int," in service
    assert "params: dict[str, Any] | None = None," in service
    assert "url += _encode_query(params or {})" in service


def test_generate_api_writes_files(tmp_path: Path) -> None:
    """``generate_api`` writes a compilable client to disk."""
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text(json.dumps(_SPEC), encoding="utf-8")
    out = tmp_path / "client"
    result = generate_api(str(spec_path), out=str(out))
    assert result.tags == ["users"]
    assert (out / "users" / "service.py").is_file()
    assert (out / "_runtime.py").is_file()
    compile((out / "users" / "schemas.py").read_text(), "schemas.py", "exec")
    compile((out / "users" / "service.py").read_text(), "service.py", "exec")


def test_generate_api_rejects_empty_spec(tmp_path: Path) -> None:
    """A spec with no operations raises a GenError."""
    spec_path = tmp_path / "empty.json"
    spec_path.write_text(
        json.dumps({"openapi": "3.1.0", "paths": {}}), encoding="utf-8"
    )
    with pytest.raises(GenError):
        generate_api(str(spec_path), out=str(tmp_path / "out"))


def test_load_spec_missing_file() -> None:
    """Loading a nonexistent file raises SpecLoadError."""
    with pytest.raises(SpecLoadError):
        load_spec("/no/such/openapi.json")
