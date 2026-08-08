# Dogfooding cycles

Each cycle uses the service the way someone outside this repository will, and
writes down what actually happened. A cycle that only re-asserts what we
already believed is not a cycle; the value is in the defects, so each report
records the ones its first run found.

They are runnable by anyone, against their own instance:

```bash
python scripts/dogfood_cycle1.py --out /tmp/cycle1.json   # cold install first-boot
python scripts/dogfood_cycle2.py --out /tmp/cycle2.json   # paying buyer
python scripts/dogfood_cycle3.py --out /tmp/cycle3.json   # hostile caller
python scripts/dogfood_cycle4.py --out /tmp/cycle4.json   # operator economics
```

Both print JSON and exit non-zero on any failure. `tests/test_dogfood.py` runs
them in CI, so a regression in the money path or in the limits breaks the
build rather than quietly invalidating a committed report.

| Cycle | Perspective | Report | Defects it found |
|---|---|---|---|
| 1 | Cold autonomous install / first-boot | [`cycle1/report.json`](cycle1/report.json) | 0 (first green run) |
| 2 | Paying buyer | [`cycle2/report.json`](cycle2/report.json) | 1 |
| 3 | Hostile caller | [`cycle3/report.json`](cycle3/report.json) | 1 |
| 4 | Operator economics | [`cycle4/report.json`](cycle4/report.json) | 2 |
| 5 | Ecosystem participant | not yet run | — |


## Cycle 1 — cold autonomous install / first-boot

Was gated on Phase N0. Now that N0–N1.3 are on main, this cycle checks whether
an autonomous agent can **first-boot** the free-mode product without a human
editing config: console-script install contract, required modules, free-mode
bootstrap, discovery (including notarize / attest / pack), offline research,
offline notary with `evidence_pack`, and free pack verify.

**Boundary:** does **not** re-run blank-machine `pip install` from PyPI (CI's
package job owns wheel install + hash-pinned deps). Measures the agent
first-boot path after the package is available. **No on-chain settlement.**

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

## Cycle 4 — operator economics

Asks the question an operator actually has — *am I making money, and how would
I know?* — under one rule: every answer must come out of `veritas-ops`, not
out of the script's own bookkeeping. A number that cannot be obtained that way
is the finding.

**Found (two):** `veritas-ops owed` answered **zero** while `veritas-ops
reconcile` flagged an unresolved settlement. Delivered work is delivered
whether the facilitator said no, said nothing, or was never asked, so an
indeterminate settlement is exposure and is now counted — broken out by state,
with the amount at risk per asset, because an operator acts differently on
each. Fixing that then exposed the second: `reconcile` labelled the same entry
`settlement_failed` *and* `settlement_indeterminate`, telling the operator
there were two problems when there was one.

The cycle now cross-checks the two commands against each other, so they cannot
drift apart again silently.

### Measured, supplied, and neither

The report separates these deliberately, because a unit-economics table that
mixes them is how invented numbers get quoted back as facts.

- **Measured:** provider calls per request, evidence bytes, handler wall time,
  atomic amounts settled, every ledger state transition.
- **Operator-supplied:** the per-provider cost. Nothing here can verify a
  provider's list price, so the shipped table is empty and margin is withheld
  rather than computed against an assumed zero. The cycle passes an explicit,
  labelled figure purely to demonstrate the arithmetic.
- **Not a production figure:** retrieval runs against the offline corpus, so
  the wall times are a floor — a real provider call dominates them. The
  metering column is whole milliseconds, which is too coarse to resolve the
  offline path at all; it reads 0.
