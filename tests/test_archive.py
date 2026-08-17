"""Cold archive of pruned receipts.

PROPERTY: when VERITAS_ARCHIVE_DIR is set, prune copies the receipt body
before deleting it. When the archive write fails, the live copy stays.
Unset archive keeps historical prune behaviour.

EVIDENCE LEVEL: L1. NOT IPFS, NOT S3 — local directory only.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from veritas.custody import CustodyStore, ReceiptPresence


def _save(store: CustodyStore, request_id: str) -> None:
    store.save({
        "request_id": request_id, "query": "q", "status": "completed",
        "custody_root": "sha256:x", "custody_valid": True, "evidence": [],
    })
    path = store.base_dir / f"{request_id}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["stored_at"] = "2020-01-01T00:00:00Z"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")


def test_prune_archives_then_tombstones(tmp_path, monkeypatch):
    archive = tmp_path / "cold"
    monkeypatch.setenv("VERITAS_ARCHIVE_DIR", str(archive))
    store = CustodyStore(str(tmp_path / "runtime"))
    _save(store, "r-old")
    report = store.prune(datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert report["deleted"] == 1
    assert report["archived"] == 1
    assert store.lookup("r-old") is ReceiptPresence.GONE
    copied = archive / "receipts" / "r-old.json"
    assert copied.is_file()
    body = json.loads(copied.read_text(encoding="utf-8"))
    assert body["request_id"] == "r-old"
    hashed = list((archive / "sha256").glob("*.json"))
    assert len(hashed) == 1


def test_unset_archive_still_prunes(tmp_path, monkeypatch):
    monkeypatch.delenv("VERITAS_ARCHIVE_DIR", raising=False)
    store = CustodyStore(str(tmp_path))
    _save(store, "r-old")
    report = store.prune(datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert report["deleted"] == 1
    assert report["archived"] == 0


def test_failed_archive_keeps_the_live_copy(tmp_path, monkeypatch):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("nope", encoding="utf-8")
    monkeypatch.setenv("VERITAS_ARCHIVE_DIR", str(blocker))
    store = CustodyStore(str(tmp_path / "runtime"))
    _save(store, "r-old")
    report = store.prune(datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert report["deleted"] == 0
    assert store.lookup("r-old") is ReceiptPresence.PRESENT
