from veritas.custody import CustodyLedger
from veritas.hashing import compute_content_hash, verify_content_hash


def test_hash_roundtrip():
    text = "Veritas evidence test"
    h = compute_content_hash(text)
    ok, _ = verify_content_hash(text, h)
    assert ok
    tampered, detail = verify_content_hash(text + "x", h)
    assert not tampered
    assert detail["expected"] == h

def test_ledger_chain():
    ledger = CustodyLedger()
    ledger.append("created", "test", {"msg": "one"})
    ledger.append("updated", "test", {"msg": "two"})
    assert ledger.verify_chain()
    assert ledger.root_hash() is not None

def test_ledger_detects_tampering():
    ledger = CustodyLedger()
    ledger.append("created", "test", {"msg": "one"})
    ledger.append("updated", "test", {"msg": "two"})
    ledger.events[0].payload["msg"] = "tampered"
    assert not ledger.verify_chain()


def test_delivered_chain_is_verifiable_without_the_seller():
    """Buyer re-runs chain validation on delivered bytes only."""
    from veritas.custody import verify_chain_records

    ledger = CustodyLedger()
    ledger.append("created", "catalog", {"query": "fed"})
    ledger.append("delivered", "catalog", {"stored": 1})
    records = ledger.to_list()
    assert verify_chain_records(records) is True
    assert records[-1]["event_hash"] == ledger.root_hash()

if __name__ == "__main__":
    test_hash_roundtrip()
    test_ledger_chain()
    test_ledger_detects_tampering()
    print("tests passed")
