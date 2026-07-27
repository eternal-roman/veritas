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
| Installable package (`pip install .`, single `veritas` namespace, `veritas-server` script) | Working; CI builds the wheel and installs it in a clean venv. Not yet on PyPI |
| Keyed Serper retrieval tier (env-configured, key never serialised, degrades to zero-key tier) | Working against fixture-shaped responses; not yet exercised against the live API with a real key |
| Buyer-side payment construction + spend policy (`veritas.payer`, key-free signer seam) | Working; L1 unit tests + L2 bounded model check (I1–I7, 8,720 traces, CI-gated). EIP-712 signature round-trip verified against `eth_account`. No on-chain settlement yet |
| Replay protection (`veritas.replay`) | Working; a resubmitted `X-PAYMENT` does the work once (tested). Single-instance scope — local disk |
| Venue constitution (`/v1/constitution`, `veritas/constitution.py`, v1.1) | Working, tested: every L1 article's enforcement pointer resolves; L0 articles carry none; `CONSTITUTION.md` sync-tested; gap G1 closed under the register's own discipline, G2 opened |
| Unified error contract (`veritas/errors.py`, `/v1/errors`) | Working, tested: registered codes, one envelope on every non-402 error including 422 and the previously code-less 503 unavailable body |
| Self-traversing discovery (`/.well-known/x402` links, `/llms.txt`, `/v1/schema`) | Working, tested; identity document no longer fabricates a base URL when none is configured |
| Wallet self-provisioning (`veritas/autonomous/wallet.py`) | Working, tested: locally minted encrypted keystore, owner-only files, plugs into the buyer Signer seam. Funding is external |
| `veritas-agent` CLI (init/serve/up/status) | Working, tested: provisioned config now reaches the env the HTTP server reads |
| MCP tools (`veritas-mcp`: research/verify/trust/constitution) | Working, tested against the SDK; local free-mode engine only, no payment path over MCP |
| Container + release workflow (`Dockerfile`, `release.yml`) | Dockerfile CI-built; release workflow inert until a maintainer configures PyPI Trusted Publishing |

## What is built but unproven

- **Live settlement.** The verify/settle calls are implemented against the
  x402 facilitator API but have never run against a real facilitator with a
  funded wallet. Until that happens, "live mode works" is a code claim, not an
  operational one.
- **Calibration.** Machinery works and persists; no labelled outcomes exist, so
  it honestly reports `passthrough_untrained`.
- **Aspirational constitution articles.** A16 (portable reputation), A17
  (dispute path), and A18 (registry liveness) are L0 by construction: named
  norms with no enforcement, each citing the roadmap phase expected to promote
  it. Publishing them proves nothing beyond the naming.
- **Known gap G2** (registered in the constitution, pinned by a witness test):
  the local facilitator simulator now enforces payment structure (G1 closed)
  but still does not verify signatures — weaker than the HTTP path's
  facilitator verification. The control plane must not be exposed as a paid
  network surface while G2 is open.
- **What still needs a human**, stated rather than hidden: funding the
  provisioned wallet, TLS/public deployment, the PyPI project + trusted
  publisher (release workflow is otherwise ready), and the GHCR push
  permission for the container.

## What is missing

| Gap | Severity | Note |
|-----|----------|------|
| Commercial-grade retrieval | High | Snippets only; no full-text extraction |
| Answer synthesis across sources | High | Claims are grounded excerpts, not answers |
| Real-facilitator settlement test | High | Needs testnet wallet + funded run |
| Public deployment | High | No hosted instance |
| Quality benchmark vs strong baselines | High | Harness proves invariants, not quality |
| Rate limiting / abuse controls | Medium | Not implemented |
| Shared replay/spend state across instances | Medium | Both are local disk; a second instance does not see them (roadmap 6.2) |
| Bazaar / registry auto-registration | Medium | Manual |
| Durable evidence re-fetch (IPFS pinning) | Medium | Receipts store hashes, not content |
| Solana settlement | Low | Deliberately excluded from advertised networks |

## Honest verdict

The epistemic core is sound and the payment path is now real code rather than a
header check. What remains between this and revenue is not architecture — it is
retrieval quality, one funded settlement test, and a deployment.

## Security / CI

| Control | State |
|---------|--------|
| CI workflows | On `main` — tests must pass (no soft-fail) |
| Import check | All top-level modules must import |
| Harness quality gates | Fidelity, custody, refusal discrimination, unavailability handling |
| Security scan job | Bandit + pip-audit, fail on high |
| Dependabot config | Present (weekly pip + Actions) |
| CODEOWNERS | Present |
| Branch protection | **Documented only** — admin must apply in Settings |
| Dependabot alerts product | Enable in repo Settings → Code security |
