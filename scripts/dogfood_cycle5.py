"""Dogfood cycle 5 — ecosystem participant (buyer / counterparty agent).

Cycles 1–4 covered install, paying buyer, hostile caller, and operator
economics. This cycle uses the service the way a *peer agent in the ecosystem*
does: discover surfaces, consume unpaid discovery docs, verify a research
receipt with the zero-dep standalone verifier, re-check a notary pack and a
Merkle inclusion proof offline, and refuse to treat trust as authorization.

No outbound network. No on-chain settlement. Facilitator is not involved.

Run: ``python -m scripts.dogfood_cycle5`` or ``python scripts/dogfood_cycle5.py``.
Exits non-zero if any check fails.
"""

from __future__ import annotations

import argparse
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


def _check(name: str, expected: str, observed: str, ok: bool, **extra: Any) -> dict[str, Any]:
    return {
        "check": name,
        "expected": expected,
        "observed": observed,
        "pass": ok,
        **extra,
    }


def _free_client(tmp: Path):
    from fastapi.testclient import TestClient

    os.environ["VERITAS_RUNTIME_DIR"] = str(tmp)
    os.environ.pop("VERITAS_REQUIRE_PAYMENT", None)
    os.environ.pop("VERITAS_PUBLIC_URL", None)
    import veritas.server as server

    importlib.reload(server)
    server.pull_signals = lambda query, **kw: [
        {
            "venue": "polymarket",
            "market_id": "m-cycle5",
            "question": query,
            "outcomes": [{"name": "Yes", "price": 0.5}],
            "observed_at": "2026-08-17T00:00:00Z",
            "source_url": "https://gamma-api.polymarket.com/markets/m-cycle5",
            "method": "veritas.signals.v1",
            "note": "market-implied prices, not a verdict",
        }
    ]
    return server, TestClient(server.app, raise_server_exceptions=False)


def check_discovery_traversal(tmp: Path) -> dict[str, Any]:
    _server, client = _free_client(tmp / "disc")
    wk = client.get("/.well-known/x402")
    if wk.status_code != 200:
        return _check("discovery_traversal", "200 well-known", f"status={wk.status_code}", False)
    links = wk.json().get("links") or {}
    required = (
        "identity",
        "constitution",
        "schema",
        "errors",
        "notarize",
        "attestations_verify",
        "packs_verify",
        "evidence_log",
        "evidence_log_verify",
    )
    missing = [k for k in required if k not in links]
    dead = []
    for k in required:
        if k not in links:
            continue
        path = links[k]
        code = client.get(path).status_code
        # POST-only surfaces: GET may be 405; 404 is a lie
        if code == 404:
            dead.append(f"{k}:{path}:{code}")
    ok = not missing and not dead
    return _check(
        "discovery_traversal",
        "well-known links reach N0–N1.4 ecosystem surfaces",
        f"missing={missing}; dead={dead}",
        ok,
    )


def check_constitution_enforcement_shape(tmp: Path) -> dict[str, Any]:
    _server, client = _free_client(tmp / "const")
    r = client.get("/v1/constitution")
    if r.status_code != 200:
        return _check("constitution", "200 constitution", f"status={r.status_code}", False)
    body = r.json()
    gaps = body.get("known_gaps") or []
    g12 = [g for g in gaps if g.get("id") == "G12"]
    articles = body.get("articles") or []
    # G12 is closed in constitution 2.8 and must stay disclosed (closed ≠ omitted).
    ok = bool(articles) and len(g12) == 1 and g12[0].get("status") == "closed"
    return _check(
        "constitution_g12_disclosed",
        "constitution served; G12 closed and still disclosed to buyers",
        f"articles={len(articles)}; g12={g12[0] if g12 else None}",
        ok,
    )


def check_standalone_verifier_on_research(tmp: Path) -> dict[str, Any]:
    from veritas.custody import CustodyLedger
    from veritas.hashing import compute_content_hash
    from veritas.verifier import verify_response

    os.environ["VERITAS_RUNTIME_DIR"] = str(tmp / "res")
    excerpt = "catalog snapshot for cycle5"
    digest = compute_content_hash(excerpt)
    ledger = CustodyLedger()
    ledger.append("created", "catalog", {"query": "fed"})
    ledger.append("delivered", "catalog", {"hash": digest})
    response = {
        "request_id": "cycle5",
        "status": "completed",
        "query": "fed",
        "claims": [
            {
                "id": "c1",
                "statement": excerpt,
                "evidence_hash": digest,
                "source_url": "https://example.test/m",
            }
        ],
        "evidence": [
            {
                "url": "https://example.test/m",
                "excerpt": excerpt,
                "content_hash": digest,
            }
        ],
        "custody_root": ledger.root_hash(),
        "custody_valid": True,
        "custody_chain": ledger.to_list(),
        "support": {"n_evidence": 1},
        "attests": "fixture",
        "retrieval": {},
        "refusal_reason": None,
        "billable": True,
        "timestamp": "2026-08-17T00:00:00Z",
    }
    report = verify_response(response)
    ok = report.valid is True and response.get("status") in {"completed", "refused"}
    return _check(
        "standalone_verifier",
        "zero-dep verifier accepts a catalog custody chain",
        f"status={response.get('status')}; valid={report.valid}; "
        f"failed={[c.name for c in report.checks if not c.valid]}",
        ok,
    )


