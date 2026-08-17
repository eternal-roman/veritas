"""shared_rate_limited: no free pass when the shared store is down.

PROPERTY: if VERITAS_DATABASE_URL is set but parse/connect/exec fails,
repeated calls still trip a process-local limiter after `limit` hits.
Unset DATABASE_URL still returns False (server.py owns that path).

EVIDENCE LEVEL: L1. NOT PROVEN: two processes behind a real balancer,
Postgres HA, or that the fallback window matches wall-clock across
process restarts (it cannot — it is process-local).
"""

from __future__ import annotations

from veritas.store import (
    StoreUnavailable,
    shared_rate_limited,
    sqlite_file_url,
)


def test_unusable_url_still_trips_local_fallback(monkeypatch):
    """:memory: is refused at parse time. That is not a free pass."""
    monkeypatch.setenv("VERITAS_DATABASE_URL", "sqlite:///:memory:")
    caller = "fallback-memory"
    now = 1_000_000.0
    assert shared_rate_limited(caller, limit=3, window_seconds=60, now=now) is False
    assert shared_rate_limited(caller, limit=3, window_seconds=60, now=now + 1) is False
    assert shared_rate_limited(caller, limit=3, window_seconds=60, now=now + 2) is False
    assert shared_rate_limited(caller, limit=3, window_seconds=60, now=now + 3) is True


def test_connect_failure_still_trips_local_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_DATABASE_URL", sqlite_file_url(tmp_path / "shared.sqlite3"))

    def boom(_target):
        raise StoreUnavailable("down")

    monkeypatch.setattr("veritas.store.connect_target", boom)
    caller = "fallback-connect"
    now = 2_000_000.0
    assert shared_rate_limited(caller, limit=2, window_seconds=30, now=now) is False
    assert shared_rate_limited(caller, limit=2, window_seconds=30, now=now + 1) is False
    assert shared_rate_limited(caller, limit=2, window_seconds=30, now=now + 2) is True


def test_exec_failure_still_trips_local_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_DATABASE_URL", sqlite_file_url(tmp_path / "shared.sqlite3"))

    class _Dead:
        def executescript(self, _script):
            raise RuntimeError("exec-down")

        def execute(self, *_a, **_k):
            raise RuntimeError("exec-down")

        def close(self):
            return None

    monkeypatch.setattr("veritas.store.connect_target", lambda _t: _Dead())
    caller = "fallback-exec"
    now = 3_000_000.0
    assert shared_rate_limited(caller, limit=1, window_seconds=10, now=now) is False
    assert shared_rate_limited(caller, limit=1, window_seconds=10, now=now + 1) is True


def test_unset_url_does_not_consume_local_fallback(monkeypatch):
    """server.py owns the no-URL path. This function must stay a no-op."""
    monkeypatch.delenv("VERITAS_DATABASE_URL", raising=False)
    caller = "unset-path"
    now = 4_000_000.0
    assert all(
        shared_rate_limited(caller, limit=1, window_seconds=60, now=now + i) is False
        for i in range(8)
    )


def test_fallback_window_expires(monkeypatch):
    monkeypatch.setenv("VERITAS_DATABASE_URL", "sqlite:///:memory:")
    caller = "fallback-window"
    now = 5_000_000.0
    assert shared_rate_limited(caller, limit=2, window_seconds=10, now=now) is False
    assert shared_rate_limited(caller, limit=2, window_seconds=10, now=now + 1) is False
    assert shared_rate_limited(caller, limit=2, window_seconds=10, now=now + 2) is True
    assert shared_rate_limited(caller, limit=2, window_seconds=10, now=now + 12) is False


def test_fallback_callers_are_independent(monkeypatch):
    monkeypatch.setenv("VERITAS_DATABASE_URL", "sqlite:///:memory:")
    now = 6_000_000.0
    assert shared_rate_limited("alice", limit=1, window_seconds=60, now=now) is False
    assert shared_rate_limited("alice", limit=1, window_seconds=60, now=now + 1) is True
    assert shared_rate_limited("bob", limit=1, window_seconds=60, now=now + 1) is False


def test_working_shared_store_still_limits(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_DATABASE_URL", sqlite_file_url(tmp_path / "shared.sqlite3"))
    caller = "shared-ok"
    now = 7_000_000.0
    assert shared_rate_limited(caller, limit=2, window_seconds=60, now=now) is False
    assert shared_rate_limited(caller, limit=2, window_seconds=60, now=now + 1) is False
    assert shared_rate_limited(caller, limit=2, window_seconds=60, now=now + 2) is True
