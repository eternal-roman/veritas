# G10 — Survival-records reputation: first-principles consensus

**Status:** consensus landed as docs (2026-08-08). **Constitution gap G10 remains open on `origin/main`.**
**Mechanism land:** A26/A27/standing shipped as **#75** (`ab728a6`) — buyer-side audit + warranty W0 + composed standing. That is **not** G10 closed.
**Source claim:** Observer note re Fable-max / `fable/survival-records`.

### Where the mechanism lives now (post-#75)

| Path | Role |
|------|------|
| `veritas/audit.py` + `audit_cli.py` | A26 survival records / independence |
| `veritas/warranty.py` | A27 warranty W0 |
| `veritas/standing.py` | Composed standing over audit records |
| `docs/program/FABLE_INSIGHTS.md` | First-principles insights (on main) |
| `docs/program/FALSIFIABLE_COMMERCE.md` | Falsifiable commerce notes (on main) |
| `docs/program/FABLE_SURVIVAL_MONITOR.md` | Monitor notes (on main) |
| Historical export | `Downloads/fable-survival-records.patch` (pre-merge apply path) |

**Naming:** constitution **G10** = self-reported trust score (this doc). Program
**G10** in `GUARDIAN` / `flywheel-claim` = claim-thrash guard (unrelated). Do not
confuse them.

---

## Claim under review (Fable-max paraphrase)

> Reputation computed by the party being judged (registered gap G10) is inverted:
> standing becomes a pure function any buyer runs over third-party-signed audit
> records of a seller’s staked claims surviving independent re-observation,
> requiring zero cooperation from the seller. Evidence-layer principles map up:
> one auditor key counts as one witness (source-independence); an unreachable
> origin counts as nothing (`unavailable` ≠ `no_evidence`). Trust stops being
> self-description and becomes what survives adversarial audit. Indirect
> reciprocity is old theory; the claimed contribution is composition from
> existing primitives. “Groundbreaking” is not asserted as product fact.

---

## What G10 actually is today (checked)

| Fact | Evidence |
|------|----------|
| Score is computed by the graded party from local counters | `veritas/trust.py` `score_service` / `OutcomeLog` |
| Document admits self-report | `basis.self_reported` string; A11 statement |
| Paid-only scoring (G7 closed) does **not** close G10 | CONSTITUTION G7 resolution text; G10 description |
| Witness pins the gap open | `tests/test_known_gaps.py::test_known_gap_the_trust_score_is_self_reported` — asserts no `verify_attestation` / `verify_external_attestation` in `trust`, and `self_reported` present |
| Diligence treats it as disclosure, not authority | `veritas/diligence.py` check 4; counterparty fixtures |
| ROADMAP already aimed buyer attestations later | Phase 5.1 “Signed attestations”; A16 portable reputation is **L0** |

**PROPERTY (current product):** A buyer who only reads `/v1/trust` cannot tell a
honest paid-history log from a forged one produced by the seller.

**EVIDENCE LEVEL:** L1 (witness + module source).  
**NOT PROVEN:** Any external attestation path for standing.

---

## First-principles decomposition

### P1 — Who produces the number?

- **Self-report (status quo):** seller runs `score_service` over seller DB →
  buyer receives a number. Incentives align to inflate.
- **Inversion (thesis):** buyer (or any third party) runs a pure function `S`
  over a multiset of **signed audit records** they already hold or can fetch
  from non-seller sources. The seller cannot unilaterally invent a favourable
  `S` without forging others’ signatures or origins.

**Consensus:** P1 inversion is the correct *direction* for closing G10.
It matches A12’s spirit (verify without seller cooperation for hashes/receipts)
and the honesty already baked into diligence (“input, not authorization”).

### P2 — What is an audit record?

Minimally, a record that binds:

1. a **claim** (what the seller asserted or delivered — e.g. `content_hash`,
   `request_id`, notarized URL + extract version);
2. an **auditor identity** (key that signed the audit outcome);
3. a **re-observation outcome** (match / mismatch / *unavailable*);
4. **time** and enough context to replay the check.

**Already partially present as evidence primitives (not as reputation):**

