# Veritas Status

Written to be accurate rather than encouraging. The previous version of this
file described a system that did not import.

## What actually works (verified by tests + CI gates)

| Component | State |
|-----------|-------|
| Content hashing + normalization | Working, tested |
| Custody hash-chain + tamper detection | Working, tested |
| Durable custody receipts (`/v1/receipts`) | Working, tested |
| Bayesian updating with correlated-source damping | Working, tested |
| Refusal taxonomy (`refused` vs `unavailable`) | Working, tested |
| Retrieval error surfacing | Working, tested |
| x402 402-challenge construction (atomic amounts) | Working, tested |
| Facilitator verify/settle client, fail-closed | Working, tested against unreachable host |
| Payment misconfiguration guard | Working, tested |
| Hiding wallet commitments | Working, tested |
| Signed JIT packets, enforced expiry, chain verification | Working, tested |
| Behaviour-derived trust score | Working, reports `UNPROVEN` until 10 samples |
| Evaluation harness + CI quality gates | Working |

## What is built but unproven

- **Live settlement.** The verify/settle calls are implemented against the
  x402 facilitator API but have never run against a real facilitator with a
  funded wallet. Until that happens, "live mode works" is a code claim, not an
  operational one.
- **Calibration.** Machinery works and persists; no labelled outcomes exist, so
  it honestly reports `passthrough_untrained`.

## What is missing

| Gap | Severity | Note |
|-----|----------|------|
| Commercial-grade retrieval | High | Snippets only; no full-text extraction |
| Answer synthesis across sources | High | Claims are grounded excerpts, not answers |
| Real-facilitator settlement test | High | Needs testnet wallet + funded run |
| Public deployment | High | No hosted instance |
| Quality benchmark vs strong baselines | High | Harness proves invariants, not quality |
| Rate limiting / abuse controls | Medium | Not implemented |
| Bazaar / registry auto-registration | Medium | Manual |
| Durable evidence re-fetch (IPFS pinning) | Medium | Receipts store hashes, not content |
| Solana settlement | Low | Deliberately excluded from advertised networks |

## Honest verdict

The epistemic core is sound and the payment path is now real code rather than a
header check. What remains between this and revenue is not architecture — it is
retrieval quality, one funded settlement test, and a deployment.
