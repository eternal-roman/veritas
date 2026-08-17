# Ecosystem loops — when they may turn

**Status: L0 plan.** Last verified 2026-08-16. None of these loops have
been observed to compound. `ECOSYSTEM.md` points here; it does not
restate `VISION.md`. A loop is marked turned only with a dated
transcript under `docs/program/fable/`.

Catalog A2A on this branch is **mesh TLS**: each agent hosts HTTPS,
`connect` / `pull-signals` pin the presented cert to the peer card.
There is no Veritas CA and no required public CA.

| Loop | What would turn it | Not before | Falsifier |
|------|--------------------|------------|-----------|
| Outcome → trust | Third-party signed audits `POST /v1/trust`. Catalog GETs never score. GET stays UNPROVEN until those records exist. | Independent auditor publication the seller cannot filter (G11). | 90 listed days, zero third-party audits → trust stays UNPROVEN. |
| Trust → discovery ranking | A registry we do not operate ranks published standing. | Public HTTPS + registry listing (human Stage 1). | We do not build a ranking registry. |
| Attestation → portable reputation (A16) | ERC-8004 or equivalent *after* Stage 1 existence. Spec-track only. | Public host + unsolicited traffic window started. | Implementing A16 before a stranger can dial us is theater. |
| Dispute path (A17) | D0 warranty + escrow forfeit on **catalog** claims (hash/persist/allowlist). No court. | Catalog is the paid SKU and at least one warranty is offered. | If no seller attaches a lock, A17 stays L0. |
| Other sellers adopt constitution | `/v1/constitution` + “Adopting this pattern.” Outreach is not code. | Stage 1 listed. | Zero external adopters after the Stage-1 window → park venue talk. |
| Challenge market / predators | W3 in `FALSIFIABLE_COMMERCE.md`. | Warranted catalog SKUs in the wild. | Challenge volume ≈ 0 at equilibrium. |
| Peer A2A | Pin-on-fetch mesh TLS for `pull-signals`. Book stays local. Introductions stay signed public-URL PEX. | Both peers `--tls`. | Do not turn introductions into a network. Degree cap 32 stays. |

```
PROPERTY: staged, falsifiable plan for compounding loops; none observed
EVIDENCE LEVEL: L0
NOT PROVEN: demand, registry ranking, ERC-8004, dispute volume, other sellers
```