| Primitive | Role | Honesty bound |
|-----------|------|----------------|
| `notary.observe` | one-engine observation | not multi-party origin proof |
| `notary.sign` (EIP-191) | operator attestation of bound fields | **operator = seller-side key today** — not third-party |
| `notary.refetch` / P7 `/v1/verify` | re-observe origin vs claimed hash | origin may have changed; not multi-party |
| `notary.pack` EvidencePack | portable handoff | integrity of pack, not external trust |
| Merkle log + inclusion (N1.4/N1.5) | operator-local append-only | not public CT; not multi-operator |
| `support.registrable_domain` | one publisher domain = one evidence witness | URL domains, **not** auditor keys |
| pipeline `unavailable` ≠ `no_evidence` | failed look ≠ empty world | research path; not yet reputation path |

**Consensus:** The *composition* story is real at the evidence layer. It is
**not** yet a reputation module. Calling that “solved G10” confuses primitives
with a closed gap.

### P3 — Independence rule (auditor keys)

Thesis: one auditor key = one witness (map of source-independence).

**Sound if:** colluding keys are treated as one (or discounted); key generation
is cheap so stake, registration cost, or web-of-trust is required; buyer
algorithm is deterministic and disclosed.

**Not free:** without cost-of-identity, Sybil keys invent corroboration the same
way free traffic invented G7 reputation. G7’s lesson applies upstairs.

### P4 — Unreachable origin = nothing

Thesis maps `unavailable` ≠ `no_evidence` correctly:

- Re-fetch fails (timeout, 5xx, robots block, SSRF deny) → **do not score as
  fraud and do not score as survival**. Drop or park as `unavailable`.
- Re-fetch completes with hash mismatch → **failure to survive** (with the P7
  caveat that the page may have changed).
- Re-fetch completes with match → **survived this auditor at this time**.

**Consensus:** this mapping is load-bearing and already product doctrine for
retrieval. Applying it to standing is correct. Mis-implementing “unreachable =
bad seller” would manufacture NOT_RECOMMENDED from network weather.

### P5 — “Zero cooperation from the seller”

**Partial, not absolute.**

- **True without seller:** given published durable audit records and public
  claim digests, a buyer can recompute `S` offline (A12-style).
- **Still needs some published object:** staked claims, packs, or auditor
  journals must exist *somewhere* the buyer can read. If only the seller hosts
  them, unavailability of the seller is not “no reputation” — it is
  `unavailable` again. Zero-coop requires **non-seller distribution**
  (buyer-published attestations, public log, registry, other auditors).
- **Operator EIP-191 today is not third-party.** Closing G10 on operator-signed
  self-attestations alone would rename self-report, not invert it.

### P6 — “Staked claims”

Staking / economic bond for claims is **not** in the current product.
Composition from *existing* primitives can start with **published signed
claims + re-observation** without on-chain stake; stake is an amplifier
(ROADMAP / A16 territory), not a prerequisite for the inversion logic.
Claiming “staked” without a stake path is aspirational language — mark L0.

### P7 — Novelty

Indirect reciprocity and third-party reputation are old. Fable’s own caveat is
right: the interesting claim is **composability from Veritas’s evidence
invariants**, not invention of reputation theory. Product language: “design
direction for G10,” not “groundbreaking.”

---

## Verdict matrix

