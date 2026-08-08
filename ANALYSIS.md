# End-to-End Analysis: Dependency and Transmission Chain

## Service dependency graph

```
veritas/server.py ─────────────┐
                         ├──> veritas/pipeline.py  (THE single engine)
veritas/autonomous/  ─────┘         │
                                    ├──> veritas/retrieval.py ──> veritas/autonomous/zero_key_retrieval.py
                                    │                                   ├── Wikipedia REST  (network)
                                    │                                   └── ddgs / DDG IA   (network, optional dep)
                                    ├──> veritas/hashing.py
                                    ├──> veritas/custody.py ──> CustodyStore (disk)
                                    └──> veritas/bayesian.py

veritas/server.py ──> veritas/x402.py        (challenge construction, atomic amounts)
           └──> veritas/facilitator.py (network: POST /verify, POST /settle)
           └──> veritas/payment_config.py ──> veritas/networks.py ──> veritas/x402.USDC_ASSETS
```

Two structural rules now hold, and both were previously violated:

1. **One engine.** `control_plane` used to contain a second, independent
   pipeline. The HTTP surface served a static 3-document corpus while the real
   retrieval was unreachable. Both now call `veritas.pipeline.run_research`.
2. **One source of truth for payability.** `supported_networks()` derives from
   `USDC_ASSETS`, so the service cannot advertise a network on which it cannot
   construct a payment.

## Network dependencies and failure behaviour

| Dependency | Required for | On failure |
|------------|--------------|------------|
| Wikipedia REST | Retrieval | Error recorded; other providers continue |
| ddgs / DDG IA | Retrieval | `dependency_missing` or error recorded; falls back to IA |
| All providers fail | Retrieval | `status: unavailable`, `billable: false`, HTTP 503 |
| Facilitator `/verify` | Live payment | **Fail closed** — HTTP 503, access denied |
| Facilitator `/settle` | Live payment | HTTP 402 `settlement_failed`, result withheld |
| Disk (receipts) | Auditability | Request still served; `persisted: false` reported |

The critical property: no network failure can produce a confident answer, and
no failure of ours is billed to the buyer.

## Transmission ordering (live mode)

```
402 challenge  ──>  buyer signs  ──>  X-PAYMENT header
                                          │
                              facilitator /verify   (fail closed)
                                          │
                                   run_research
                                          │
                        billable? ──no──> 503, no settlement
                                          │yes
                              facilitator /settle
                                          │
                         200 + X-PAYMENT-RESPONSE + custody receipt
```

Verify-before-work and settle-after-work is deliberate: a buyer is never
charged for a request that produced nothing deliverable.

## Verification path for the buying agent

1. Receive response with `evidence[].content_hash` and `custody_root`.
2. Re-hash each excerpt locally, or `POST /v1/verify`.
3. Re-run the custody chain with `veritas.custody.verify_chain_records` over
   the `custody_chain` delivered in the response. (This step was documented
   before the chain was actually delivered; true as of 2026-08-05.)
4. Re-fetch the receipt later at `GET /v1/receipts/{request_id}`.

Step 4 was impossible before: ledgers were in-memory and died with the request.

## Remaining chain weaknesses

- **Evidence content is not durably stored**, only its hash. A buyer verifying
  a week later can confirm the hash matches what we published, but cannot
  re-obtain the text from us if the source URL rots.
- **Facilitator settlement is untested against a real facilitator.** The client
  matches the documented API; that is not the same as having settled once.
- **Receipts are local disk**, so a multi-instance deployment needs shared
  storage before `/v1/receipts` is reliable behind a load balancer.
