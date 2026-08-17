"""Dogfood cycle 3 — a hostile caller.

Cycle 2 used the service the way a customer will. This one uses it the way an
attacker will, against the limits added in Phase O and the SSRF guards added
in Phase T. The point is the same: probe, and write down what actually
happens, rather than assert what we believe.

Probes, each targeting a way the service could be made to work for free, leak
something, or fall over:

    unpaid_flood        hammer the free unauthenticated surfaces
    oversized_body      a body far past the cap, at /v1/verify which re-hashes it
    payment_fuzzing     malformed X-PAYMENT headers, including ones shaped to crash
    nonce_flooding      distinct well-formed nonces with an unusable payment
    ssrf_facilitator    push the facilitator URL at internal and metadata hosts
    ssrf_scheme         push it at file:// and other non-HTTP schemes
    metrics_probe       reach the operator surface without the token
    error_leakage       force failures and grep every body for server internals

`python scripts/dogfood_cycle3.py [--out FILE]`. Exits non-zero if any probe
succeeds where it should have been refused. It performs no outbound network
request: the SSRF probes assert that the *guard* refuses before any socket is
opened, which is what the guard is for.
"""

from __future__ import annotations

import argparse
import base64
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

QUERY = "What is the x402 payment protocol?"

#: Strings that must never appear in a response body. Server paths, internal
#: hostnames, and the exception vocabulary that carries them.
LEAK_MARKERS = ("/home/", "/usr/lib", "Traceback", "File \"", "site-packages")


def _client(tmp: Path, **env):
    from fastapi.testclient import TestClient

    os.environ.update({
        "VERITAS_RUNTIME_DIR": str(tmp),
        "VERITAS_RATE_LIMIT_PER_MINUTE": "300",
        "VERITAS_METRICS_TOKEN": "operator-token",
        **env,
    })
    os.environ.pop("VERITAS_REQUIRE_PAYMENT", None) if "VERITAS_REQUIRE_PAYMENT" not in env else None
    import veritas.server as server
    importlib.reload(server)

    server.pull_signals = lambda query, **kw: [
        {
            "venue": "polymarket",
            "market_id": "m-cycle3",
            "question": query,
            "outcomes": [{"name": "Yes", "price": 0.5}],
            "observed_at": "2026-08-17T00:00:00Z",
            "source_url": "https://gamma-api.polymarket.com/markets/m-cycle3",
            "method": "veritas.signals.v1",
            "note": "market-implied prices, not a verdict",
        }
    ]
    return server, TestClient(server.app, raise_server_exceptions=False)


def _finding(name, expected, observed, ok, **extra):
    return {"probe": name, "expected": expected, "observed": observed,
            "refused": ok, **extra}


def probe_unpaid_flood(tmp: Path) -> dict[str, Any]:
    """The free surfaces are the ones anyone can hammer."""
    _server, client = _client(tmp / "flood", VERITAS_RATE_LIMIT_PER_MINUTE="20")
    codes = [client.get("/v1/trust").status_code for _ in range(40)]
    limited = codes.count(429)
    ok = limited > 0 and client.get("/health").status_code == 200
    return _finding(
        "unpaid_flood",
        "the limiter engages, and /health keeps answering through it",
        f"{limited}/40 refused with 429; health={client.get('/health').status_code}",
        ok,
    )


def probe_oversized_body(tmp: Path) -> dict[str, Any]:
    """/v1/verify re-hashes what it is sent, so size is work."""
    _server, client = _client(tmp / "big", VERITAS_RATE_LIMIT_PER_MINUTE="0")
    response = client.post("/v1/verify", json={
        "content": "A" * 2_000_000, "content_hash": "sha256:" + "0" * 64,
    })
    ok = response.status_code == 413 and response.json().get("error") == "request_too_large"
    return _finding(
        "oversized_body",
        "413 request_too_large, refused before the body is hashed",
        f"{response.status_code}, error={response.json().get('error')}",
        ok,
    )


