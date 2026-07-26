from veritas.custody import CustodyLedger
from veritas.hashing import content_hash, verify_content_hash

def test_hash_roundtrip():
    text = "Veritas evidence test"
    h = content_hash(text)
    assert verify_content_hash(text, h)
    assert not verify_content_hash(text + "x", h)

def test_ledger_chain():
    ledger = CustodyLedger()
    ledger.append("created", "test", {"msg": "one"})
    ledger.append("updated", "test", {"msg": "two"})
    assert ledger.verify_chain()
    assert ledger.root_hash() is not None

if __name__ == "__main__":
    test_hash_roundtrip()
    test_ledger_chain()
    print("tests passed")
