# First-principles insights — fable/survival-records

> **ATTENTION — AGENTS WORKING IN THIS REPOSITORY**
> This document records the load-bearing reasoning behind the survival-record
> audit protocol (`veritas/audit.py`) and the findings that produced it. It is
> maintained on this branch alongside the code. If you touch trust, reputation,
> attestation, or Phase 5 work: read this first, and keep it current — a design
> decision changed without updating its rationale here is the same defect as an
> article changed without its enforcement pointer. Per
> `skills/adversarial-code-truth.md`, nothing below claims more than its
> evidence carries.

## 1. What this codebase actually is (read 2026-08-08, main @ 622429c)

Strip the payments plumbing and Veritas is one commitment, applied recursively:
**never let a claim outrun what was observed, and always hand the counterparty
the means to check the claim without trusting the claimant.**

Every load-bearing mechanism in the repo is an instance of that commitment:

- The outcome taxonomy (`completed` / `refused` / `unavailable`) refuses to
  convert "I could not look" into "there is nothing" — and refuses to bill
  when it could not look.
- The custody chain ships **with** the response so `verify_chain_records`
  runs on the buyer's bytes, not the seller's goodwill.
- `veritas/verifier.py` imports nothing from `veritas` so the auditor's tool
  cannot be the audited party's code.
- `support.py` replaced a Bayesian posterior with counts a buyer can recompute
  — because the posterior's hypothesis had no truth value and its likelihoods
  were hand-typed constants.
- The constitution forces every stated norm to name the test that enforces it
  or confess to being aspirational.

## 2. The deepest open contradiction

The repository states it plainly (README, `trust.py` docstring, gap G10): **the
trust score is computed by the graded party from its own records.** A seller
that logged favourable outcomes would produce an identical document. G7 closed
the free-traffic manipulation route; G10 remains open because restricting input
to paid traffic does not make the number verifiable by the buyer relying on it.

The planned fix (ROADMAP Phase 5.1) has the seller collecting buyer
attestations and aggregating them into its own trust basis, "weighted below
local telemetry." That inherits the defect: **the audited party remains the
aggregator.** The roadmap itself concedes "self-reported reputation is gameable
by construction." Phase 5 as sequenced would rebuild G10 one layer up.

## 3. The evolution lens

Reputation among unrelated organisms did not evolve as self-description. It
evolved as **indirect reciprocity**: individuals act, third parties observe and
remember, and standing is computed by each observer from records of survived
interactions — image scoring, not self-image. Three structural features make it
stable, and each has an exact analogue available in this codebase today:

| Evolutionary requirement | Veritas primitive that satisfies it |
|---|---|
| A costly, falsifiable commitment by the actor | EIP-191 attestation over `url + content_hash + observed_at` (N1.1) — signing binds the seller to a claim any third party can test forever after |
| Independent observation of the commitment | Origin re-fetch through `notary.observe` (P7) — the observer's own fetch, not the seller's word |
| Portable, unforgeable memory of outcomes | Signed records passed agent-to-agent (N1.3 EvidencePack shape) — standing computable by anyone holding the records |

The selection dynamic: a seller's attestation is a **staked claim**. Honest
sellers survive arbitrary audit pressure at zero marginal cost; dishonest
sellers accumulate divergence records signed by keys they do not control.
Fitness = survival under adversarial re-observation. Trust is not what a
service says about itself; **trust is what survives audit.**

## 4. The derivation, from the repo's own principles

No new principles were needed — only the existing ones applied to the
reputation layer, where they had not yet been applied:

1. **Independence damping, applied to auditors.** `support.py` counts
   evidence independence per registrable domain because two pages on one site
   are one publisher, not two witnesses. The same argument: two thousand audit
   records signed by one key are **one auditor, not two thousand**. The unit
   of reputation evidence is the distinct auditor key, never record volume.
   (`bayesian.py`'s correlated-source damping is the same insight in its
   scored form; the counts form is what ships, per the support.py precedent.)
2. **The outcome taxonomy, applied to audits.** A re-fetch that could not
   observe the origin is evidence of nothing. `unobserved` must be reported
   and must never count for or against a seller — the exact analogue of
   `unavailable` ≠ `no_evidence` (invariant 2) and of trust.py's
   reported-but-never-scored free traffic. An audit protocol that scored
   unreachability would let a network outage assassinate a reputation.
3. **Divergence is not fraud.** P7 already states it: a page legitimately
   changes between T1 and T2. A `diverged` verdict is a fact about
   re-observation, not a fraud proof; verdicts are counts in a report, never
   an authorization. (Consequence: `surviving` decays naturally — content
   that rots stops being confirmable, which is honest.)
4. **The aggregator must not be the audited party.** The repo's verifier
   ships as a zero-dependency file precisely so the auditor's tool is not the
   auditee's code. Therefore `survival_report` is a **pure function over
   records the buyer holds**, obtained from anywhere. There is deliberately
   no server surface where the seller hosts "its" audit record set: a mailbox
   the seller curates is G10 with extra steps.
