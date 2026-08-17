# DOME — do-me punch list

What is still unresolved after `main` @ `3b06f6b` plus this branch
(`feat/g2-signals-observe`). No GitHub issues were open. This is the
honest remainder, not a wish list.

Dated 2026-08-16. Status of each item is as of this branch's tip.

## This branch is doing

| Item | Why now |
|------|---------|
| **G2 signature check** | Local facilitator recovers the EIP-712 signer. Forged payments fail. |
| **Signals analytics** | Store was not enough. History + arithmetic analysis on venue prices. |
| **Observe-grade retrieval** | Wikipedia official extracts; served path re-observes search hits. |
| **Research is a primitive** | No auto-warranty. Not a truth arbiter. |

## Constitution gaps

| Id | Status | What is still true |
|----|--------|--------------------|
| **G2** | **closed on this branch** | EIP-712 recover of `transferWithAuthorization`. Balance and nonce-unused stay on-chain (G13). |
| **G13** | **open** | Local facilitator does not check nonce-unused or balance. Do not expose the control plane as a paid network surface. |
| **G12** | **closed (library + HTTP primitive)** | `escrow_bond` + `settle_forfeit`. Research does **not** auto-attach a warranty. Mainnet collect unproven. |

Closed earlier and not to be re-opened: G1, G6–G11, G9 (chain classify exists; mainnet still needs `VERITAS_RPC_URL`).

## Operational (blocks "next-level AI commerce" more than code does)

| Item | Severity | Note |
|------|----------|------|
| Public TLS host | High | None live. `docs/deploy/PUBLIC_HOST.md` is the operator runbook (Fly + Caddy). Needs a funded wallet, a domain or Fly app, and secrets this environment does not have. |
| Unsolicited buyers | High | Zero. Operator-run testnet only. |
| Mainnet settlement | High | None. Base Sepolia only. |
| PyPI publish | High | Job waits on `PYPI_TRUSTED_PUBLISHER=configured`. |
| Registry auto-registration | Medium | Manual. |
| Branch protection | Medium | Documented, not applied in Settings. |
| Human steps | — | Fund the wallet, TLS, PyPI publisher, GHCR push. |

## Product / methodology

| Item | Severity | Note |
|------|----------|------|
| Research-as-truth | Closed as product claim | Signals are the commercial surface. Research is an observe primitive. |
| Commercial-grade retrieval | Medium | Wikipedia extracts + notary.observe on the served path. Serper/DDG snippets stay labelled `search_snippet` until observed. Not a paid search stack. |
| D2 predicates | Medium | Synthesized claims are lexical-NLI gated, not warranted-D2. |
| Venue-cut calibration | Medium | Collusion economics for friendly self-challenges: named, not solved. |
| Quality vs strong baselines | High | Harness proves invariants, not quality. |
| Calibration | Medium | Reports `passthrough_untrained`. |
| A16–A18 | L0 | Named, unenforced. |

## Scale / operations leftovers

| Item | Severity | Note |
|------|----------|------|
| Balancer proof | Medium | `VERITAS_DATABASE_URL` is the seam. Two nodes behind a real balancer: not proven. |
| Shared receipts | Medium | File backend remains. When `VERITAS_DATABASE_URL` is set, `custody_receipts` is also upserted so a sibling can `GET /v1/receipts/{id}`. Two sqlite-file nodes: L1. Multi-host Postgres / real balancer: not proven. |
| Rate-limit fail-open | Low | When DATABASE_URL is set but the store cannot open, `shared_rate_limited` uses a process-local limiter (same limit/window). Unset URL still uses server.py buckets. Outage is not a free pass. |
| Abuse 10× load | Medium | Roadmap 6.3 acceptance unmet. |
| Docker hash-lock + signed SBOM | Medium | O15 partial. |
| Wallet ACLs on Windows (O16) | Medium | Linux/Docker is the deploy target. |
| Solana settlement | Low | Deliberately not advertised. |
| Tracing | Low | Logs + metrics exist; tracing is not claimed. |

## Defect register still `open` (`docs/program/STATE.md`)

P13 remainder (origin re-fetch still depends on the live URL), O6 (multi-instance), O15 remainder.

O5, L6, R10 closed on #157.

## Honesty bound

Closing G2 does **not** mean: on-chain nonce/balance check, public TLS host, unsolicited volume, or "the local facilitator settles."
Those stay on this list.
