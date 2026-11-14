"""Settings used when the app runs on a public server (see deploy/README.md)."""
import os
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("BSS_DATA_DIR", tempfile.mkdtemp(prefix="bss-test-"))

from fastapi.testclient import TestClient  # noqa: E402

from app import db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def fresh(monkeypatch, tmp_path):
    """An empty database, as on a server that was just installed."""
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "studio.db")
    monkeypatch.setattr(db, "IMG_DIR", tmp_path / "images")
    monkeypatch.setattr(db, "UPLOAD_DIR", tmp_path / "uploads")
    with TestClient(app) as c:
        yield c


def test_healthz_needs_no_login(fresh):
    r = fresh.get("/healthz")
    assert r.status_code == 200 and r.json()["ok"] is True and "version" in r.json()


def test_setup_code_protects_first_admin(fresh, monkeypatch):
    monkeypatch.setenv("BSS_SETUP_TOKEN", "orange-tiger-42")
    assert fresh.get("/api/status").json()["setup_token_required"] is True
    body = {"email": "boss@shop.in", "password": "longpassword", "name": "Boss"}
    assert fresh.post("/api/setup", json=body).status_code == 403
    assert fresh.post("/api/setup", json={**body, "setup_token": "wrong"}).status_code == 403
    assert fresh.post("/api/setup", json={**body, "setup_token": "orange-tiger-42"}).status_code == 200
    assert fresh.get("/api/status").json()["setup_token_required"] is False  # only matters before the first admin exists


def test_no_setup_code_means_open_setup(fresh, monkeypatch):
    monkeypatch.delenv("BSS_SETUP_TOKEN", raising=False)
    assert fresh.get("/api/status").json()["setup_token_required"] is False
    assert fresh.post("/api/setup", json={"email": "a@b.in", "password": "longpassword"}).status_code == 200


def test_secure_cookie_only_when_asked(fresh, monkeypatch):
    monkeypatch.delenv("BSS_SETUP_TOKEN", raising=False)
    monkeypatch.setenv("BSS_SECURE_COOKIES", "1")
    r = fresh.post("/api/setup", json={"email": "a@b.in", "password": "longpassword"})
    cookie = r.headers["set-cookie"].lower()
    assert "secure" in cookie and "httponly" in cookie and "samesite=lax" in cookie


def test_deploy_files_are_consistent():
    """The pipeline, server scripts and compose file must agree on names and paths."""
    root = Path(__file__).resolve().parent.parent
    wf = (root / ".github/workflows/deploy.yml").read_text()
    compose = (root / "deploy/docker-compose.prod.yml").read_text()
    deploy_sh = (root / "deploy/deploy.sh").read_text()
    for needle in ("/healthz", "BSS_VERSION"):
        assert needle in (root / "Dockerfile").read_text()
    assert "deploy.sh" in wf and "docker-compose.prod.yml" in deploy_sh
    assert "${BSS_IMAGE" in compose and "/srv/bath-studio/data:/app/data" in compose
    assert "--proxy-headers" in (root / "Dockerfile").read_text()
