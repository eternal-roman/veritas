"""Guided buyer journey: discover → diligence → pay-surface probe → verify path.

Closes the cold-agent gap from the E2E A2A eval worklist (PS9-journey): pieces
existed (diligence, payer, verifier, receipts) but no single command a foreign
agent runs against a base URL.

This module **does not settle payment**. The default path is dry:

1. Fetch discovery + linked surfaces (via :mod:`veritas.counterparty`).
2. Diligence verdict (pass / fail / unverifiable) — fail-closed for pay.
3. Probe ``POST /v1/research`` **without** ``X-PAYMENT`` and report whether
   the seller returned a 402 accepts array (live) or a free-mode body.
4. If a ``content_hash`` is available (free response or ``--content-hash``),
   run local hash verify; optional receipt fetch when ``--request-id`` given.

Paid settle remains on :mod:`veritas.payer` / dogfood / money_loop — never
invented green here.

    veritas-buy https://seller.example --query "…"
    python -m veritas.buyer_journey https://127.0.0.1:8000 --allow-private
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any
from urllib.parse import urljoin

from veritas import __version__
from veritas.counterparty import (
    DEFAULT_TIMEOUT_SECONDS,
    Fetcher,
    evaluate_seller,
    fetch_seller,
)
from veritas.diligence import DiligencePolicy, Verdict
from veritas.hashing import verify_content_hash
from veritas.safeurl import UnsafeUrlError, assert_public_destination

SCHEMA = "veritas.buyer_journey.v0"
USER_AGENT = f"veritas-buy/{__version__}"
RESEARCH_PATH = "/v1/research"
RECEIPTS_PATH = "/v1/receipts/"

# Process contract (aligned with diligence: UNVERIFIABLE ≠ FAIL).
EXIT_OK = 0
EXIT_DILIGENCE_FAIL = 1
EXIT_UNVERIFIABLE = 2
EXIT_BAD_INPUT = 3
EXIT_PROBE_ERROR = 4

Exchange = Callable[..., dict[str, Any]]


def _default_exchange(
    url: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """HTTP exchange returning status + body bytes (for 402 probe honesty)."""
    hdrs = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        **(headers or {}),
    }
    request = urllib.request.Request(  # noqa: S310 - scheme checked by caller
        url, data=body, method=method, headers=hdrs
    )
    try:
        with urllib.request.urlopen(  # nosec B310
            request, timeout=timeout
        ) as response:
            raw = response.read(1_048_576 + 1)
            return {
                "status": int(response.status),
                "body": raw,
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read(1_048_576 + 1) if exc.fp is not None else b""
        return {"status": int(exc.code), "body": raw, "error": None}
    except (OSError, urllib.error.URLError, ValueError) as exc:
        return {
            "status": None,
            "body": b"",
            "error": f"{type(exc).__name__}: {exc}",
        }


def _parse_json_body(raw: bytes) -> Any | None:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None


def probe_research_pay_surface(
    base_url: str,
    query: str,
    *,
    exchange: Exchange | None = None,
    resolver=None,
    allow_private: bool = False,
) -> dict[str, Any]:
    """POST research without payment; report 402 accepts or free body.

    Does **not** attach X-PAYMENT and does **not** settle.
    """
    exchange = exchange or _default_exchange
    url = urljoin(base_url.rstrip("/") + "/", RESEARCH_PATH.lstrip("/"))
    if not allow_private:
        assert_public_destination(url, resolver=resolver)

    payload = json.dumps({"query": query}).encode("utf-8")
    result = exchange(
        url,
        method="POST",
        body=payload,
        headers={"Content-Type": "application/json"},
    )
    if result.get("error"):
        return {
            "step": "pay_surface_probe",
            "ok": False,
            "status": result.get("status"),
            "error": result["error"],
            "payment_required": None,
            "accepts_count": None,
            "free_response": None,
            "not_settled": True,
        }

    status = result.get("status")
    body = _parse_json_body(result.get("body") or b"")
    if status == 402:
        accepts = []
        if isinstance(body, dict):
            raw_accepts = body.get("accepts")
            if isinstance(raw_accepts, list):
                accepts = raw_accepts
        return {
            "step": "pay_surface_probe",
            "ok": True,
            "status": 402,
            "payment_required": True,
            "accepts_count": len(accepts),
            "accepts_preview": accepts[:2] if accepts else [],
            "free_response": None,
            "not_settled": True,
            "note": "Seller issued x402 challenge; settle via payer/dogfood, not this CLI.",
        }

    if status == 200 and isinstance(body, dict):
        return {
            "step": "pay_surface_probe",
            "ok": True,
            "status": 200,
            "payment_required": False,
            "accepts_count": 0,
            "free_response": {
                "status": body.get("status"),
                "request_id": body.get("request_id"),
                "content_hash": body.get("content_hash"),
                "billable": body.get("billable"),
            },
            "not_settled": True,
            "note": "Free-mode (or unpaid) research body returned; not a paid settlement.",
        }

    return {
        "step": "pay_surface_probe",
        "ok": False,
        "status": status,
        "payment_required": None,
        "accepts_count": None,
        "body_keys": list(body.keys()) if isinstance(body, dict) else None,
        "free_response": None,
        "not_settled": True,
        "error": f"unexpected research status {status}",
    }


def _dogfood_resolver(host: str, port: int | None = None):
    """SSRF seam for --allow-private: claim a public A so assert passes.

    urllib still dials the URL host (e.g. 127.0.0.1). Only for local dogfood.
    """
    # AF_INET, SOCK_STREAM shape matching socket.getaddrinfo
    return [(2, 1, 6, "", ("8.8.8.8", 0))]


def run_buyer_journey(
    base_url: str,
    *,
    query: str = "buyer journey probe",
    challenge: object | None = None,
    policy: DiligencePolicy | None = None,
    fetch: Fetcher | None = None,
    exchange: Exchange | None = None,
    resolver=None,
    allow_private: bool = False,
    content_hash: str | None = None,
    content: str | None = None,
    request_id: str | None = None,
    skip_research_probe: bool = False,
) -> dict[str, Any]:
    """Run the guided journey. Never invents settlement success."""
    steps: list[dict[str, Any]] = []
    errors: list[str] = []
    resolve = resolver or (_dogfood_resolver if allow_private else None)

    # --- 1 discover ---
    try:
        documents = fetch_seller(base_url, fetch=fetch, resolver=resolve)
        disc_step = {
            "step": "discover",
            "ok": documents.discovery is not None,
            "fetched": documents.to_dict()["fetched"],
            "errors": list(documents.errors),
        }
        steps.append(disc_step)
        if documents.errors:
            errors.extend(documents.errors)
    except UnsafeUrlError as exc:
        steps.append({
            "step": "discover",
            "ok": False,
            "error": f"unsafe_url: {exc}",
        })
        return _finalize(
            base_url, steps, errors + [str(exc)],
            diligence_verdict=None, exit_hint=EXIT_BAD_INPUT,
        )

    # --- 2 diligence ---
    try:
        report = evaluate_seller(
            base_url,
            challenge=challenge,
            policy=policy,
            fetch=fetch,
            resolver=resolve,
        )
    except UnsafeUrlError as exc:
        steps.append({
            "step": "diligence",
            "ok": False,
            "error": f"unsafe_url: {exc}",
        })
        return _finalize(
            base_url, steps, errors + [str(exc)],
            diligence_verdict=None, exit_hint=EXIT_BAD_INPUT,
        )

    dil_dict = {
        "step": "diligence",
        "ok": report.verdict != Verdict.FAIL,
        "verdict": report.verdict,
        "checks": [
            {"name": c.name, "verdict": c.verdict, "detail": c.detail}
            for c in report.checks
        ],
    }
    steps.append(dil_dict)

    if report.verdict == Verdict.FAIL:
        return _finalize(
            base_url, steps, errors,
            diligence_verdict=report.verdict, exit_hint=EXIT_DILIGENCE_FAIL,
        )

    # --- 3 pay surface probe ---
    free_hash = None
    free_request_id = None
    if not skip_research_probe:
        try:
            probe = probe_research_pay_surface(
                base_url,
                query,
                exchange=exchange,
                resolver=resolve,
                allow_private=allow_private,
            )
            steps.append(probe)
            if not probe.get("ok"):
                errors.append(probe.get("error") or "pay surface probe failed")
            fr = probe.get("free_response") or {}
            free_hash = fr.get("content_hash") if isinstance(fr, dict) else None
            free_request_id = fr.get("request_id") if isinstance(fr, dict) else None
        except UnsafeUrlError as exc:
            steps.append({
                "step": "pay_surface_probe",
                "ok": False,
                "error": f"unsafe_url: {exc}",
                "not_settled": True,
            })
            errors.append(str(exc))

    # --- 4 verify (optional / free-path) ---
    hash_to_check = content_hash or free_hash
    if hash_to_check and content is not None:
        try:
            valid = verify_content_hash(content, hash_to_check)
            steps.append({
                "step": "verify_content_hash",
                "ok": bool(valid),
                "content_hash": hash_to_check,
                "matched": bool(valid),
            })
        except (TypeError, ValueError) as exc:
            steps.append({
                "step": "verify_content_hash",
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            })
    elif hash_to_check:
        steps.append({
            "step": "verify_content_hash",
            "ok": True,
            "skipped": True,
            "content_hash": hash_to_check,
            "note": "Hash observed; pass --content to recompute locally.",
        })
    else:
        steps.append({
            "step": "verify_content_hash",
            "ok": True,
            "skipped": True,
            "note": "No content_hash yet (typical after 402-only probe).",
        })

    # --- 5 receipt (optional) ---
    rid = request_id or free_request_id
    if rid:
        receipt_url = urljoin(
            base_url.rstrip("/") + "/", f"{RECEIPTS_PATH.lstrip('/')}{rid}"
        )
        try:
            if not allow_private:
                assert_public_destination(receipt_url, resolver=resolve)
            ex = (exchange or _default_exchange)(receipt_url, method="GET")
            body = _parse_json_body(ex.get("body") or b"")
            steps.append({
                "step": "receipt",
                "ok": ex.get("status") == 200 and isinstance(body, dict),
                "status": ex.get("status"),
                "request_id": rid,
                "error": ex.get("error"),
                "keys": list(body.keys()) if isinstance(body, dict) else None,
            })
        except UnsafeUrlError as exc:
            steps.append({
                "step": "receipt",
                "ok": False,
                "error": f"unsafe_url: {exc}",
            })
    else:
        steps.append({
            "step": "receipt",
            "ok": True,
            "skipped": True,
            "note": "No request_id; pass --request-id after a delivered research call.",
        })

    exit_hint = EXIT_OK
    if report.verdict == Verdict.UNVERIFIABLE:
        exit_hint = EXIT_UNVERIFIABLE
    probe_steps = [s for s in steps if s.get("step") == "pay_surface_probe"]
    if probe_steps and not probe_steps[0].get("ok") and exit_hint == EXIT_OK:
        exit_hint = EXIT_PROBE_ERROR

    return _finalize(
        base_url, steps, errors,
        diligence_verdict=report.verdict, exit_hint=exit_hint,
    )


def _finalize(
    base_url: str,
    steps: list[dict[str, Any]],
    errors: list[str],
    *,
    diligence_verdict: str | None,
    exit_hint: int,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "package_version": __version__,
        "base_url": base_url,
        "diligence_verdict": diligence_verdict,
        "steps": steps,
        "errors": errors,
        "exit_hint": exit_hint,
        "not_proven": [
            "paid settlement",
            "unsolicited demand",
            "seller will deliver",
            "mainnet",
        ],
        "not_settled": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="veritas-buy",
        description=(
            "Guided buyer journey against a seller base URL: discover, "
            "diligence, pay-surface probe (no settle), optional verify/receipt."
        ),
    )
    parser.add_argument("url", help="Seller base URL, e.g. https://seller.example")
    parser.add_argument(
        "--query",
        default="buyer journey probe",
        help="Research query for the unpaid pay-surface probe",
    )
    parser.add_argument(
        "--challenge",
        metavar="PATH",
        help="Optional 402 challenge JSON file for stronger diligence",
    )
    parser.add_argument(
        "--content-hash",
        dest="content_hash",
        help="Known content_hash to verify (with --content)",
    )
    parser.add_argument(
        "--content",
        help="Content body to recompute hash against --content-hash",
    )
    parser.add_argument(
        "--request-id",
        dest="request_id",
        help="Fetch /v1/receipts/{id} when known",
    )
    parser.add_argument(
        "--skip-research-probe",
        action="store_true",
        help="Only discover + diligence (no POST /v1/research)",
    )
    parser.add_argument(
        "--allow-private",
        action="store_true",
        help="Allow loopback/private sellers (local dogfood only)",
    )
    parser.add_argument(
        "--allow-missing-constitution",
        action="store_true",
        help="Diligence: do not require a constitution document",
    )
    parser.add_argument(
        "--allow-undeclared-gaps",
        action="store_true",
        help="Diligence: allow empty gap register",
    )
    parser.add_argument(
        "--allow-undisclosed-trust",
        action="store_true",
        help="Diligence: do not require self-reported trust disclosure",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    challenge = None
    if args.challenge:
        try:
            with open(args.challenge, encoding="utf-8") as handle:
                challenge = json.load(handle)
        except (OSError, ValueError) as exc:
            print(json.dumps({
                "error": "challenge_unreadable",
                "detail": f"{type(exc).__name__}: {exc}",
            }, indent=2))
            return EXIT_BAD_INPUT

    policy = DiligencePolicy(
        require_challenge_matches_discovery=challenge is not None,
        require_constitution=not args.allow_missing_constitution,
        require_gap_register=not args.allow_undeclared_gaps,
        require_trust_self_disclosure=not args.allow_undisclosed_trust,
    )

    try:
        report = run_buyer_journey(
            args.url,
            query=args.query,
            challenge=challenge,
            policy=policy,
            allow_private=args.allow_private,
            content_hash=args.content_hash,
            content=args.content,
            request_id=args.request_id,
            skip_research_probe=args.skip_research_probe,
        )
    except UnsafeUrlError as exc:
        print(json.dumps({
            "error": "unsafe_url",
            "detail": str(exc),
        }, indent=2))
        return EXIT_BAD_INPUT

    print(json.dumps(report, indent=2, sort_keys=True))
    return int(report.get("exit_hint", EXIT_OK))


if __name__ == "__main__":
    raise SystemExit(main())
