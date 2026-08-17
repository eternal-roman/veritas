# The Venue: Ecosystem Architecture

Roles, transaction lifecycle, compounding loops, and the evidence level of
each piece. Companions: `CONSTITUTION.md` (from `veritas/constitution.py`)
and `ROADMAP.md`.

## Why agents are the primary customer

Every property is machine-checkable: hashes, custody, refusal, billable
tied to delivery. That fits buyers who verify mechanically and transact at
sub-dollar volume — other agents. They can check a custody chain per
response, retry a 402, and route spend by published trust data.

Humans stay in governance: budgets, spend policy, operating and auditing
sellers, running facilitators and registries. They leave the per-request
hot path, where sub-dollar pricing makes human approval uneconomic
(ROADMAP Part III).

## Roles in the venue

| Role | What it does | Instances today |
|------|--------------|-----------------|
| Buyer agent | Discovers services, evaluates them, signs x402 payments, verifies deliverables | `veritas-buy` + `veritas.payer` ship locally; no unsolicited external buyer yet |
| Seller service | Publishes identity, constitution, and prices; pulls Kalshi/Polymarket books; settles after delivery | Veritas (this repository; catalog pull is the SKU) |
| Facilitator | Verifies payment payloads and settles them on-chain (`POST /verify`, `POST /settle`) | x402 facilitator API; a local simulator for free mode |
| Registry | Lists services so buyers can find them | CDP x402 Bazaar, ERC-8004 (planned, Phase 4); nothing announces Veritas yet |
| Attester | Signs statements about outcomes against a `request_id` | None; Phase 5 |

## The transaction lifecycle

```
discover ──> evaluate ──> pay ──> consume ──> verify ──> attest
```

1. **Discover.** `GET /.well-known/x402`, `GET /v1/identity`, and
   `GET /llms.txt` are unpaid, and the well-known document is
   self-traversing: its `links` object reaches every machine-readable
   surface (identity, trust, constitution, errors, schema, OpenAPI). Today
   discovery still requires knowing the endpoint; registry publication is
   ROADMAP Phase 4.
2. **Evaluate.** The buyer reads the identity document, fetches
   `GET /v1/constitution`, checks enforcement pointers against the published
   test suite, and reads `GET /v1/trust` — which reports `UNPROVEN` rather
   than a manufactured score below its sample floor (article A11). Trust is
   an input to the buyer's spend policy, not authorization.
3. **Pay.** `POST /v1/signals` without payment returns a spec-shaped 402
   with exact atomic amounts (article A10). The buyer signs and retries with
   an `X-PAYMENT` header; the seller verifies through the facilitator before
   doing any work (article A4).
4. **Consume.** Catalog pull is one engine (article A1), and the
   response separates `completed`, `refused`, and `unavailable` — the third
   is never billed (articles A2, A3, A13).
5. **Verify.** The buyer re-checks any hash at `POST /v1/verify`, fetches the
   durable receipt at `GET /v1/receipts/{request_id}`, and can re-run chain
   validation client-side with `veritas.custody.verify_chain_records` —
   none of which needs the seller's cooperation (article A12).
6. **Attest.** Not built. When Phase 5 lands, attestations reference the
   `request_id` and can cite constitution article ids.

## Where Veritas sits, and what it exports

Veritas is one seller service. The exportable idea is the constitution
pattern (`CONSTITUTION.md`, "Adopting this pattern"): articles as data,
enforced-or-admitted evidence levels, and gap registration with witness
tests. A venue in which every seller publishes such a document gives buyer
agents something to evaluate that is stronger than marketing copy and cheaper
than trial-and-error: norms with pointers into artifacts that fail when the
norm is broken.

## Growth loops, with evidence levels

Stated in the repository's register: L1 means a test or gate holds on
exercised cases; L0 means design intent, nothing more.

- **Outcome → trust.** Every served request appends to the outcome log and
  moves the behaviour-derived trust score. L1 today
  (`tests/test_api.py::test_trust_is_unproven_without_data` and
  `veritas/trust.py`), though with zero external traffic the log holds only
  what local runs put there.
- **Trust → discovery ranking.** A registry that ranks by published,
  behaviour-derived trust would route demand toward honest services. L0:
  no registry lists this service yet, and no registry is known to rank by
  this signal.
- **Attestation → portable reputation.** Buyer-signed outcomes would let
  reputation travel across venues (article A16). L0: aspirational, Phase
  4.3/5.1.
- **Constitution adoption → venue-wide evaluability.** If peer sellers adopt
  the pattern, buyer-side evaluation code generalizes across sellers. L0: no
  peer adoption exists; the pattern ships here first.

None of these loops has been observed to compound. The first is real but
locally fed; the rest are architecture waiting on Phases 3–5. The staged
plan and falsifiers live in `docs/program/ECOSYSTEM_LOOPS.md`.

## What must be true before the flywheel turns

In dependency order (see `STATUS.md` for what has already landed):

1. A payment must settle on-chain once (Phase 0) — operator-run testnet
   did; unsolicited and mainnet have not.
2. Retrieval must be worth paying for (Phase 1) — the venue does not reward
   honest plumbing around a weak product.
3. A buyer side must exist (Phase 3) — signing, key custody, budgets.
4. Discovery must announce the service (Phase 4) — an unlisted seller has no
   venue.
5. Reputation must attach to outcomes (Phase 5) — so honesty becomes an
   advantage a counterparty can price.

This document describes the intended shape of that venue and the norms
Veritas commits to inside it. The commitments are enforced today (the L1
articles); the venue around them is still being built.
