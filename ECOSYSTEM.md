# The Venue: Ecosystem Architecture

How Veritas positions itself in the agent economy: the roles around it, the
lifecycle a transaction moves through, the loops that could compound, and the
honest evidence level of each piece. Companion documents: `CONSTITUTION.md`
(the norms, rendered from `veritas/constitution.py`) and `ROADMAP.md` (the
sequencing).

## Why agents are the primary customer segment

Veritas sells evidence-grounded research whose every property is
machine-checkable: content hashes, custody chains, explicit refusal, a
billable flag tied to delivery. That output profile matches buyers who can
verify it mechanically and transact at sub-dollar prices with high request
volume — which is to say, other agents. Agentic buyers can check a custody
chain on every response, retry on a 402, and route spend by published trust
data; serving them well is the growth thesis.

Humans hold the governing positions in this venue: they set budgets and spend
policies for buyer agents, operate and audit seller services, run the
facilitators and registries, and are the beneficiaries the honesty guarantees
ultimately protect. Nothing in this architecture removes them from oversight;
it removes them from the per-request hot path, where sub-dollar pricing makes
per-request human approval uneconomic (see ROADMAP Part III, assumptions).

## Roles in the venue

| Role | What it does | Instances today |
|------|--------------|-----------------|
| Buyer agent | Discovers services, evaluates them, signs x402 payments, verifies deliverables | None known; ROADMAP Phase 3 builds the buyer side |
| Seller service | Publishes identity, constitution, and prices; does the work; settles after delivery | Veritas (this repository) |
| Facilitator | Verifies payment payloads and settles them on-chain (`POST /verify`, `POST /settle`) | x402 facilitator API; a local simulator for free mode |
| Registry | Lists services so buyers can find them | CDP x402 Bazaar, ERC-8004 (planned, Phase 4); nothing announces Veritas yet |
| Attester | Signs statements about outcomes against a `request_id` | None; Phase 5 |

## The transaction lifecycle

```
discover ──> evaluate ──> pay ──> consume ──> verify ──> attest
```

1. **Discover.** `GET /.well-known/x402` and `GET /v1/identity` are unpaid.
   Today discovery requires knowing the endpoint; registry publication is
   ROADMAP Phase 4.
2. **Evaluate.** The buyer reads the identity document, fetches
   `GET /v1/constitution`, checks enforcement pointers against the published
   test suite, and reads `GET /v1/trust` — which reports `UNPROVEN` rather
   than a manufactured score below its sample floor (article A11). Trust is
   an input to the buyer's spend policy, not authorization.
3. **Pay.** `POST /v1/research` without payment returns a spec-shaped 402
   with exact atomic amounts (article A10). The buyer signs and retries with
   an `X-PAYMENT` header; the seller verifies through the facilitator before
   doing any work (article A4).
4. **Consume.** The pipeline runs once, in one engine (article A1), and the
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
locally fed; the rest are architecture waiting on Phases 3–5.

## What must be true before the flywheel turns

In dependency order (see ROADMAP Part III for sizing):

1. A payment must settle on-chain once (Phase 0) — every commercial claim
   downstream rests on it.
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