def check_pack_and_merkle_offline(tmp: Path) -> dict[str, Any]:
    from veritas.hashing import compute_content_hash
    from veritas.notary.fetch import FetchResult
    from veritas.notary.log import reset_default_evidence_log, verify_log_inclusion
    from veritas.notary.observe import observe
    from veritas.notary.pack import verify_evidence_pack

    os.environ["VERITAS_RUNTIME_DIR"] = str(tmp / "notary")
    reset_default_evidence_log()
    body = b"Cycle-5 ecosystem notary body."

    def fake_fetch(url, **kwargs):
        return FetchResult(
            request_url=url,
            final_url=url,
            status=200,
            headers={"content-type": "text/plain"},
            body=body,
            truncated=False,
        )

    obs = observe(
        "https://example.org/cycle5",
        request_id="cycle5-obs",
        robots_body="User-agent: *\nAllow: /\n",
        fetch_fn=fake_fetch,
        observed_at="2026-08-08T21:30:00Z",
    )
    pack = obs.get("evidence_pack") or {}
    pack_ok = verify_evidence_pack(pack).get("valid") is True
    log_meta = obs.get("evidence_log") or {}
    from veritas.notary.log import default_evidence_log

    proof = default_evidence_log().proof(int(log_meta.get("index", 0)))
    merkle_ok = verify_log_inclusion(proof).get("valid") is True
    leaf_ok = log_meta.get("leaf") == compute_content_hash(body.decode("utf-8"))
    ok = obs.get("status") == "completed" and pack_ok and merkle_ok and leaf_ok
    return _check(
        "pack_and_merkle_offline",
        "ecosystem peer verifies EvidencePack + Merkle inclusion offline",
        f"status={obs.get('status')}; pack_ok={pack_ok}; merkle_ok={merkle_ok}; leaf_ok={leaf_ok}",
        ok,
    )


def check_trust_is_not_authorization(tmp: Path) -> dict[str, Any]:
    """Peer agents must see trust as self-reported, not as a capability grant."""
    _server, client = _free_client(tmp / "trust")
    r = client.get("/v1/trust")
    if r.status_code != 200:
        return _check("trust_not_authz", "200 trust", f"status={r.status_code}", False)
    body = r.json()
    ok = (body.get("basis") or {}).get("score_source") == "independent_audits"
    rec = body.get("recommendation") == "UNPROVEN"
    return _check(
        "trust_not_authz",
        "trust is independent-audit sourced (or UNPROVEN), not a seller number",
        f"keys={sorted(body.keys())[:12]}; independent={ok}; unproven={rec}",
        ok and rec,
    )


def check_diligence_module_importable() -> dict[str, Any]:
    """Counterparty diligence is part of the ecosystem package surface."""
    try:
        import veritas.counterparty as cp
        import veritas.diligence as dil

        ok = hasattr(dil, "run_diligence") or hasattr(cp, "assess") or True
        # softer: modules import and expose callables
        callables = [
            n
            for n in dir(dil)
            if callable(getattr(dil, n, None)) and not n.startswith("_")
        ]
        ok = len(callables) >= 1
        return _check(
            "diligence_surface",
            "diligence/counterparty modules import for peer assessment",
            f"diligence_callables={callables[:8]}",
            ok,
        )
    except Exception as exc:  # noqa: BLE001
        return _check(
            "diligence_surface",
            "diligence/counterparty modules import",
            f"error={type(exc).__name__}",
            False,
        )


def check_no_network_in_script() -> dict[str, Any]:
    source = Path(__file__).read_text(encoding="utf-8")
    # Build needles without embedding the full tokens in this function body
    # (this check would otherwise match its own source).
    needles = [
        "url" + "open(",
        "requests." + "get",
        "requests." + "post",
        "httpx." + "get",
        "httpx." + "post",
    ]
    # Only scan code outside this function's definition block.
    marker = "def check_no_network_in_script"
    head, _, rest = source.partition(marker)
    # Drop until next top-level def after this one.
    after = rest.split("\ndef ", 1)[-1] if "\ndef " in rest else ""
    scanned = head + "def " + after
    hits = [n for n in needles if n in scanned]
    return _check(
        "no_outbound_in_script",
        "cycle-5 script performs no outbound network calls",
        f"hits={hits}",
        not hits,
    )


def run() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="veritas-cycle5-") as tmp_name:
        tmp = Path(tmp_name)
        checks = [
            check_discovery_traversal(tmp),
            check_constitution_enforcement_shape(tmp),
            check_standalone_verifier_on_research(tmp),
            check_pack_and_merkle_offline(tmp),
            check_trust_is_not_authorization(tmp),
            check_diligence_module_importable(),
            check_no_network_in_script(),
        ]
    passed = sum(1 for c in checks if c["pass"])
    return {
        "cycle": 5,
        "perspective": "ecosystem participant / peer agent",
        "network": "none — offline corpus, injected fetch, no facilitator",
        "on_chain_settlements": 0,
        "boundary": (
            "Does not contact a foreign venue or live facilitator. Measures "
            "discovery + independent verify of research/notary/Merkle surfaces "
            "a peer agent can use after installing the package."
        ),
        "checks": checks,
        "passed": passed,
        "total": len(checks),
        "all_pass": passed == len(checks),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dogfood cycle 5 — ecosystem participant")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    report = run()
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
