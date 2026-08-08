# Counterparty diligence: letting a buyer agent refuse a seller

**Status:** design. Chosen by the agent under a standing instruction to proceed
without further questions; not separately reviewed by a human. Implemented on
`feat/session-2026-08-08`.
**Date:** 2026-08-08. **Baseline:** `main` @ `4c3b23c`.

## Problem

`veritas/payer.py` states the gap in its own docstring:

> Pinning parameters to the validated challenge does NOT authenticate the
> seller. The 402 challenge is itself content from an untrusted counterparty
> and is the sole source of `payTo` and `amount`; a hostile seller can name
> any recipient and any price, and only `SpendPolicy` bounds the loss.
> Counterparty vetting is roadmap 5.2, not this module.

So a buyer agent's only defence against a hostile seller today is a spend cap:
it will pay the wrong party, for the wrong thing, at the wrong price — just not
more than $N per day. That is a budget, not a decision.

Meanwhile `CONSTITUTION.md` §"Adopting this pattern" specifies exactly what a
buyer agent *should* do — fetch the constitution, check enforcement pointers,
weigh aspirational articles at zero — and no code in this repository does it.
Every surface here is seller-side. **Veritas publishes a due-diligence protocol
it has not implemented.** A buyer adopting it still needs a human to read a
test suite, which is the human-in-the-loop dependency that matters most.

## What we are building

`veritas/diligence.py`: a pure evaluator that turns a seller's published
documents into a verdict a buyer agent can act on, plus a third gate in
`PaymentClient.pay()` so the verdict binds money rather than advising about it.

### Non-goal, deliberately

**No network I/O in this module.** It evaluates documents the caller already
fetched. That keeps it pure and trivially testable, adds no SSRF surface, and
lets a buyer fetch however it likes. A fetch helper is a later, separate
concern. This is the YAGNI cut.

## The central discipline

`UNVERIFIABLE` is not `FAIL`.

This is the same distinction the product already sells — `unavailable` is not
`no_evidence` — applied to the buyer side. "I could not check this seller" and
"this seller failed the check" are different facts, and reporting the first as
the second would be the exact dishonesty the service exists to refuse.

For a payment gate **both block** (fail-closed), but they are reported
separately, because the buyer's response differs: `FAIL` means find another
seller; `UNVERIFIABLE` means fix your own fetch path and retry.

## Checks

Each is independently reportable, and each states what it is evidence of.

| # | Check | What it proves | Needs trust? |
|---|-------|----------------|--------------|
| 1 | **Challenge/discovery agreement** — the 402's `payTo`, `network` and `asset` equal what `/.well-known/x402` advertises, and its amount does **not exceed** the advertised price | The seller is billing to the address it publicly advertises, at no more than its published price | **No** — pure cross-document consistency |
| 2 | **Register integrity** — every article claiming L1 carries a non-empty enforcement pointer; none claims both L1 and aspirational | The seller's own meta-test, re-run by the buyer instead of trusted | No |
| 3 | **Aspirational discount** — count and report L0 articles | Which norms carry no enforcement, weighted at zero | No |
| 4 | **Self-report disclosure** — `/v1/trust` states that it is self-reported and names its sample floor | A seller publishing a bare number is *less* trustworthy than one publishing `UNPROVEN` | No |
| 5 | **Gap register present** — the constitution declares known gaps | A seller claiming zero gaps is claiming perfection, which is a negative signal | No |

Address, network and asset are compared for equality; the amount is compared
one-sided. A seller charging *less* than it advertises is not defrauding the
buyer, so only an amount exceeding the advertised price fails. Comparison is on
atomic units, never on the human-readable price string.

Check 1 is the strongest and the most novel: it requires no trust in the seller
at all, only that two of its own documents agree. A seller that advertises one
payout address and challenges with another is compromised or hostile, and today
nothing anywhere notices.

Check 5 is deliberately inverted. In a venue where sellers self-describe, an
empty defect register is evidence of concealment, not of quality.

## Architecture