#: Payloads we can already tell are inadmissible. None may cost a facilitator
#: round trip: judging them needs no outside opinion.
PAYMENT_FUZZ_DOOMED = [
    ("empty", ""),
    ("not_base64", "!!!!not base64!!!!"),
    ("base64_not_json", base64.b64encode(b"\x00\x01\x02plain bytes").decode()),
    ("json_not_object", base64.b64encode(b"[1,2,3]").decode()),
    ("null_nonce", base64.b64encode(json.dumps(
        {"payload": {"authorization": {"nonce": None}}}).encode()).decode()),
    ("nonce_wrong_type", base64.b64encode(json.dumps(
        {"payload": {"authorization": {"nonce": {"$ne": 1}}}}).encode()).decode()),
    ("huge_nonce", base64.b64encode(json.dumps(
        {"payload": {"authorization": {"nonce": "0x" + "ab" * 5000}}}).encode()).decode()),
    ("sql_ish_nonce", base64.b64encode(json.dumps(
        {"payload": {"authorization": {"nonce": "0x' OR 1=1 --"}}}).encode()).decode()),
]

#: Payloads carrying a well-formed nonce. These legitimately reach the
#: facilitator — whether a signature is valid is not ours to decide — and must
#: still be refused. Listing them separately keeps the amplification
#: measurement above honest rather than merely small.
PAYMENT_FUZZ_PLAUSIBLE = [
    ("deeply_nested", base64.b64encode(json.dumps(
        {"payload": {"authorization": {"nonce": "0x" + "ab" * 32}},
         "junk": [[[[["deep"]]]]]}).encode()).decode()),
    ("unicode_padding", base64.b64encode(json.dumps(
        {"payload": {"authorization": {"nonce": "0x" + "cd" * 32}},
         # The escape, not the character: a raw bidi override in source is
         # a trojan-source risk in its own right (bandit B613).
         "note": "\u202e" * 500}).encode()).decode()),
]


def probe_payment_fuzzing(tmp: Path) -> dict[str, Any]:
    """Junk payment headers must be cheap for us and useless to the caller.

    Cheap matters as much as useless. The first run of this cycle found that
    every structurally doomed payload still cost an outbound facilitator round
    trip, so an unpaid caller could spend our request budget one junk header
    at a time. The facilitator here counts its calls so that stays measured
    rather than assumed.
    """
    server, client = _client(
        tmp / "fuzz",
        VERITAS_REQUIRE_PAYMENT="true",
        VERITAS_PUBLIC_URL="https://veritas.example",
        VERITAS_PAY_TO="0x" + "22" * 20,
        VERITAS_NETWORK="eip155:84532",
        VERITAS_FACILITATOR="https://facilitator.invalid",
        VERITAS_RATE_LIMIT_PER_MINUTE="0",
    )

    from veritas.facilitator import VerificationResult

    class _Counting:
        calls = 0

        def verify(self, payload, requirements):
            type(self).calls += 1
            return VerificationResult(False, invalid_reason="rejected_by_harness")

        def settle(self, payload, requirements):  # pragma: no cover - unreachable here
            raise AssertionError("settle must never be reached by a junk payload")

    server.get_facilitator = lambda *a, **k: _Counting()

    served, leaks, statuses = [], [], {}

    def send(name, header):
        response = client.post("/v1/signals", json={"query": QUERY},
                               headers={"X-PAYMENT": header})
        statuses[name] = response.status_code
        if response.status_code == 200:
            served.append(name)
        if any(marker in response.text for marker in LEAK_MARKERS):
            leaks.append(name)

    for name, header in PAYMENT_FUZZ_DOOMED:
        send(name, header)
    doomed_cost = _Counting.calls
    for name, header in PAYMENT_FUZZ_PLAUSIBLE:
        send(name, header)

    ok = (
        not served and not leaks
        and all(s < 500 for s in statuses.values())
        and doomed_cost == 0
    )
    return _finding(
        "payment_fuzzing",
        f"nothing served, nothing leaked, no 5xx, and no facilitator round trip "
        f"for any of the {len(PAYMENT_FUZZ_DOOMED)} structurally doomed payloads",
        f"served={served}, leaked={leaks}, "
        f"facilitator_calls_for_doomed={doomed_cost}, "
        f"facilitator_calls_total={_Counting.calls}, statuses={statuses}",
        ok,
        found_defect=(
            f"First run: all {len(PAYMENT_FUZZ_DOOMED)} doomed payloads caused an "
            "outbound facilitator call, so an unpaid caller could spend our "
            "request budget one junk header at a time. The structural nonce "
            "check now runs first; fixed in the same commit as this cycle. The "
            "remaining calls are for payloads carrying a well-formed nonce, "
            "which only the facilitator can judge."
        ),
    )


