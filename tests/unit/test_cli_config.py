"""Tests for ``tempestweb.cli.config`` (tempestweb.toml loading)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tempestweb.cli import ConfigError, ProjectConfig, load_config


def test_load_config_defaults_when_missing(tmp_path: Path) -> None:
    cfg = load_config(tmp_path)
    assert isinstance(cfg, ProjectConfig)
    assert cfg.name == tmp_path.name
    assert cfg.entrypoint == "app.py"
    assert cfg.mode == "wasm"
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 8000


def test_load_config_reads_fields(tmp_path: Path) -> None:
    (tmp_path / "tempestweb.toml").write_text(
        """
[project]
name = "acme"
entrypoint = "main.py"

[dev]
mode = "server"
host = "0.0.0.0"
port = 9001
""",
        encoding="utf-8",
    )
    cfg = load_config(tmp_path)
    assert cfg.name == "acme"
    assert cfg.entrypoint == "main.py"
    assert cfg.mode == "server"
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 9001


def test_entrypoint_path_is_absolute(tmp_path: Path) -> None:
    cfg = load_config(tmp_path)
    assert cfg.entrypoint_path == (tmp_path / "app.py").resolve()
    assert cfg.entrypoint_path.is_absolute()


def test_invalid_mode_raises(tmp_path: Path) -> None:
    (tmp_path / "tempestweb.toml").write_text(
        '[dev]\nmode = "native"\n', encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="invalid mode"):
        load_config(tmp_path)


def test_malformed_toml_raises(tmp_path: Path) -> None:
    (tmp_path / "tempestweb.toml").write_text("this = = broken", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid"):
        load_config(tmp_path)