| Thesis element | Consensus | Level |
|----------------|-----------|-------|
| G10 diagnosis (self-report paradox) | **Accept** — already registered | L1 |
| Invert who computes standing | **Accept** as design direction | L0 design |
| Pure buyer-side function over audit records | **Accept** as target shape | L0 |
| Map independence + unavailable rules up | **Accept** as norms for any design | L0 (evidence L1) |
| Composable from observe/sign/pack/refetch/support | **Accept partially** — evidence yes; reputation wiring no | L1 evidence / L0 reputation |
| Zero seller cooperation | **Accept only with non-seller publication** | L0 caveat |
| Staked claims | **Not in product** — optional later | L0 |
| “Solved” / close G10 | **Reject** | — |
| “Groundbreaking” as product fact | **Reject** (Fable deferred; we agree) | — |
| Ship “G10 closed” this slice | **Reject** — mechanism landed (#75); gap still open; 0 settlements | — |

---

## What would actually close G10

Do **not** close the gap until all of the following hold (mirrors G9 design
honesty):

1. **Buyer-side standing function** `S(records) → standing` lives outside
   seller self-score as the *authoritative* diligence path (seller `/v1/trust`
   may remain as telemetry labeled self-reported).
2. **Inputs are third-party-signed** (buyer or independent auditor keys), not
   only `VERITAS_SIGNING_KEY` operator attestations.
3. **Independence:** distinct auditor keys (with Sybil cost or explicit
   “keys are cheap” disclosure); unreachable re-observations do not count as
   survival or as guilt.
4. **L1 witnesses:** tests that a seller forging local `OutcomeLog` cannot
   improve `S` without forging foreign signatures; tests that `unavailable`
   re-fetch does not move standing like a match or a mismatch.
5. **Constitution:** G10 → closed with resolution pointer; delete
   `test_known_gap_the_trust_score_is_self_reported` (same discipline as other
   gaps). A16 may promote only with portable attested outcomes (Phase 5 / 4.3).

Until then the witness must keep passing.

---

## Relation to ROADMAP and sequencing

- **Phase 5.1** already names buyer-published outcome attestations — same family
  as survival-records, not a fork of product intent.
- **Phase 0 settlement proof still dominates.** Reputation without volume or
  paid path is decorative (ROADMAP: “Phase 5 last”). Survival standing without
  paid deliveries is still thin.
- **G9 remains open** (chain reconcile). Do not serialize G10-close ahead of
  Overseer singular NEXT or invent dual claim with release/N1.x thrash.

---

## Recommended program response

1. **Land this consensus** (docs) so Steward / Conductor / Overseer / Scout share
   one reading. Do **not** set flywheel claim to building for “G10 close.”
2. **Re-run this checklist** against main code after further standing/trust changes;
   do not treat A26/A27 land as G10 closed.
3. **Optional next design slice** (only if Overseer authorizes):
   `docs/program/G10_SURVIVAL_STANDING.md` — pure function sketch, record
   schema, Sybil policy, fail-closed rules — same shape as
   `G9_CHAIN_RECONCILE.md` (design + fail-closed surface ≠ gap closed).
4. **Do not** rebuild `/v1/trust` to lie that it is external. Prefer a separate
   buyer path (`veritas.standing` or diligence check) that consumes packs +
   foreign signatures.
5. **Keep claim free** for product bets until NEXT names one.

---

## Formal gate (adversarial-code-truth)

```
PROPERTY: Standing that a buyer relies on must not be unilaterally
          manufacturable by the graded seller from local records alone.
EVIDENCE LEVEL: L0 (design consensus); current G10 defect is L1-witnessed open.
CHECKED ARTIFACT: veritas/trust.py; tests/test_known_gaps.py G10;
                  notary observe/sign/refetch/pack; support.py;
                  CONSTITUTION G10; ROADMAP Phase 5.1; this doc.
ASSUMPTIONS: Thesis text as quoted by the observer note; #75 mechanism
             on main does not by itself invert /v1/trust authority.
NOT PROVEN: Third-party audit economy; stake; G10 closed (self-report
            /v1/trust still authoritative for the score path); on-chain
            settlements (still 0); “groundbreaking.”
```

---

## Addendum — mechanism on main via #75 (2026-08-08)

| Check | Result |
|-------|--------|
| PR | **#75** merged `ab728a6` |
| Modules | `veritas/audit.py`, `warranty.py`, `standing.py` + tests |
| Closes G10? | **No** — G10 witness retained; `/v1/trust` still self-reported |
| G11 / G12 | **Open** (witnessed) — survival omission bound; warranty ≠ escrow |
| A26 / A27 | **L1** articles + enforcement tests on main |

**Revised one-line:** Buyer-side audit/warranty/standing mechanism is **L1 on
main**; constitution **G10 stays open** until standing replaces self-report as
the diligence authority path; do not ship-closed or thrash-claim “G10 solved.”

---

## One-line consensus

**Sound inversion; #75 shipped the buyer-side mechanism (A26/A27/standing) with
L1 tests — G10 stays open until standing replaces self-report as the diligence
path; G11/G12 remain open; settlements still 0; do not claim G10 closed.**
