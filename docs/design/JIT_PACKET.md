# JIT Disposable Packet (JDP) Protocol

## Goal

Enable fully distributable agent-to-agent value exchange with **zero prior setup** by either party.

- The only long-lived identifier is a **salted agent ID**.
- Every communication carries a self-contained package with:
  - Wallet / payment coordinates for *this* exchange
  - Network (CAIP-2)
  - Price / asset / facilitator
  - Capability description and schema hints
  - Optional payload / evidence hashes
- The package is **Just-In-Time**, created for the communication, and **disposable** after use.
- Packets can be **chained** (`prev_packet_id` / `chain_root`) so multi-step workflows remain linked without shared state.

## Why this exists

Traditional setups require both sides to already know endpoints, wallets, networks, and schemas. That re-introduces human or pre-provisioned configuration. JDP makes each transmission carry the bootstrap data required to complete the exchange, then discards it.

## Packet fields (core)

| Field | Purpose |
|-------|--------|
| `agent_id` | Salted, non-persistent agent identifier (`sid:...`) |
| `packet_id` | Unique ID for this disposable package |
| `pay_to` / `network` / `price` / `facilitator` / `asset` | Payment coordinates for *this* transaction |
| `capability` + `schema_hint` | What the packet is offering or requesting |
| `payload` | Optional content or reference |
| `evidence_hashes` | Content-addressed evidence for verification |
| `prev_packet_id` / `chain_root` | Chainability |
| `expires_at` | TTL so packets are naturally disposable |
| `disposable` | Explicit flag |

## Flow

1. Sender creates a JIT packet with its current receiving coordinates and capability offer.
2. Packet is transmitted (HTTP body, MCP message, A2A envelope, etc.).
3. Receiver needs no prior configuration: the packet itself contains how to pay and what is being offered.
4. Receiver pays (if required) using the coordinates in the packet.
5. Result can be returned in a chained packet that references the previous `packet_id`.
6. Both sides discard the packet after the exchange; only the salted agent ID and any retained evidence hashes remain meaningful.

## Implementation

See `veritas/autonomous/jit_packet.py` for the prototype encoder/decoder and chaining helpers.

## Relationship to x402 + CAIP-2

- `network` uses CAIP-2 identifiers (`eip155:8453`, etc.).
- Payment fields map cleanly onto x402 `accepts[]` requirements.
- Facilitator URL can be included so the receiver does not need a pre-configured facilitator list.

## Security notes

- Packets are ephemeral; do not treat them as long-term identity.
- Salted agent IDs prevent trivial correlation across unrelated sessions if salts are fresh.
- Always verify evidence hashes independently.
- TTL (`expires_at`) limits replay windows.
