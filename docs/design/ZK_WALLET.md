# Hiding Wallet Commitments for JIT Packets

## Goal

Keep the receiving wallet **private** in the public JIT Disposable Packet while still allowing the holder to prove knowledge of the opening and to reveal the address only at settlement.

This is **not** a zero-knowledge SNARK. The module name `zk_wallet` is historical; the implementation is a **hiding commitment + keyed MAC proof of knowledge** (`hiding-commit-hmac-v2`).

## Construction (current)

1. **Commitment**  
   `C = HMAC(salt, address || network)` with a **private** salt.  
   Published in the packet instead of the raw `pay_to`. (Earlier code published the salt and was not hiding.)

2. **Proof of knowledge**  
   `HMAC(salt, "pok|" || challenge)` with a verifier-chosen challenge.  
   Cannot be forged without the salt; requires the opening for verification (not third-party ZK).

3. **Stealth / one-time address**  
   **Not implemented.** The old hash-derived "address" had no private key and would burn funds. `derive_stealth_address` raises `NotImplementedError` and points to ERC-5564.

4. **Selective reveal**  
   At settlement the holder opens the commitment; third parties can check `verify_revealed` once salt and address are disclosed.

## Integration with JDP

```text
Offer packet (public):
  - agent_id (salted)
  - wallet_commitment  ← instead of clear pay_to
  - network, price, facilitator
  - capability / schema
  - proof

Private (seller only):
  - opening material
  - real address
```

When the buyer accepts and pays, settlement can use the opened address or a stealth address derived for that session.

## Limits of the current prototype

- Commitment + keyed PoK only — **not** a zkSNARK/circuit and **not** third-party-verifiable without reveal.
- Hides the address from the public offer packet while the salt stays private.
- Real on-chain settlement still needs a concrete address; unlinkable stealth receives are **out of scope** until a real ERC-5564 implementation is wired.
- For production-grade payment privacy, integrate a proper stealth or confidential-payment stack rather than extending the hash-address experiment.

## Files

- `veritas/autonomous/zk_wallet.py` — commit, prove, verify, open, reveal checks
- This document — design notes

## Usage sketch

```python
from veritas.autonomous.zk_wallet import (
    commit_wallet, prove, verify_proof, open_commitment, verify_commitment,
)

wc, opening = commit_wallet("0xSellerAddress...", network="eip155:8453")
assert verify_commitment(wc, opening)
# put wc.to_dict() into the JIT packet instead of clear pay_to
# later, for settlement:
addr = open_commitment(wc, opening)
```
