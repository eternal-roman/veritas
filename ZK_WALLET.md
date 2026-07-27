# Zero-Knowledge Wallet Privacy for JIT Packets

## Goal

Keep the receiving wallet **private** in the public JIT Disposable Packet while still allowing the counterparty to verify that a valid payment target exists and that the seller knows the opening.

## Construction (v1)

1. **Commitment**  
   `C = H(salt || address || network)`  
   Published in the packet instead of the raw `pay_to`.

2. **Proof of Knowledge**  
   A lightweight Fiat-Shamir-style proof binds the commitment and demonstrates knowledge of the opening without revealing the address in the public packet.

3. **Optional stealth / one-time address**  
   Helper to derive ephemeral receive addresses from a view secret + ephemeral key material so each packet can use a fresh address.

4. **Selective reveal**  
   At settlement time the seller (or facilitator under policy) can open the commitment if required for on-chain settlement, while the original offer packet never contained the cleartext address.

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

- This is a **commitment + proof-of-knowledge** construction, not a full zkSNARK/circuit.
- It hides the address from the public packet and from passive observers of the offer.
- Real on-chain settlement still ultimately requires a concrete address; the privacy gain is in the offer/discovery phase and in unlinkability across packets when combined with stealth addresses.
- For production-grade privacy (unlinkable payments, amount privacy, etc.) integrate with systems such as confidential x402 schemes (e.g. Merces / PRXVT-style) or full stealth-address ECC.

## Files

- `autonomous/zk_wallet.py` — commitment, verify, open, stealth helper
- This document — design notes

## Usage sketch

```python
from autonomous.zk_wallet import commit_wallet, verify_commitment, open_commitment

wc, opening = commit_wallet("0xSellerAddress...", network="eip155:8453")
assert verify_commitment(wc)
# put wc.to_dict() into the JIT packet instead of clear pay_to
# later, for settlement:
addr = open_commitment(wc, opening)
```