5. **The omission bound, stated as a gap, not papered over.** Nothing forces
   an unfavourable record into the set a buyer sees. A survival report is
   therefore an honest summary of **the records provided**, and divergence
   counts are a floor, never a ceiling. This is registered as constitution
   gap G11 with a witness test, following the house discipline: a limit we
   cannot yet remove is registered with teeth, not hidden. (Removal path:
   auditor-side publication / transparency logs — the Merkle/anchor work
   already named as later N1.)
6. **Domain separation for signatures.** An audit signature must never be
   replayable as an evidence attestation or vice versa. Distinct canonical
   message prefixes (`veritas-audit-record-v1` vs
   `veritas-evidence-record-v1`) enforce this at the message layer — same key
   family, disjoint message spaces, no second crypto stack (the module reuses
   `notary.sign` primitives; a parallel signing path would violate the spirit
   of invariant 8).

## 5. What survival records change

Before: buyer → `GET /v1/trust` → a number the seller computed about itself.
After: buyer holds N signed audit records from K distinct auditor keys, runs
`survival_report` locally, and reads counts it can recompute — `confirmed` /
`diverged` per distinct auditor, self-audits surfaced and excluded,
`unobserved` reported and never scored. The seller's cooperation is not
required and the seller's arithmetic is not trusted.

This is the missing half of the venue's economics: `diligence.py` lets a buyer
vet a seller's **documents** before paying; survival records let a buyer vet a
seller's **history** — and every audit any buyer performs compounds into a
public good, which is the property Phase 2.1 wanted ("the one asset that
compounds with usage") applied to reputation.

## 6. Honesty boundaries (what this does NOT establish)

- A survival report describes **the records provided to it** — omission is
  possible and registered (G11). Divergence observed is real; divergence
  absent is not proven absent.
- `confirmed` means one auditor's fetch of the origin matched the attested
  hash at one time. It does not prove the origin serves that body to others
  (the N0 boundary), and CDN/geo/personalisation variance can produce honest
  `diverged` verdicts.
- Distinct keys are not proven distinct **parties**: sybil auditors cost only
  key generation. Distinct-auditor counts raise the floor of collusion cost;
  they do not establish identity (that is the ERC-8004 / 4.3 axis).
- Nothing here settles on-chain, anchors to a public log, or closes G10 —
  `/v1/trust` remains self-reported and says so. This ships the **mechanism**
  by which external standing can exist; standing itself requires volume that
  does not yet exist (Phase 5's "reputation requires volume" holds).

## 7. Sequencing consequence proposed to the roadmap

Phase 5.1 as written ("aggregate into the trust basis") should invert: the
buyer-side pure function ships first (this branch), the seller-side mailbox
becomes optional convenience later, and the seller **never** aggregates its own
standing. Phase 5.2's "require a minimum score" should consume
`survival_report` output computed by the buyer, not `/v1/trust` — the spend
policy then gates on evidence the buyer verified rather than on the
counterparty's self-assessment, which is the same trust-shape as invariant 8's
"payment parameters derive only from the validated challenge."

## 8. Second derivation (2026-08-08, same branch): falsifiable commerce

Survival records answered "how can standing be computed without trusting the
audited party?" — and left the deeper question exposed: **why would anyone
audit at equilibrium?** Verification in every current agent-commerce design
is a cost center — arithmetic (free, shallow), altruism (underprovided), or
escalation (human-speed). The ecosystem-forming move is giving verification
its own economics: every claim ships with a seller-authored, deterministic
falsification predicate, a bonded stake, and a challenge window, so hunting
bad answers is a paid occupation and disputes terminate in re-execution, not
judgment. The Popperian inversion — the seller writes the experiment that
would refute itself, and prices its own confidence by staking on it — plus
falsifiability classes (D0/D1/D2/U) as priced market metadata, is the part
that does not currently exist in the space. Forfeited bonds also repair this
document's own §6 asymmetry: a forfeit is a settlement event the seller
signed, so negative reputation becomes unomittable — G11's floor gains an
enforcement mechanism at W1. Full methodology, prior-art differentiation,
honesty boundaries, and the recorded mandate:
`docs/program/FALSIFIABLE_COMMERCE.md`. Implementation: `veritas/warranty.py`
(D0 registry), constitution A27 + gap G12.

Key transferable insights for future agents, compressed: (1) in agent
commerce the scarce good is not trust but *economically motivated
distrust* — design for profitable falsification, not certified truth;
(2) the repo's own invariants make the best warranty predicates — an
invariant a service brags about is an invariant it should be willing to
stake on per-transaction (`status_incoherent.v1` bonds invariant 3);
(3) honesty taxonomies generalize: completed/refused/unavailable →
confirmed/diverged/unobserved → fired/not_fired/undecidable — every layer
needs its "we could not decide, and that is different from both yes and no."

---
*Maintained on `fable/survival-records`. Update this document in the same
commit as any change to `veritas/audit.py`, `veritas/warranty.py`, the A22
or A27 articles, or gaps G11/G12.*
