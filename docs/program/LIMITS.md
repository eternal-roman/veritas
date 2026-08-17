# Limits and outliers

Snapshot of `main` @ `b1cf532` ([#160](https://github.com/eternal-roman/veritas/pull/160)).
Dated 2026-08-16. Measured or read from the code — not estimated.

This is a log, not a wish list. Closing a row here means a test pins the
new number or the claim is gone. It does not mean the product is complete.

```
PROPERTY: current hard limits and the surfaces that do not match the rest
EVIDENCE LEVEL: L1 (constants and tests on this tip)
CHECKED ARTIFACT: this file vs veritas/*.py + DOME.md + STATUS.md
NOT PROVEN: live load, WAN reachability, mainnet, unsolicited demand
```

## Numeric limits (code)

| Limit | Value | Where |
|-------|-------|-------|
| Paid work budget | 25s (`MAX_WORK_SECONDS`) | `veritas/server.py` |
| Concurrent research slots | 8 (env `VERITAS_MAX_CONCURRENT_RESEARCH`) | sheds 503, does not queue |
| Request body | 256 KiB (env `VERITAS_MAX_BODY_BYTES`) | same |
| Verify content | 200_000 chars | `MAX_VERIFY_CONTENT_CHARS` |
| Per-caller rate | 300 / 60s (env `VERITAS_RATE_LIMIT_PER_MINUTE`) | in-process unless `VERITAS_DATABASE_URL` |
| Authorization usable floor | 5s work + 20s settle margin | `veritas/deadline.py` |
| Buyer authorization validity | 1..3600s | `veritas/payer.py` |
| Wikipedia extract | 4_000 chars | `WIKIPEDIA_EXTRACT_CHARS` |
| Evidence retention | 30 days default (1..3650) | `VERITAS_RETENTION_DAYS` |
| Introductions published | 32 public-URL peers | `peer_intro.DEFAULT_LIMIT` |
| Self-signed TLS life | 365 days | `peer_tls._VALIDITY_DAYS` |
| TLS key | RSA 2048 | `peer_tls._RSA_KEY_SIZE` |
| Default bind | `127.0.0.1:8000` | loopback; not a public host |
| Default network | `eip155:84532` (Base Sepolia) | mainnet needs explicit ack |
| Price (advertised) | 10_000 atomic USDC ($0.01) | live mode only |

`/health` and `/readyz` are outside the rate-limit budget.

## Operational limits (a human owns these)

| Limit | Value now |
|-------|-----------|
| Public seller URL | none. Strangers still need a first URL. |
| Unsolicited buyers | 0 |
| Mainnet settlements | 0 |
| Testnet settlements | operator-run only; count lives in `docs/program/fable/settlement/` |
| PyPI | unpublished (`PYPI_TRUSTED_PUBLISHER` not configured) |
| Registry listing | `listed_on_registry: false` |
| Branch protection | documented, not applied |
| GHCR | not pushed from here |

## Honesty limits (not claimed)

- **G13 open.** Default local facilitator does not check nonce-unused or
  balance. Optional RPC checks (`VERITAS_FACILITATOR_CHAIN_CHECKS=1` and
  `VERITAS_RPC_URL`) do not close the gap.
- **G12** is a library + HTTP primitive. Research does not auto-attach a
  warranty. Mainnet collect unproven.
- **G2 closed** is signature recover only. It is not "the local facilitator
  settles."
- Signals are **prices, not verdicts**. Arithmetic `analyze`, not a forecast.
- Research is an **observe primitive**, not a truth arbiter.
- Peer connect is **not** the program Mesh Runner and **not** a public seller.
- `stored_excerpt` is not a fresh observation. Origin independence still
  needs the live URL (P13 remainder).
- Shared receipts / replay / trust across a real balancer: **not proven** (O6).
- SBOM is checksummed, **not signed** (O15 remainder).
- Calibration reports `passthrough_untrained`.
- Harness proves invariants on a 3-document corpus, not quality vs baselines.
- A16–A18 are L0: named, unenforced.

## Outliers

Surfaces that do not match the rest of the product, or the locked design.

| Outlier | What is true | Why it is an outlier |
|---------|--------------|----------------------|
| TLS key algorithm | Issued as RSA-2048 | Locked design (`docs/design/IDENTITY_TLS_MESH.md`) says ECDSA P-256. Commerce key is secp256k1 either way; the TLS key is still not the wallet. |
| `connect` TLS pin | Card may carry `tls.fingerprint` | `connect` does not verify the presented cert against that pin. Design says WAN connect fails closed on mismatch. |
| HTTP introductions | `GET /v1/peer/introductions` is mounted | Empty without a commerce signer. The server path never injects `sign_text`, so the served list is `[]` even when the local book has public peers. |
| Binding message | `peer_tls` EIP-191s the fingerprint string | Design specifies a multi-line `veritas-peer-tls-v1` canonical message (fingerprint + SAN + address + network). |
| Dual mesh words | `veritas.peer` is product A2A | `veritas.ecosystem_cycle` / `TRACK_MESH_RUNNER` is a different, offline kernel. Same repo; not the same network. |
| Dual product lead | Signals are the commercial surface | `POST /v1/research` is still a paid HTTP product. Observe primitive, not removed. |
| Mixed retrieval grade | Wikipedia = official extracts | Serper/DDG stay `search_snippet` until `notary.observe`. One path, two grades. |
| Shared-store default | File backend unless `VERITAS_DATABASE_URL` | Receipts, rate-limit, ledger, credits can share — only when the operator sets the URL. Two processes without it diverge. |
| Rate-limit fallback | Process-local limiter if the shared store cannot open | Same numeric cap. Outage is not a free pass. It is also not a cluster limit. |
| Optional G13 path | RPC nonce/balance exist | Default path still skips the chain. The witness that the simulator does not check nonce/balance still passes. |
| Stale measured table | `docs/program/STATE.md` "Tests passing" = 420 (2026-08-07) | Suite on this tip is 1098 passed, 2 skipped (2026-08-16, this workspace). The table was not updated when the suite grew. |
| STATUS container line | "Image not built in CI" | CI job **Container build** runs on this tip and is green. The STATUS row is stale. |
| Windows wallet ACLs | POSIX owner-only; Windows warns | Deploy target is Linux/Docker. O16 remains reported, not enforced on NTFS. |

## What this snapshot is not

Not a public seller. Not mainnet. Not a signed SBOM. Not ACME / NAT
traversal. Not a close of G13. Not the Mesh Runner.

See `DOME.md` for the punch list this log was taken from.
