"""Shared durable store: two instances, one URL, one nonce.

PROPERTY: a nonce claimed through Ledger(A) is spent for Ledger(B) when
both honour the same VERITAS_DATABASE_URL. Unset URL keeps per-directory
isolation. In-memory sqlite is refused. Postgres extra is optional and
skipped when psycopg or a live DSN is absent.

EVIDENCE LEVEL: L1 for sqlite file URLs. NOT PROVEN: two processes behind
a real load balancer, multi-host Postgres HA.
"""

from __future__ import annotations

import os

import pytest

from veritas.credits import CreditLedger, InsufficientCredits
from veritas.ledger import Ledger
from veritas.store import (
    StoreUnavailable,
    parse_database_url,
    sqlite_file_url,
)

NONCE = "0x" + "ab" * 32
OFFER = {
    "network": "eip155:84532",
    "asset": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    "amount": "10000",
    "pay_to": "0x" + "11" * 20,
    "price": "$0.01",
    "payer": "0x" + "22" * 20,
}


def test_unset_url_keeps_per_directory_isolation(tmp_path, monkeypatch):
    monkeypatch.delenv("VERITAS_DATABASE_URL", raising=False)
    a = Ledger(tmp_path / "a")
    b = Ledger(tmp_path / "b")
    assert a.claim(NONCE, "req-a", **OFFER).claimed is True
    assert b.claim(NONCE, "req-b", **OFFER).claimed is True


def test_sqlite_url_shares_nonce_claims_across_base_dirs(tmp_path, monkeypatch):
    shared = tmp_path / "shared.sqlite3"
    monkeypatch.setenv("VERITAS_DATABASE_URL", sqlite_file_url(shared))
    a = Ledger(tmp_path / "a")
    b = Ledger(tmp_path / "b")
    first = a.claim(NONCE, "req-a", **OFFER)
    second = b.claim(NONCE, "req-b", **OFFER)
    assert first.claimed is True
    assert second.claimed is False
    assert second.reason == "payment_nonce_already_spent"
    assert b.authorization(NONCE) is not None
    assert b.authorization(NONCE).request_id == "req-a"


def test_sqlite_url_shares_credit_balances(tmp_path, monkeypatch):
    shared = tmp_path / "shared.sqlite3"
    monkeypatch.setenv("VERITAS_DATABASE_URL", sqlite_file_url(shared))
    account = "0x" + "11" * 20
    a = CreditLedger(tmp_path / "a")
    b = CreditLedger(tmp_path / "b")
    a.grant(account, 500, note="shared")
    assert b.balance(account) == 500
    b.debit(account, 200, request_id="r1")
    assert a.balance(account) == 300
    with pytest.raises(InsufficientCredits):
        a.debit(account, 400, request_id="r2")


def test_relative_and_absolute_sqlite_urls_parse(tmp_path):
    rel = parse_database_url("sqlite:///relative/ledger.sqlite3")
    assert rel is not None
    assert rel.kind == "sqlite"
    assert rel.path is not None
    assert not rel.path.is_absolute() or rel.path.as_posix().endswith("relative/ledger.sqlite3")

    abs_path = tmp_path / "abs.sqlite3"
    parsed = parse_database_url(sqlite_file_url(abs_path))
    assert parsed is not None
    assert parsed.kind == "sqlite"
    assert parsed.path == abs_path


def test_memory_sqlite_is_refused():
    with pytest.raises(StoreUnavailable):
        parse_database_url("sqlite:///:memory:")


def test_unknown_scheme_is_refused():
    with pytest.raises(StoreUnavailable):
        parse_database_url("mysql://localhost/veritas")


def test_empty_url_means_per_instance(monkeypatch):
    monkeypatch.delenv("VERITAS_DATABASE_URL", raising=False)
    assert parse_database_url() is None
    monkeypatch.setenv("VERITAS_DATABASE_URL", "   ")
    assert parse_database_url() is None


@pytest.mark.skipif(
    os.getenv("VERITAS_TEST_POSTGRES_URL", "").strip() == "",
    reason="no VERITAS_TEST_POSTGRES_URL; postgres extra is optional",
)
def test_postgres_url_shares_nonce_when_dsn_provided(monkeypatch):
    psycopg = pytest.importorskip("psycopg")
    dsn = os.environ["VERITAS_TEST_POSTGRES_URL"]
    monkeypatch.setenv("VERITAS_DATABASE_URL", dsn)
    a = Ledger("/unused-a")
    b = Ledger("/unused-b")
    nonce = "0x" + "ef" * 32
    assert a.claim(nonce, "pg-a", **OFFER).claimed is True
    second = b.claim(nonce, "pg-b", **OFFER)
    assert second.claimed is False
    assert second.reason == "payment_nonce_already_spent"
    del psycopg