```
DiligencePolicy       what this buyer requires (data, no behaviour)
        │
        ▼
assess(documents, policy) -> DiligenceReport
        │                      ├── verdict: PASS | FAIL | UNVERIFIABLE
        │                      ├── checks: [CheckResult, ...]  (one per check)
        │                      └── reasons: [str, ...]
        ▼
PaymentClient.pay(..., diligence=report)
        └── not PASS -> PaymentResult denial, check="diligence"
                        signer is never reached
```

Three units, each understandable alone:

- **`DiligencePolicy`** — a frozen dataclass of buyer requirements. Pure data.
- **`assess()`** — pure function: documents + policy → report. No I/O, no clock,
  no global state. Every check is a small named function returning a
  `CheckResult`, so a buyer can read *why*, not just *what*.
- **The payer gate** — one branch in `PaymentClient.pay()`, before the signer,
  returning the module's existing `PaymentResult` denial shape.

### Why it goes in `PaymentClient.pay()`

Invariant 8 says `veritas.payer` owns the gate and that no second path may sign
without it. Adding diligence as a third policy layer beside validation and
spend caps extends that seam. Adding it anywhere else would fork it.

Article A20 already guarantees "a refused payment never reaches the signer."
The diligence denial must hold that same line, and is tested for it.

## Error handling

- Malformed or missing documents → `UNVERIFIABLE` with the specific document
  named. Never `FAIL`, never an exception.
- A document that is present but internally inconsistent (check 2 fails) →
  `FAIL`. That is an observed defect, not a missing observation.
- `assess()` raises nothing. Failures are results, matching `payer.py`'s
  existing "failures are explicit results, never control-flow exceptions."
- The gate is fail-closed: absent or non-`PASS` diligence denies when the
  policy requires diligence.

## Testing

L1 throughout; no stronger claim is available for this.

- Each check gets a passing case, a failing case, and an unverifiable case.
- **`UNVERIFIABLE` is never reported as `FAIL`** — a named test, because this is
  the module's central claim.
- **A refused counterparty never reaches the signer** — a signer double that
  raises if called, mirroring the existing A20 test.
- A hostile challenge naming a `payTo` that discovery does not advertise is
  refused (check 1, end to end through `PaymentClient.pay`).
- Veritas's own served documents are valid input: the evaluator is run against
  this service's real constitution and discovery output, so the venue's
  reference implementation passes its own bar.

## Prerequisite: a deterministic suite

Measured on `main` @ `4c3b23c`: `2 failed, 418 passed, 2 skipped, 4 errors`.
All six pass in isolation. The suite is order-dependent, not flaky — there is no
`pytest-randomly` and no `conftest.py`.

Mechanism: `veritas/server.py:96-98` constructs `CustodyStore()`, `OutcomeLog()`
and `Ledger()` at import time, each reading a cwd-relative
`VERITAS_RUNTIME_DIR` (defect O5, open). The suite works around this with 23
`importlib.reload` calls across 11 files; all three failing files are reload
sites, and the run leaves a real `.veritas_runtime/` in the repository root.

This matters beyond hygiene: **CI-green is the evidence every L1 constitution
article points at.** An order-dependent suite makes that evidence
non-reproducible, which weakens every enforcement pointer at once.

A `tests/conftest.py` giving each test an isolated runtime directory lands
first, as its own commit. It is purely additive — one new file, no existing
file touched — so it cannot collide with concurrent work.

## Scope boundaries

Not in this change: fetching seller documents over the network; fixing O5 in
`server.py` itself; the reload workarounds; multi-instance state. `server.py`,
`custody.py`, `ledger.py`, `ops_cli.py` and `docs/program/` are being worked
concurrently by another agent and are not touched here.

## Honest limits

- Every check is cross-document consistency and register integrity. **None
  proves the seller will deliver.** A careful liar with a coherent set of
  documents passes all five.
- Check 1 binds the challenge to advertised discovery. It does not
  authenticate discovery itself: a seller who controls both documents can make
  them agree on a hostile address. What it defeats is a *tampered or
  swapped challenge*, and inconsistency between a seller's own surfaces.
- This raises the cost of dishonesty and gives a buyer machine-checkable
  grounds to refuse. It is not proof of honesty, and the module must not be
  described as such.
