"""L1: plane agent money (VAAT) — not x402 settlement."""

from __future__ import annotations

import pytest

from veritas.agent_money import (
    CURRENCY,
    AgentMoneyLedger,
    ChainIntegrityError,
    InsufficientFunds,
)


def test_mint_transfer_and_chain(tmp_path):
    led = AgentMoneyLedger(tmp_path / "m.sqlite3")
    led.mint("overseer", 1000, memo="bootstrap")
    led.mint("money_loop", 500)
    led.transfer("overseer", "multiparty_trust", 100, memo="research stipend")
    assert led.balance("overseer") == 900
    assert led.balance("multiparty_trust") == 100
    assert led.verify_chain() is True
    snap = led.snapshot()
    assert snap["currency"] == CURRENCY
    assert snap["not_x402_settlement"] is True
    assert snap["journal_entries"] == 3
    led.close()


def test_insufficient_funds(tmp_path):
    led = AgentMoneyLedger(tmp_path / "m.sqlite3")
    led.mint("a", 10)
    with pytest.raises(InsufficientFunds):
        led.transfer("a", "b", 11)
    led.close()


def test_no_float_amounts(tmp_path):
    from veritas.agent_money import AgentMoneyError

    led = AgentMoneyLedger(tmp_path / "m.sqlite3")
    led.mint("a", 10)
    with pytest.raises(AgentMoneyError):
        led.transfer("a", "b", 1.5)  # type: ignore[arg-type]
    led.close()


def test_chain_detects_tamper(tmp_path):
    path = tmp_path / "m.sqlite3"
    led = AgentMoneyLedger(path)
    led.mint("a", 50)
    led.transfer("a", "b", 5)
    led.close()
    # Tamper raw journal
    import sqlite3

    conn = sqlite3.connect(str(path))
    conn.execute("UPDATE journal SET amount = 99 WHERE seq = 2")
    conn.commit()
    conn.close()
    led2 = AgentMoneyLedger(path)
    with pytest.raises(ChainIntegrityError):
        led2.verify_chain()
    led2.close()
