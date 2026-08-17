# DOME — do-me punch list

What is still unresolved after `main` @ `9bf043a` (product glue #155 +
VCAE/signals #156) plus the product-quality pass on this branch.
No GitHub issues were open. This is the honest remainder, not a wish list.

Dated 2026-08-16. Status of each item is as of this branch's tip.

## Closed on this branch

| Item | What landed |
|------|-------------|
| **O5** | Runtime dir is absolute (`veritas.runtime`). `/readyz` fails if it cannot be written. `veritas-agent` binds `{base-dir}/runtime`. Legacy `./.veritas_runtime` still wins if present. |
| **L6** | Research questions are stored as `query_hash` only. GET `/v1/receipts` never returns a free-text question. Origin URLs (notarize) stay so verify can re-fetch. |
| **R10** | Paid Serper is not registered in free mode unless `VERITAS_SERPER_IN_FREE_MODE` is set. |
| **VCAE collect** | GET never serves the authorization signature. Forfeit re-runs `evaluate_challenge` on warranty+deliverable. Release is loopback-only. |
| **Buyer verify** | `veritas-buy --content` unpacks `verify_content_hash`'s `(ok, meta)` tuple. |

## Constitution gaps

| Id | Status | What is still true |
|----|--------|--------------------|
| **G2** | **open** | Local facilitator checks payment *structure*, not signatures. Do not expose the control plane as a paid network surface while this is open. |
| **G12** | **closed (library + HTTP primitive)** | `escrow_bond` + `settle_forfeit`. HTTP forfeit re-executes the challenge. Research does **not** auto-attach a warranty. Mainnet collect unproven. G2 still open. |

Closed earlier and not to be re-opened: G1, G6–G11, G9 (chain classify exists; mainnet still needs `VERITAS_RPC_URL`).

## Operational (blocks "next-level AI commerce" more than code does)

| Item | Severity | Note |
|------|----------|------|
| Public TLS host | High | None. Agents cannot find a live seller. |
| Unsolicited buyers | High | Zero. Operator-run testnet only. |
| Mainnet settlement | High | None. Base Sepolia only. |
| PyPI publish | High | Job waits on `PYPI_TRUSTED_PUBLISHER=configured`. |
| Registry auto-registration | Medium | Manual. |
| Branch protection | Medium | Documented, not applied in Settings. |
| Human steps | — | Fund the wallet, TLS, PyPI publisher, GHCR push. |

## Product / methodology

| Item | Severity | Note |
|------|----------|------|
| Research-as-truth | High | Placeholder. Market *prices* are a signal, not a second arbiter. |
| Commercial-grade retrieval | High | Snippets + optional notary observe. Not a paid search stack. |
| Research does not auto-warrant | Medium | G12 is a primitive. Paid `/v1/research` ships no lock. |
| D2 predicates | Medium | Synthesized claims are lexical-NLI gated, not warranted-D2. |
| Venue-cut calibration | Medium | Collusion economics for friendly self-challenges: named, not solved. |
| Quality vs strong baselines | High | Harness proves invariants, not quality. |
| Calibration | Medium | Reports `passthrough_untrained`. |
| A16–A18 | L0 | Named, unenforced. |

## Scale / operations leftovers

| Item | Severity | Note |
|------|----------|------|
| Balancer proof | Medium | `VERITAS_DATABASE_URL` is the seam. Two nodes behind a real balancer: not proven. |
| Shared receipts | Medium | Receipts are files. Multi-host needs a shared disk or a later object store. |
| Rate-limit fail-open | Low | Shared limiter returns "not limited" if the store cannot open, so an outage does not 503 the API. |
| Abuse 10× load | Medium | Roadmap 6.3 acceptance unmet. |
| Docker hash-lock + signed SBOM | Medium | O15 partial. |
| Wallet ACLs on Windows (O16) | Medium | Linux/Docker is the deploy target. |
| Solana settlement | Low | Deliberately not advertised. |
| Tracing | Low | Logs + metrics exist; tracing is not claimed. |

## Defect register still `open` (`docs/program/STATE.md`)

P13 (evidence text — *partially closed by #155, excerpt store exists*), O6 (partially closed by shared store), O15 remainder.

## Honesty bound

Closing G12 as a library/HTTP primitive does **not** mean: deployed vault contract, mainnet collect, signature-checked local facilitator, unsolicited volume, auto-warranted research, or "commercial-grade research."
Those stay on this list.
