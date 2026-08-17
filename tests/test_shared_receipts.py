"""Shared custody receipts: two nodes, one DATABASE_URL.

PROPERTY: when VERITAS_DATABASE_URL is set, a receipt saved on
CustodyStore(A) is loadable on CustodyStore(B) with a different runtime
dir. A tombstone on A is gone on B. File backend stays authoritative
locally. Shared-write failure does not fail a paid save. L6 shape is
unchanged (query_hash, no free-text question).

EVIDENCE LEVEL: L1 for sqlite file URLs. NOT PROVEN: two processes
behind a real load balancer, multi-host Postgres HA.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from veritas.custody import CustodyStore, ReceiptPresence
from veritas.hashing import compute_content_hash
from veritas.store import (
    StoreUnavailable,
    load_shared_receipt,
    probe_shared_store,
    sqlite_file_url,
)


def _result(request_id: str, query: str = "https://example.com/origin") -> dict:
    return {
        "request_id": request_id,
        "query": query,
        "status": "completed",
        "custody_root": "sha256:x",
        "custody_valid": True,
        "evidence": [{"content_hash": "sha256:" + "ab" * 32}],
    }


def _backdate(store: CustodyStore, request_id: str, stored_at: str) -> None:
    path = store.base_dir / f"{request_id}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["stored_at"] = stored_at
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")


def test_save_on_a_is_loadable_on_b_via_shared_store(tmp_path, monkeypatch):
    shared = tmp_path / "shared.sqlite3"
    monkeypatch.setenv("VERITAS_DATABASE_URL", sqlite_file_url(shared))
    a = CustodyStore(str(tmp_path / "node-a"))
    b = CustodyStore(str(tmp_path / "node-b"))

    saved = a.save(_result("req-shared-1"))
    assert saved["persisted"] is True
    assert (tmp_path / "node-a" / "receipts" / "req-shared-1.json").is_file()
    assert not (tmp_path / "node-b" / "receipts" / "req-shared-1.json").exists()

    assert b.lookup("req-shared-1") is ReceiptPresence.PRESENT
    loaded = b.load("req-shared-1")
    assert loaded is not None
    assert loaded["request_id"] == "req-shared-1"
    assert loaded["custody_root"] == "sha256:x"
    assert loaded["query"] == "https://example.com/origin"


def test_tombstone_on_a_is_gone_on_b(tmp_path, monkeypatch):
    shared = tmp_path / "shared.sqlite3"
    monkeypatch.setenv("VERITAS_DATABASE_URL", sqlite_file_url(shared))
    a = CustodyStore(str(tmp_path / "node-a"))
    b = CustodyStore(str(tmp_path / "node-b"))
    assert a.save(_result("req-gone-1"))["persisted"] is True
    _backdate(a, "req-gone-1", "2020-01-01T00:00:00Z")

    report = a.prune(datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert report["tombstoned"] == 1
    assert a.lookup("req-gone-1") is ReceiptPresence.GONE
    assert a.load("req-gone-1") is None

    assert b.lookup("req-gone-1") is ReceiptPresence.GONE
    assert b.load("req-gone-1") is None


def test_unset_url_keeps_per_directory_receipt_isolation(tmp_path, monkeypatch):
    monkeypatch.delenv("VERITAS_DATABASE_URL", raising=False)
    a = CustodyStore(str(tmp_path / "node-a"))
    b = CustodyStore(str(tmp_path / "node-b"))
    assert a.save(_result("req-local-only"))["persisted"] is True
    assert a.lookup("req-local-only") is ReceiptPresence.PRESENT
    assert b.lookup("req-local-only") is ReceiptPresence.UNKNOWN
    assert b.load("req-local-only") is None


def test_shared_body_is_l6_redacted(tmp_path, monkeypatch):
    """The shared row is the same redacted-on-wire shape the file store writes."""
    shared = tmp_path / "shared.sqlite3"
    monkeypatch.setenv("VERITAS_DATABASE_URL", sqlite_file_url(shared))
    a = CustodyStore(str(tmp_path / "node-a"))
    b = CustodyStore(str(tmp_path / "node-b"))
    question = "buyer-only research question about a merger"
    saved = a.save(_result("req-l6-shared", query=question))
    assert saved["persisted"] is True
    assert "query" not in saved
    assert saved["query_hash"] == compute_content_hash(question)

    file_body = json.loads(
        (tmp_path / "node-a" / "receipts" / "req-l6-shared.json").read_text(encoding="utf-8")
    )
    assert "query" not in file_body
    assert file_body["query_hash"] == compute_content_hash(question)

    row = load_shared_receipt("req-l6-shared")
    assert row is not None
    assert row.gone is False
    parsed = json.loads(row.body)
    assert "query" not in parsed
    assert parsed["query_hash"] == compute_content_hash(question)
    assert question not in row.body

    loaded = b.load("req-l6-shared")
    assert loaded is not None
    assert "query" not in loaded
    assert loaded["query_hash"] == compute_content_hash(question)
    assert question not in json.dumps(loaded)


def test_shared_write_failure_does_not_fail_paid_save(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_DATABASE_URL", sqlite_file_url(tmp_path / "shared.sqlite3"))

    def boom(_target):
        raise StoreUnavailable("down")

    monkeypatch.setattr("veritas.store.connect_target", boom)
    store = CustodyStore(str(tmp_path / "node-a"))
    record = store.save(_result("req-file-only"))
    assert record["persisted"] is True
    assert store.load("req-file-only")["request_id"] == "req-file-only"
    assert store.lookup("req-file-only") is ReceiptPresence.PRESENT


def test_unsafe_id_never_reaches_shared_store(tmp_path, monkeypatch):
    monkeypatch.setenv("VERITAS_DATABASE_URL", sqlite_file_url(tmp_path / "shared.sqlite3"))
    a = CustodyStore(str(tmp_path / "node-a"))
    b = CustodyStore(str(tmp_path / "node-b"))
    record = a.save(_result("../escaped"))
    assert record["persisted"] is False
    assert load_shared_receipt("../escaped") is None
    assert b.lookup("../escaped") is ReceiptPresence.UNKNOWN
    assert b.load("../escaped") is None


def test_resave_clears_shared_tombstone(tmp_path, monkeypatch):
    shared = tmp_path / "shared.sqlite3"
    monkeypatch.setenv("VERITAS_DATABASE_URL", sqlite_file_url(shared))
    a = CustodyStore(str(tmp_path / "node-a"))
    b = CustodyStore(str(tmp_path / "node-b"))
    a.save(_result("req-revive"))
    _backdate(a, "req-revive", "2020-01-01T00:00:00Z")
    a.prune(datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert b.lookup("req-revive") is ReceiptPresence.GONE

    a.save(_result("req-revive"))
    assert b.lookup("req-revive") is ReceiptPresence.PRESENT
    assert b.load("req-revive")["request_id"] == "req-revive"


def test_probe_shared_store_matches_url_usability(tmp_path, monkeypatch):
    monkeypatch.delenv("VERITAS_DATABASE_URL", raising=False)
    assert probe_shared_store() is False
    monkeypatch.setenv("VERITAS_DATABASE_URL", sqlite_file_url(tmp_path / "ok.sqlite3"))
    assert probe_shared_store() is True
    monkeypatch.setenv("VERITAS_DATABASE_URL", "sqlite:///:memory:")
    assert probe_shared_store() is False


def test_local_file_wins_over_shared_row(tmp_path, monkeypatch):
    """Read: file first, then shared. A local body is not overwritten by a sibling."""
    shared = tmp_path / "shared.sqlite3"
    monkeypatch.setenv("VERITAS_DATABASE_URL", sqlite_file_url(shared))
    a = CustodyStore(str(tmp_path / "node-a"))
    b = CustodyStore(str(tmp_path / "node-b"))
    a.save({**_result("req-conflict"), "status": "completed"})
    # B writes its own file for the same id (different runtime dir).
    monkeypatch.delenv("VERITAS_DATABASE_URL", raising=False)
    b_local = CustodyStore(str(tmp_path / "node-b"))
    b_local.save({**_result("req-conflict"), "status": "refused"})
    monkeypatch.setenv("VERITAS_DATABASE_URL", sqlite_file_url(shared))
    b_again = CustodyStore(str(tmp_path / "node-b"))
    loaded = b_again.load("req-conflict")
    assert loaded is not None
    assert loaded["status"] == "refused"
    # unused `b` kept so the two-dir layout is obvious to the next reader
    assert b.base_dir != a.base_dir