def probe_nonce_flooding(tmp: Path) -> dict[str, Any]:
    """Distinct well-formed nonces with a payment nothing can verify. Each
    must be refused before a retrieval pass, or an attacker buys work with
    signatures they never made."""
    _server, client = _client(
        tmp / "nonces",
        VERITAS_REQUIRE_PAYMENT="true",
        VERITAS_PUBLIC_URL="https://veritas.example",
        VERITAS_PAY_TO="0x" + "22" * 20,
        VERITAS_NETWORK="eip155:84532",
        # Unroutable: verification cannot succeed, so nothing may be served.
        VERITAS_FACILITATOR="http://127.0.0.1:1",
        VERITAS_RATE_LIMIT_PER_MINUTE="0",
    )
    import veritas.server as server
    calls = {"n": 0}
    inner = server.pull_signals

    def counting(query, **kw):
        calls["n"] += 1
        return inner(query, **kw)

    server.pull_signals = counting

    statuses = []
    for i in range(25):
        header = base64.b64encode(json.dumps({
            "x402Version": 1, "scheme": "exact", "network": "eip155:84532",
            "payload": {"signature": "0x" + "cd" * 65,
                        "authorization": {"nonce": f"0x{i:064x}"}},
        }).encode()).decode()
        statuses.append(client.post("/v1/signals", json={"query": QUERY},
                                    headers={"X-PAYMENT": header}).status_code)
    ok = calls["n"] == 0 and 200 not in statuses
    return _finding(
        "nonce_flooding",
        "no retrieval pass consumed, nothing served",
        f"retrievals={calls['n']}, statuses={sorted(set(statuses))}",
        ok,
        authorizations_recorded=len(server.ledger.summary()["states"]),
    )


SSRF_HOSTS = [
    "http://169.254.169.254/latest/meta-data/",   # cloud instance metadata
    "http://127.0.0.1:8000/health",                # loopback
    "http://10.0.0.1/internal",                    # RFC1918
    "http://192.168.1.1/admin",                    # RFC1918
    "http://[::1]:8000/",                          # loopback, v6
    "http://metadata.google.internal/",            # metadata by name
]

SSRF_SCHEMES = [
    "file:///etc/passwd",
    "gopher://127.0.0.1:11211/_stats",
    "ftp://127.0.0.1/",
    "data:text/plain,hello",
]


def probe_ssrf_facilitator(_tmp: Path) -> dict[str, Any]:
    """The facilitator URL is operator configuration, but an operator can be
    tricked and a compromised config file is a real path. The guard must
    refuse before a socket is opened, not after a response comes back."""
    from veritas.safeurl import UnsafeUrlError, assert_public_destination

    reached = []
    for url in SSRF_HOSTS:
        try:
            assert_public_destination(url)
            reached.append(url)
        except UnsafeUrlError:
            pass
    return _finding(
        "ssrf_facilitator",
        "every internal, loopback and metadata destination refused",
        f"reached={reached}" if reached else "all refused",
        not reached,
    )


