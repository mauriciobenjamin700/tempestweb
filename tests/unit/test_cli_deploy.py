"""Tests for ``tempestweb deploy`` (cli.commands.deploy) — Track S / S5."""

from __future__ import annotations

from pathlib import Path

import pytest

from tempestweb.cli import (
    DEPLOY_FILES,
    DeployError,
    render_deploy_files,
    scaffold_deploy,
    scaffold_project,
)


def _project(tmp_path: Path) -> Path:
    return scaffold_project("deployme", parent=tmp_path).root


def test_render_covers_every_file(tmp_path: Path) -> None:
    files = render_deploy_files(_project(tmp_path))
    assert set(files) == set(DEPLOY_FILES)
    for body in files.values():
        assert body


def test_nginx_has_ws_upgrade_and_sticky(tmp_path: Path) -> None:
    conf = render_deploy_files(_project(tmp_path))["nginx.conf"]
    assert "ip_hash;" in conf
    assert "proxy_set_header Upgrade $http_upgrade;" in conf
    assert 'proxy_set_header Connection "upgrade";' in conf
    assert "proxy_buffering off;" in conf
    assert "location = /health" in conf
    # Brace-balanced (no f-string escaping leaks).
    assert "{{" not in conf and conf.count("{") == conf.count("}")


def test_nginx_http_only_by_default(tmp_path: Path) -> None:
    conf = render_deploy_files(_project(tmp_path))["nginx.conf"]
    assert "listen 80;" in conf
    assert "listen 443" not in conf
    assert "ssl_certificate" not in conf


def test_nginx_tls_block(tmp_path: Path) -> None:
    conf = render_deploy_files(
        _project(tmp_path), server_name="app.example.com", tls=True
    )["nginx.conf"]
    assert "server_name app.example.com;" in conf
    assert "listen 443 ssl;" in conf
    assert "return 301 https://$host$request_uri;" in conf
    assert "ssl_certificate_key /etc/nginx/certs/privkey.pem;" in conf


def test_no_sticky_drops_ip_hash(tmp_path: Path) -> None:
    conf = render_deploy_files(_project(tmp_path), sticky=False)["nginx.conf"]
    assert "ip_hash;" not in conf
    assert "RedisSessionRouter" in conf  # explains the round-robin choice


def test_replicas_expand_upstream(tmp_path: Path) -> None:
    conf = render_deploy_files(_project(tmp_path), replicas=3)["nginx.conf"]
    assert "server app:8000;" in conf
    assert "server app1:8000;" in conf
    assert "server app2:8000;" in conf


def test_replicas_define_matching_compose_services(tmp_path: Path) -> None:
    """The compose defines every app replica the nginx upstream references."""
    files = render_deploy_files(_project(tmp_path), replicas=3)
    compose = files["docker-compose.yml"]
    # Services app, app1, app2 exist so the nginx `server appN` hosts resolve.
    assert "\n  app:\n" in compose
    assert "\n  app1:\n" in compose
    assert "\n  app2:\n" in compose
    # The proxy depends on all of them.
    assert "      - app1\n" in compose and "      - app2\n" in compose


def test_single_replica_compose_has_one_app(tmp_path: Path) -> None:
    compose = render_deploy_files(_project(tmp_path))["docker-compose.yml"]
    assert "\n  app:\n" in compose
    assert "app1:" not in compose


def test_port_from_config(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "tempestweb.toml").write_text(
        '[project]\nname = "deployme"\n\n[dev]\nport = 9000\n', encoding="utf-8"
    )
    files = render_deploy_files(root)
    assert "server app:9000;" in files["nginx.conf"]
    assert "EXPOSE 9000" in files["Dockerfile"]
    assert '"--port", "9000"' in files["Dockerfile"]


def test_zero_replicas_rejected(tmp_path: Path) -> None:
    with pytest.raises(DeployError):
        render_deploy_files(_project(tmp_path), replicas=0)


def test_scaffold_writes_files(tmp_path: Path) -> None:
    root = _project(tmp_path)
    result = scaffold_deploy(root)
    assert result.out_dir == (root / "deploy").resolve()
    for name in DEPLOY_FILES:
        assert (result.out_dir / name).is_file()


def test_scaffold_refuses_overwrite_without_force(tmp_path: Path) -> None:
    root = _project(tmp_path)
    scaffold_deploy(root)
    with pytest.raises(DeployError, match="already exists"):
        scaffold_deploy(root)
    # force overwrites cleanly.
    assert scaffold_deploy(root, force=True).files == DEPLOY_FILES
