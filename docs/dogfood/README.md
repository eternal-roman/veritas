# Dogfooding cycles

Each cycle uses the service the way someone outside this repository will, and
writes down what actually happened. A cycle that only re-asserts what we
already believed is not a cycle; the value is in the defects, so each report
records the ones its first run found.

They are runnable by anyone, against their own instance:

```bash
python scripts/dogfood_cycle2.py --out /tmp/cycle2.json   # paying buyer
python scripts/dogfood_cycle3.py --out /tmp/cycle3.json   # hostile caller
```

Both print JSON and exit non-zero on any failure. `tests/test_dogfood.py` runs
them in CI, so a regression in the money path or in the limits breaks the
build rather than quietly invalidating a committed report.

| Cycle | Perspective | Report | Defects it found |
|---|---|---|---|
| 1 | Cold autonomous install | not yet run — gated on Phase N0 | — |
| 2 | Paying buyer | [`cycle2/report.json`](cycle2/report.json) | 1 |
| 3 | Hostile caller | [`cycle3/report.json`](cycle3/report.json) | 1 |
| 4 | Operator economics | not yet run | — |
| 5 | Ecosystem participant | not yet run | — |

## Cycle 2 — paying buyer

Drives the real buyer path (`veritas.buyer_payment.pay_via_policy`, EIP-712
signature over the challenge we actually publish) against the real server.
Seven scenarios: the happy path, a connection dropped after settlement, a
distinct request on a spent authorization, a facilitator that never answers,
one that answers no, what our own published buyer helper concludes about an
unresolved settlement, and an authorization that expires mid-work.

**Found:** resubmitting an authorization with a *different* question returned
200 with the earlier deliverable. Re-delivery is right when the buyer is
retrying the request they paid for; when the question differs, the earlier
answer is an answer to a question nobody asked, and the only sign of the
mismatch was the echoed `query` — which a client has no reason to inspect on a
success. Now `409 payment_authorization_bound_to_another_request`, naming the
request the authorization did buy.

**Boundary, and it is a real one:** the facilitator is a local stand-in. This
sandbox has no route to Base Sepolia or to any public facilitator, so **no
on-chain settlement was performed and none is claimed**. Everything on either
side of the facilitator call is exercised: challenge construction, spend caps,
signing, verification, the authorization state machine,
delivery-before-settle ordering, replay, and the ledger.

## Cycle 3 — hostile caller

Eight probes: flooding the free surfaces, an oversized body at the endpoint
that re-hashes what it is sent, malformed `X-PAYMENT` headers, nonce flooding,
SSRF against internal/metadata hosts and non-HTTP schemes, reaching `/metrics`
without the token, and grepping every forced failure for server internals.

**Found:** every structurally doomed payment payload still cost an outbound
facilitator round trip, because the nonce check ran *after* verification. An
unpaid caller could spend our outbound request budget one junk header at a
time. The structural check is free and changes no state, so it now runs first:
zero facilitator calls for the eight doomed payloads, down from eight. The
payloads that do still reach the facilitator carry well-formed nonces, which
only the facilitator can judge — the report separates the two so the
measurement stays honest rather than merely small.

**Boundary:** no outbound request is made. The SSRF probes assert the *guard*
refuses before a socket is opened, which is what the guard is for — they do
not prove that a real request to a real metadata endpoint would fail.

The limits these probes exercise are all in-process. Behind a load balancer
each node has its own budget; that needs shared state (roadmap 6.2).
