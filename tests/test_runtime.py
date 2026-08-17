"""O5: the runtime directory is absolute and /readyz fails if it cannot be written."""

from __future__ import annotations

import importlib
import os

from fastapi.testclient import TestClient

from veritas.ledger import Ledger
from veritas.runtime import (
    bind_agent_runtime,
    default_runtime_dir,
    probe_runtime_dir,
    resolve_runtime_dir,
)


def test_default_runtime_dir_is_never_cwd_relative(monkeypatch, tmp_path):
    monkeypatch.delenv("VERITAS_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("VERITAS_AGENT_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    default = default_runtime_dir()
    assert default.is_absolute()
    assert default.name == "runtime"
    resolved = resolve_runtime_dir()
    assert resolved.is_absolute()
    assert resolved == default.resolve()
    assert resolved != (tmp_path / ".veritas_runtime").resolve()


def test_env_and_agent_home_resolve_absolute(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path / "from-env"))
    assert resolve_runtime_dir() == (tmp_path / "from-env").resolve()
    monkeypatch.delenv("VERITAS_RUNTIME_DIR")
    monkeypatch.setenv("VERITAS_AGENT_HOME", str(tmp_path / "agent"))
    assert resolve_runtime_dir() == (tmp_path / "agent" / "runtime").resolve()


def test_legacy_cwd_dir_is_bound_absolute(tmp_path, monkeypatch):
    monkeypatch.delenv("VERITAS_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("VERITAS_AGENT_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    legacy = tmp_path / ".veritas_runtime"
    legacy.mkdir()
    resolved = resolve_runtime_dir()
    assert resolved == legacy.resolve()
    assert resolved.is_absolute()


def test_explicit_base_dir_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path / "env"))
    other = tmp_path / "explicit"
    assert resolve_runtime_dir(other) == other.resolve()


def test_ledger_uses_resolver(tmp_path):
    ledger = Ledger(tmp_path / "led")
    assert ledger.base_dir.is_absolute()
    assert ledger.base_dir == (tmp_path / "led").resolve()


def test_bind_agent_runtime_setdefaults(tmp_path, monkeypatch):
    monkeypatch.delenv("VERITAS_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("VERITAS_AGENT_HOME", raising=False)
    bound = bind_agent_runtime(tmp_path / "home")
    assert os.environ["VERITAS_AGENT_HOME"] == str((tmp_path / "home").resolve())
    assert os.environ["VERITAS_RUNTIME_DIR"] == str((tmp_path / "home" / "runtime").resolve())
    assert bound == (tmp_path / "home" / "runtime").resolve()
    monkeypatch.delenv("VERITAS_AGENT_HOME", raising=False)
    monkeypatch.delenv("VERITAS_RUNTIME_DIR", raising=False)


def test_probe_reports_unwritable(tmp_path):
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    ok, reason = probe_runtime_dir(blocked)
    assert ok is False
    assert reason is not None
    assert reason.startswith("runtime_dir_unwritable:")
    assert "/" not in reason.split(":", 1)[1]


def test_readyz_is_not_ready_when_runtime_dir_is_unwritable(tmp_path, monkeypatch):
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(blocked))
    monkeypatch.delenv("VERITAS_REQUIRE_PAYMENT", raising=False)
    import veritas.server as server

    importlib.reload(server)
    ready = TestClient(server.app).get("/readyz")
    assert ready.status_code == 503
    body = ready.json()
    assert body["ready"] is False
    assert any(str(r).startswith("runtime_dir_unwritable:") for r in body["reasons"])