def probe_ssrf_scheme(_tmp: Path) -> dict[str, Any]:
    from veritas.safeurl import UnsafeUrlError, require_http_url

    reached = []
    for url in SSRF_SCHEMES:
        try:
            require_http_url(url)
            reached.append(url)
        except UnsafeUrlError:
            pass
    return _finding(
        "ssrf_scheme",
        "every non-HTTP scheme refused",
        f"reached={reached}" if reached else "all refused",
        not reached,
    )


def probe_metrics_without_token(tmp: Path) -> dict[str, Any]:
    """Counters include settlements, which are revenue."""
    _server, client = _client(tmp / "metrics", VERITAS_RATE_LIMIT_PER_MINUTE="0")
    attempts = {
        "no_header": client.get("/metrics"),
        "wrong_token": client.get("/metrics", headers={"Authorization": "Bearer nope"}),
        "empty_bearer": client.get("/metrics", headers={"Authorization": "Bearer "}),
        "basic_auth": client.get("/metrics", headers={"Authorization": "Basic b3A6b3A="}),
    }
    served = [name for name, r in attempts.items() if r.status_code == 200]
    bodies_leak = [name for name, r in attempts.items() if "veritas_" in r.text]
    ok = not served and not bodies_leak
    return _finding(
        "metrics_probe",
        "no counter reaches an unauthenticated caller",
        f"served={served}, leaked={bodies_leak}, "
        f"statuses={ {k: v.status_code for k, v in attempts.items()} }",
        ok,
    )


def probe_error_leakage(tmp: Path) -> dict[str, Any]:
    """Force every failure we can reach and grep the bodies for internals."""
    _server, client = _client(tmp / "leak", VERITAS_RATE_LIMIT_PER_MINUTE="0")
    import veritas.server as server

    def exploding(query, **kw):
        raise RuntimeError("/home/veritas/secret/path exploded")

    server.pull_signals = exploding

    responses = {
        "unhandled": client.post("/v1/signals", json={"query": QUERY}),
        "validation": client.post("/v1/signals", json={"query": "x"}),
        "missing_receipt": client.get("/v1/receipts/nope"),
        "bad_verify": client.post("/v1/verify", json={"content": "a"}),
    }
    leaks = {
        name: [m for m in LEAK_MARKERS if m in r.text]
        for name, r in responses.items()
    }
    leaking = {k: v for k, v in leaks.items() if v}
    unparseable = [
        name for name, r in responses.items()
        if not r.headers.get("content-type", "").startswith("application/json")
    ]
    ok = not leaking and not unparseable
    return _finding(
        "error_leakage",
        "every failure is JSON and names no server internals",
        f"leaking={leaking}, non_json={unparseable}",
        ok,
    )


PROBES = (
    probe_unpaid_flood,
    probe_oversized_body,
    probe_payment_fuzzing,
    probe_nonce_flooding,
    probe_ssrf_facilitator,
    probe_ssrf_scheme,
    probe_metrics_without_token,
    probe_error_leakage,
)


def run() -> dict[str, Any]:
    findings = []
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for probe in PROBES:
            try:
                findings.append(probe(tmp))
            except Exception as exc:  # noqa: BLE001 - a crash IS the finding
                findings.append(_finding(
                    probe.__name__.removeprefix("probe_"),
                    "the probe completes",
                    f"raised {type(exc).__name__}: {exc}",
                    False,
                ))
    return {
        "cycle": 3,
        "title": "Hostile caller",
        "note": (
            "No outbound request is made. The SSRF probes assert the guard "
            "refuses before a socket is opened, which is what the guard is for."
        ),
        "limits_are": "in-process; behind a load balancer each node has its own",
        "probes": findings,
        "refused": sum(1 for f in findings if f["refused"]),
        "total": len(findings),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", help="Write the JSON report here as well as stdout.")
    args = parser.parse_args(argv)

    report = run()
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n")
    return 0 if report["refused"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
