"""Agent-hosted HTTPS: TLS files from env, passed through to uvicorn."""

from __future__ import annotations

import os

import pytest

from veritas.server import main, tls_files_from_env


@pytest.fixture(autouse=True)
def _clean_tls_env(monkeypatch):
    monkeypatch.delenv("VERITAS_TLS_CERT", raising=False)
    monkeypatch.delenv("VERITAS_TLS_KEY", raising=False)


def test_tls_files_from_env_none_when_unset():
    assert tls_files_from_env() is None


def test_tls_files_from_env_returns_temp_paths(tmp_path, monkeypatch):
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    cert.write_text("CERT", encoding="utf-8")
    key.write_text("KEY", encoding="utf-8")
    monkeypatch.setenv("VERITAS_TLS_CERT", str(cert))
    monkeypatch.setenv("VERITAS_TLS_KEY", str(key))
    assert tls_files_from_env() == (str(cert), str(key))


def test_tls_files_from_env_rejects_half_set(monkeypatch, tmp_path):
    monkeypatch.setenv("VERITAS_TLS_CERT", str(tmp_path / "cert.pem"))
    with pytest.raises(SystemExit, match="half-configured"):
        tls_files_from_env()


def test_main_passes_ssl_files_when_env_set(tmp_path, monkeypatch):
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    cert.write_text("CERT", encoding="utf-8")
    key.write_text("KEY", encoding="utf-8")
    monkeypatch.setenv("VERITAS_TLS_CERT", str(cert))
    monkeypatch.setenv("VERITAS_TLS_KEY", str(key))
    captured: dict = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", fake_run)
    monkeypatch.setattr("veritas.server.configure_logging", lambda: None)
    main([])
    assert captured["kwargs"]["ssl_certfile"] == str(cert)
    assert captured["kwargs"]["ssl_keyfile"] == str(key)
    assert captured["kwargs"]["host"] == "127.0.0.1"


def test_main_omits_ssl_when_tls_unset(monkeypatch):
    captured: dict = {}

    def fake_run(*args, **kwargs):
        captured["kwargs"] = kwargs

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", fake_run)
    monkeypatch.setattr("veritas.server.configure_logging", lambda: None)
    main([])
    assert "ssl_certfile" not in captured["kwargs"]
    assert "ssl_keyfile" not in captured["kwargs"]
    assert captured["kwargs"]["host"] == os.getenv("VERITAS_HOST", "127.0.0.1")
