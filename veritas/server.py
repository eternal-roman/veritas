"""FastAPI surface: discovery, x402-gated research, and verification.

Run it with the installed console script or uvicorn directly:

    veritas-server
    python -m uvicorn veritas.server:app
"""

from __future__ import annotations

import base64
import hmac
import json
import os
import threading
import time
import uuid
from collections import deque
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from veritas import __version__
from veritas.constitution import build_constitution
from veritas.credits import CreditLedger, InsufficientCredits, RefundNotAllowed
from veritas.custody import CustodyStore, ReceiptPresence
from veritas.deadline import (
    MIN_USABLE_SECONDS,
    SETTLEMENT_MARGIN_SECONDS,
    Deadline,
    DeadlineTooShort,
)
from veritas.discovery import LLMS_TXT
from veritas.errors import ERROR_REGISTRY, ErrorCode, error_envelope
from veritas.facilitator import VERIFICATION_OUTAGE_PREFIXES, get_facilitator
from veritas.hashing import verify_content_hash
from veritas.identity import build_identity
from veritas.ledger import REDELIVERABLE_STATES, Ledger, NonceState
from veritas.metering import Usage
from veritas.notary.observe import observe
from veritas.observability import Metrics, configure_logging, log_request
from veritas.payment_config import get_payment_config
from veritas.pipeline import run_research
from veritas.pricing import PRICE_TABLE_VERSION, current_price_point
from veritas.siwx import SiwxError, SiwxSessionError, SiwxSessionStore, SiwxVerifyError
from veritas.trust import OutcomeLog, score_service
from veritas.x402 import (
    PriceError,
    build_402_challenge,
    build_payment_requirements,
    decode_payment_header,
    extract_nonce,
    payment_authorization,
    to_atomic_amount,
)

app = FastAPI(title="Veritas Research", version=__version__)

RESOURCE_PATH = "/v1/research"
NOTARIZE_PATH = "/v1/notarize"
ATTESTATION_VERIFY_PATH = "/v1/attestations/verify"

# Ceiling on retrieval work for one paid request, independent of how long the
# buyer's authorization happens to run.
MAX_WORK_SECONDS = 25


def _authorization_valid_before(payload: dict[str, Any]) -> float:
    """The buyer's authorization expiry, or a conservative default.

    A payload we cannot read a `validBefore` from is budgeted as if the window
    were the protocol's advertised maximum, so a malformed value can shorten
    the budget but never extend it.
    """
    authorization = payment_authorization(payload) or {}
    raw = authorization.get("validBefore") or authorization.get("valid_before")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return time.time() + DEFAULT_AUTHORIZATION_SECONDS


DEFAULT_AUTHORIZATION_SECONDS = 60


def resource_url() -> str:
    """The absolute URL of the paid research resource, as x402 expects in `resource`.

    Falls back to the bare path only when no public URL is configured, which
    live mode refuses (see veritas/payment_config.py) — so a published
    challenge always names something a counterparty can dial.
    """
    base = (os.getenv("VERITAS_PUBLIC_URL") or "").strip().rstrip("/")
    return f"{base}{RESOURCE_PATH}" if base else RESOURCE_PATH


def notarize_resource_url() -> str:
    """Absolute URL of the paid notarize resource (same public-base rules)."""
    base = (os.getenv("VERITAS_PUBLIC_URL") or "").strip().rstrip("/")
    return f"{base}{NOTARIZE_PATH}" if base else NOTARIZE_PATH


store = CustodyStore()
outcomes = OutcomeLog()
ledger = Ledger()
credit_ledger = CreditLedger()
siwx_store = SiwxSessionStore()

#: Header carrying a SIWx-issued session token for prepaid credit spend (M7).
SESSION_HEADER = "X-VERITAS-SESSION"
CREDITS_TOPUP_PATH = "/v1/credits/topup"

# 402 bodies are x402-spec-shaped, not registry envelopes; the header marks
# the protocol so a client can recognise the challenge without parsing.
PAYMENT_REQUIRED_HEADER = {"Payment-Required": "x402"}

# --- Limits -----------------------------------------------------------------
#
# Every handler used to be `def`, which in FastAPI means the shared 40-slot
# threadpool. Forty slow retrievals therefore stopped `/health` answering, so a
# load balancer would pull a node that was merely busy. The cheap endpoints are
# now `async def` (served on the event loop and never blocked by retrieval) and
# the one expensive endpoint runs in the threadpool behind an explicit cap.

MAX_CONCURRENT_RESEARCH = max(1, int(os.getenv("VERITAS_MAX_CONCURRENT_RESEARCH", "8")))

#: Shedding, not queueing. An unbounded queue turns a slow dependency into a
#: total outage: every buyer waits behind work that will miss its authorization
#: window anyway. Refusing immediately costs the shed caller one retry and
#: costs them nothing — no work runs and no authorization is claimed.
research_slots = threading.BoundedSemaphore(MAX_CONCURRENT_RESEARCH)
OVERLOAD_RETRY_AFTER = "2"

#: `/v1/verify` re-hashes whatever it is sent, so an unbounded body was an
#: unbounded amount of work for an unpaid, unauthenticated caller.
MAX_BODY_BYTES = int(os.getenv("VERITAS_MAX_BODY_BYTES", str(256 * 1024)))
MAX_VERIFY_CONTENT_CHARS = 200_000

#: Per-caller request budget. Local, in-process, single-instance — behind a
#: balancer each node has its own, which is a real limit and not a closed
#: problem (roadmap 6.2). Set to 0 to disable.
RATE_LIMIT_PER_MINUTE = int(os.getenv("VERITAS_RATE_LIMIT_PER_MINUTE", "300"))
RATE_LIMIT_WINDOW_SECONDS = 60

#: Never rate limited. A limiter that can starve the liveness probe turns a
#: busy node into a node the balancer believes is dead.
UNMETERED_PATHS = frozenset({"/health", "/readyz"})

_rate_lock = threading.Lock()
_rate_buckets: dict[str, deque[float]] = {}

# --- Observability ----------------------------------------------------------
#
# Counters are revenue-adjacent (`veritas_settlements_total`), so /metrics does
# not exist until an operator sets a token. Access logs carry method, path,
# status and duration — never the query, never the X-PAYMENT header.
metrics = Metrics()
METRICS_TOKEN = (os.getenv("VERITAS_METRICS_TOKEN") or "").strip()
METRICS_ENABLED = bool(METRICS_TOKEN)


def _presented_metrics_token(request: Request) -> str:
    return (request.headers.get("Authorization") or "").removeprefix("Bearer ").strip()


def _is_operator_scrape(request: Request) -> bool:
    """An authenticated metrics scrape is not charged against the caller budget.

    A scraper polling every few seconds shares a source address with nothing
    else, but it would otherwise consume a slice of the same per-caller budget
    real traffic uses, and lose visibility exactly when traffic is heaviest.
    The exemption requires the token: an unauthenticated `/metrics` hammer is
    still rate limited, so the 401 path is not a free endpoint.
    """
    return (
        METRICS_ENABLED
        and request.url.path == "/metrics"
        and hmac.compare_digest(_presented_metrics_token(request), METRICS_TOKEN)
    )


def _rate_limited(caller: str) -> bool:
    if RATE_LIMIT_PER_MINUTE <= 0:
        return False
    now = time.monotonic()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    with _rate_lock:
        bucket = _rate_buckets.setdefault(caller, deque())
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT_PER_MINUTE:
            return True
        bucket.append(now)
        # Bound the map itself: an attacker cycling source addresses must not
        # be able to grow it without limit.
        if len(_rate_buckets) > 10_000:
            for key in [k for k, v in _rate_buckets.items() if not v or v[-1] < cutoff]:
                _rate_buckets.pop(key, None)
    return False


@app.middleware("http")
async def enforce_limits(request: Request, call_next):
    """Bound body size and caller rate, then record the request.

    The log line and the counters are deliberately built from the request
    *envelope* only — method, path, status, duration. The body never reaches
    them: a buyer's query is their business, it is already erasable from the
    custody receipt, and a log file is the one place that erasure would not
    reach.
    """
    started = time.monotonic()
    path = request.url.path
    if path not in UNMETERED_PATHS:
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
            metrics.increment("veritas_request_too_large_total")
            return _observed(JSONResponse(status_code=413, content=error_envelope(
                ErrorCode.REQUEST_TOO_LARGE,
                f"body exceeds {MAX_BODY_BYTES} bytes",
            )), request, started)
        caller = request.client.host if request.client else "unknown"
        if not _is_operator_scrape(request) and _rate_limited(caller):
            metrics.increment("veritas_rate_limited_total")
            return _observed(JSONResponse(
                status_code=429,
                content=error_envelope(
                    ErrorCode.RATE_LIMITED,
                    f"more than {RATE_LIMIT_PER_MINUTE} requests in "
                    f"{RATE_LIMIT_WINDOW_SECONDS}s from this caller",
                ),
                headers={"Retry-After": str(RATE_LIMIT_WINDOW_SECONDS)},
            ), request, started)
    return _observed(await call_next(request), request, started)


def _observed(response, request: Request, started: float):
    """Count and log one request from its envelope. Never touches the body."""
    duration_ms = int((time.monotonic() - started) * 1000)
    path = request.url.path
    metrics.increment("veritas_requests_total", {
        "path": path, "status": str(response.status_code),
    })
    if path == RESOURCE_PATH:
        metrics.increment("veritas_research_duration_ms_sum", by=duration_ms)
        metrics.increment("veritas_research_duration_ms_count")
    log_request(
        method=request.method,
        path=path,
        status=response.status_code,
        duration_ms=duration_ms,
    )
    return response


@app.exception_handler(RequestValidationError)
async def invalid_request_handler(request: Request, exc: RequestValidationError):
    """422s previously leaked FastAPI's raw shape, unlike every other error."""
    return JSONResponse(
        status_code=422,
        content=error_envelope(ErrorCode.INVALID_REQUEST, jsonable_encoder(exc.errors())),
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    """The last response on the surface that was not a registered envelope.

    An unhandled exception used to escape as Starlette's plain-text 500, so an
    agent branching on `body["error"]` crashed on exactly the case it most
    needed to handle. The cause is deliberately not described: the exception
    text names server internals and this body goes to external callers.
    """
    return JSONResponse(
        status_code=500,
        content=error_envelope(
            ErrorCode.INTERNAL_ERROR,
            "the service failed to handle this request; nothing was billed",
        ),
    )


class ResearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    max_results: int = Field(default=5, ge=1, le=10)


class NotarizeRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    retention_class: str = Field(default="standard", min_length=1, max_length=64)
    declared_license: str | dict[str, Any] | None = None
    robots_override: str | None = Field(default=None, max_length=200)


class VerifyRequest(BaseModel):
    """Verification request. Prefer origin re-fetch (P7 product) over arithmetic.

    Independent modes (caller does not supply both sides of the comparison):

    * ``url`` + ``content_hash`` — re-fetch the origin via notary.observe
    * ``request_id`` — load the custody receipt, re-fetch its stored URL,
      compare to the receipt's published evidence hash

    Legacy convenience (non-independent): ``content`` + ``content_hash`` —
    pure arithmetic on caller inputs; labeled ``binding: caller_supplied``.
    """

    content: str | None = Field(default=None, max_length=MAX_VERIFY_CONTENT_CHARS)
    content_hash: str | None = Field(default=None, max_length=256)
    url: str | None = Field(default=None, max_length=2000)
    request_id: str | None = Field(default=None, max_length=128)


class VerifyAttestationRequest(BaseModel):
    """Buyer-supplied EvidenceRecord fields + optional operator attestation.

    Free to call. Reconstructs the N1.1 canonical message and recovers the
    EIP-191 signer. Does **not** re-fetch the origin URL and is **not** an
    on-chain check (use POST /v1/verify with url for re-fetch; G9 separate).
    """

    evidence_record: dict[str, Any] = Field(min_length=1)
    attestation: dict[str, Any] = Field(min_length=1)
    expected_signer: str | None = Field(default=None, max_length=64)


@app.get("/health")
async def health():
    """Liveness: is this process running? Never rate limited, never blocked."""
    cfg = get_payment_config()
    return {
        "status": "ok",
        "service": "veritas",
        "version": app.version,
        "payment_mode": cfg.mode,
        "live_ready": cfg.is_live_ready(),
    }


@app.get("/readyz")
async def readyz():
    """Readiness: can this process serve? Distinct from liveness on purpose.

    One endpoint conflating the two leaves an operator with a bad choice: a
    misconfigured node that reports healthy and silently serves nothing, or a
    busy node that gets restarted for being busy. A misconfigured service is
    alive (do not restart it) and not ready (do not route to it).
    """
    cfg = get_payment_config()
    reasons = list(cfg.config_errors) if cfg.mode == "misconfigured" else []
    ready = not reasons
    body = {"ready": ready, "payment_mode": cfg.mode, "reasons": reasons}
    return body if ready else JSONResponse(status_code=503, content=body)


@app.get("/v1/payment-config")
async def payment_config():
    cfg = get_payment_config()
    # The human price alone cannot be checked against a settlement; the atomic
    # amount and the pricing version can, and the version is what a revenue
    # report spanning a reprice needs.
    return {**cfg.as_dict(), "pricing": current_price_point(cfg.price, cfg.network)}


def _carries_a_nonce_field(payload: dict[str, Any]) -> bool:
    """Did the caller attempt a nonce at all?

    Separates "you sent no authorization" from "the one you sent is not a
    32-byte hex value" — two different mistakes, and a buyer debugging their
    client needs to know which one they made.
    """
    authorization = payment_authorization(payload) or {}
    inner = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    return any(
        "nonce" in candidate
        for candidate in (authorization, inner, payload)
        if isinstance(candidate, dict)
    )


def _challenge(
    cfg,
    error: str | None = None,
    *,
    resource: str | None = None,
) -> JSONResponse:
    kwargs = {"error": error} if error else {}
    return JSONResponse(
        status_code=402,
        content=build_402_challenge(
            cfg.pay_to,
            cfg.network,
            cfg.price,
            resource if resource is not None else resource_url(),
            **kwargs,
        ),
        headers=PAYMENT_REQUIRED_HEADER,
    )


def _payment_response_header(payment: dict[str, Any]) -> dict[str, str]:
    return {"X-PAYMENT-RESPONSE": base64.b64encode(
        json.dumps(payment).encode()
    ).decode()}


def _meter(result: dict[str, Any], request_id: str, started: float, *, paid: bool) -> None:
    """Record what this request consumed, paid or not.

    A retrieval pass costs the same whether or not anyone paid for it, so cost
    is metered on every request while the financial tables stay paid-only.
    Provider *attempts* are counted rather than successes: a search API bills
    the request, not the result. Metering never raises — a bookkeeping failure
    must not fail a request the buyer paid for.
    """
    retrieval = result.get("retrieval") or {}
    calls: dict[str, int] = {}
    for provider in retrieval.get("providers_attempted") or []:
        calls[provider] = calls.get(provider, 0) + 1
    ledger.record_usage(Usage(
        request_id=request_id,
        status=result.get("status", "unknown"),
        billable=bool(result.get("billable")),
        paid=paid,
        provider_calls=calls,
        evidence_bytes=sum(len(e.get("excerpt") or "") for e in result.get("evidence", [])),
        duration_ms=int((time.monotonic() - started) * 1000),
    ))


def _settle_and_respond(
    result: dict[str, Any], request_id: str, facilitator, payment_payload,
    requirements_dict, *, replayed: bool = False,
):
    """Attempt settlement for delivered work and answer accordingly.

    Three outcomes, and the middle one is why this is not a boolean:

    * settled — 200 with the deliverable.
    * indeterminate — the facilitator never answered, so the funds may have
      moved. The buyer gets the work and is told the settlement is unresolved;
      withholding it is the one outcome that is certainly wrong, because we may
      already hold their money.
    * failed — the facilitator answered no. 402, no delivery, nothing owed.
    """
    settlement = facilitator.settle(payment_payload, requirements_dict)
    outcome = settlement.outcome
    metrics.increment("veritas_settlements_total", {"outcome": outcome})
    ledger.record_settlement(
        request_id,
        outcome=outcome,
        transaction=settlement.transaction,
        network=settlement.network,
        payer=settlement.payer,
        reason=settlement.error_reason,
    )
    payment = {"settled": settlement.success, **settlement.to_dict()}
    if replayed:
        payment["replayed"] = True

    if outcome == "failed":
        return JSONResponse(status_code=402, content=error_envelope(
            ErrorCode.SETTLEMENT_FAILED,
            settlement.error_reason,
            request_id=request_id,
        ))

    result = dict(result, payment=payment)
    return JSONResponse(
        status_code=200, content=result,
        headers=_payment_response_header(settlement.to_dict()),
    )


def _resubmitted_authorization(claim, cfg, facilitator, payment_payload,
                               requirements_dict, query):
    """Answer a payment authorization this instance has already admitted.

    Burning the nonce and returning 409 — the previous behaviour — charged a
    buyer whose connection dropped after settlement and left them with an
    authorization that is single-use on chain, so they could not even re-sign
    it. What they get now depends on what state their request reached.
    """
    reason = claim.reason or "payment_nonce_rejected"
    if reason == "replay_store_unavailable":
        # Fail closed: an unusable guard must not become no guard.
        return JSONResponse(status_code=503, content=error_envelope(
            ErrorCode.REPLAY_PROTECTION_UNAVAILABLE, reason,
        ))
    existing = claim.existing
    if existing is None:
        return JSONResponse(status_code=409, content=error_envelope(
            reason,
            "This payment authorization cannot be admitted. Request a "
            "fresh 402 challenge and sign a new authorization.",
        ))

    if existing.state == NonceState.CLAIMED:
        # The first request is still in flight (or died mid-work). Doing the
        # work again is exactly what the claim exists to prevent.
        return JSONResponse(status_code=409, content=error_envelope(
            ErrorCode.PAYMENT_AUTHORIZATION_IN_PROGRESS,
            "A request against this authorization is already in progress.",
            request_id=existing.request_id,
        ))

    if existing.state == NonceState.ABANDONED:
        return JSONResponse(status_code=409, content=error_envelope(
            ErrorCode.PAYMENT_NONCE_ALREADY_SPENT,
            "The earlier request against this authorization failed on our "
            "side and was not billed. Request a fresh 402 challenge and sign "
            "a new authorization.",
            request_id=existing.request_id,
        ))

    # An authorization buys one request. Returning its deliverable in answer
    # to a *different* question would hand the buyer a 200 whose only sign of
    # mismatch is the echoed `query` — found in dogfood cycle 2.
    if not ledger.delivered_query_matches(existing.request_id, query):
        return JSONResponse(status_code=409, content=error_envelope(
            ErrorCode.PAYMENT_AUTHORIZATION_BOUND_TO_ANOTHER_REQUEST,
            "This authorization already bought a different request. Request a "
            "fresh 402 challenge for this one.",
            request_id=existing.request_id,
        ))

    stored = ledger.deliverable(existing.request_id)
    if stored is None:
        return JSONResponse(status_code=409, content=error_envelope(
            ErrorCode.PAYMENT_NONCE_ALREADY_SPENT,
            "This authorization was admitted but its deliverable is no longer "
            "retrievable. Request a fresh 402 challenge.",
            request_id=existing.request_id,
        ))

    if existing.state in REDELIVERABLE_STATES:
        # Already settled, or settled-unknown. Re-settling would present an
        # authorization the chain has burned; deliver what was bought instead.
        attempts = ledger.settlements(existing.request_id)
        last = attempts[-1] if attempts else {}
        payment = {
            "settled": existing.state == NonceState.SETTLED,
            "state": existing.state,
            "transaction": last.get("transaction"),
            "network": last.get("network"),
            "payer": last.get("payer"),
            "error_reason": last.get("reason"),
            "replayed": True,
        }
        return JSONResponse(
            status_code=200, content=dict(stored, payment=payment),
            headers=_payment_response_header(payment),
        )

    # delivered (settlement never recorded) or settlement_failed: the work is
    # done and unpaid, so retry settlement rather than redo the retrieval.
    return _settle_and_respond(
        stored, existing.request_id, facilitator, payment_payload,
        requirements_dict, replayed=True,
    )


@app.post(RESOURCE_PATH)
async def research(req: ResearchRequest, request: Request):
    """Bound the one expensive endpoint, then run it off the event loop.

    The cap is taken *before* the thread hop, so a shed request costs nothing:
    no retrieval pass, no facilitator call, no claimed payment authorization.
    The payment header is read here rather than passed through, so no Request
    object crosses into the worker thread.
    """
    if not research_slots.acquire(blocking=False):
        metrics.increment("veritas_research_shed_total")
        return JSONResponse(
            status_code=503,
            content=error_envelope(
                ErrorCode.SERVICE_OVERLOADED,
                f"all {MAX_CONCURRENT_RESEARCH} research slots are in use; "
                "nothing was done and nothing is owed",
            ),
            headers={"Retry-After": OVERLOAD_RETRY_AFTER},
        )
    # A credit debit is taken *before* the work, so unlike the x402 path it does
    # not fail safe on its own. x402 charges last — an exception before
    # settlement means the buyer is simply not charged. Credits invert that: the
    # money has already moved, so an exception anywhere after the debit would
    # leave the buyer paying for our crash, which invariant 3 forbids.
    #
    # `_research` records the debit here as soon as it takes one, and this
    # handler reverses it if the request dies on an unexpected exception. Every
    # *expected* outcome (deadline, unavailable) already refunds inside
    # `_research`; refund is idempotent, so the two cannot double-refund.
    #
    # Today every call after the debit swallows its own failures, so no
    # reachable path is known — this is the structural guarantee rather than a
    # fix for an observed bug. Without it the invariant holds only for as long
    # as every downstream callee stays defensive.
    charge: dict[str, str] = {}
    try:
        return await run_in_threadpool(
            _research,
            req,
            request.headers.get("X-PAYMENT"),
            request.headers.get(SESSION_HEADER),
            charge,
        )
    except Exception:
        _refund_unfinished_charge(charge)
        raise
    finally:
        research_slots.release()


def _refund_unfinished_charge(charge: dict[str, str]) -> None:
    """Reverse a credit debit whose request never produced a response.

    Never raises: this runs while an exception is propagating, and masking the
    original failure with a bookkeeping error would lose the reason the request
    died. A refund that cannot be written is reported by the credit journal's
    own records, which still hold the unreversed debit.
    """
    if not charge:
        return
    try:
        credit_ledger.refund(
            charge["account"],
            request_id=charge["request_id"],
            note="refund_request_failed",
        )
    except Exception:
        metrics.increment("veritas_credit_refund_failed_total")


def _research(
    req: ResearchRequest,
    payment_header: str | None,
    session_header: str | None = None,
    charge: dict[str, str] | None = None,
):
    cfg = get_payment_config()
    payment_payload: dict[str, Any] | None = None
    requirements_dict: dict[str, Any] | None = None
    facilitator = None
    deadline: Deadline | None = None
    credit_account: str | None = None
    paid_with_credits = False
    # Allocated here, not inside the pipeline, so the authorization claim, the
    # custody receipt, the ledger and the response all name the same request
    # (defect R6: `claim` accepted a request_id no caller ever passed).
    request_id = str(uuid.uuid4())

    # Payment was demanded but the configuration is invalid. Refuse to serve
    # rather than silently falling back to giving the paid service away.
    if cfg.mode == "misconfigured":
        return JSONResponse(
            status_code=503,
            content=error_envelope(ErrorCode.PAYMENT_MISCONFIGURED, cfg.config_errors),
        )

    # M7 credit path: live mode + SIWx session + no X-PAYMENT → debit prepaid
    # credits (one payer path still owns signing; this is spend of already-
    # settled top-up, not a second signing seam).
    if cfg.require_payment and not payment_header and session_header:
        try:
            session = siwx_store.resolve(session_header)
        except SiwxSessionError:
            # Category only — exception text never reaches a buyer (4f2321c).
            return JSONResponse(
                status_code=401,
                content=error_envelope(
                    ErrorCode.SESSION_INVALID,
                    "SIWx session missing, unknown, or expired",
                ),
            )
        try:
            atomic = int(to_atomic_amount(cfg.price, cfg.network))
        except (PriceError, TypeError, ValueError):
            return JSONResponse(
                status_code=503,
                content=error_envelope(
                    ErrorCode.PAYMENT_MISCONFIGURED,
                    "price configuration rejected at credit debit",
                ),
            )
        try:
            credit_ledger.debit(
                session.address,
                atomic,
                request_id=request_id,
                note="research_debit",
            )
        except InsufficientCredits:
            # Balance/required are structured fields; do not echo exception text.
            return JSONResponse(
                status_code=402,
                content=error_envelope(
                    ErrorCode.CREDITS_INSUFFICIENT,
                    "prepaid credits insufficient for this research debit",
                    balance=credit_ledger.balance(session.address),
                    required=atomic,
                ),
            )
        credit_account = session.address
        paid_with_credits = True
        # The debit is now committed. Publish it to the caller so that a
        # request dying on an unexpected exception still reverses the charge
        # (see `research`); every expected outcome refunds below instead.
        if charge is not None:
            charge["account"] = session.address
            charge["request_id"] = request_id
        # Same work ceiling as x402-paid research; overruns refund the debit
        # (no payment authorization window — credits are already prepaid).
        deadline = Deadline.after(MAX_WORK_SECONDS)

    if cfg.require_payment and not paid_with_credits:
        try:
            requirements = build_payment_requirements(
                pay_to=cfg.pay_to,
                network=cfg.network,
                price=cfg.price,
                resource=resource_url(),
            )
        except PriceError:
            # Misconfiguration must not silently become free service. The
            # exception text describes server-side configuration, so it stays
            # out of the response body (CodeQL: information exposure); the
            # operator inspects config via /v1/payment-config, not this error.
            return JSONResponse(
                status_code=500,
                content=error_envelope(
                    ErrorCode.PAYMENT_MISCONFIGURED,
                    "price configuration rejected at challenge construction",
                ),
            )
        requirements_dict = requirements.to_dict()

        if not payment_header:
            return _challenge(cfg)

        payment_payload = decode_payment_header(payment_header)
        if payment_payload is None:
            return _challenge(cfg, "X-PAYMENT header is not valid base64-encoded JSON")

        # Structural admissibility first. A payload with no usable
        # authorization nonce can never be admitted, and finding that out
        # costs nothing — so it must not cost a facilitator round trip. Doing
        # this after verification let an unpaid caller spend our outbound
        # request budget one junk header at a time (dogfood cycle 3). It
        # claims nothing and changes no state, so it does not weaken the
        # verify-before-claim ordering below.
        nonce = extract_nonce(payment_payload)
        if nonce is None:
            reason = (
                ErrorCode.PAYMENT_NONCE_MALFORMED
                if _carries_a_nonce_field(payment_payload)
                else ErrorCode.PAYMENT_NONCE_MISSING
            )
            return JSONResponse(status_code=409, content=error_envelope(
                reason,
                "This payment authorization cannot be admitted. Request a "
                "fresh 402 challenge and sign a new authorization.",
            ))

        facilitator = get_facilitator(cfg.facilitator, live=True)
        verification = facilitator.verify(payment_payload, requirements_dict)
        if not verification.is_valid:
            reason = verification.invalid_reason or "payment_invalid"
            # Facilitator outages fail closed as 503 so buyers retry rather
            # than treating the refusal as a permanent payment rejection.
            if reason.startswith(VERIFICATION_OUTAGE_PREFIXES):
                return JSONResponse(status_code=503, content=error_envelope(
                    ErrorCode.PAYMENT_VERIFICATION_UNAVAILABLE, reason,
                ))
            return _challenge(cfg, reason)

        # Budget the work against the authorization that pays for it. Doing
        # this before the claim means an authorization too short to finish
        # costs the buyer nothing: no work, no burned nonce.
        try:
            deadline = Deadline.for_authorization(
                valid_before=_authorization_valid_before(payment_payload),
                max_work_seconds=MAX_WORK_SECONDS,
            )
        except DeadlineTooShort:
            # Built from our own constants, never from the exception. The
            # current DeadlineTooShort message is only timings, but the rule
            # here is that exception text does not reach a buyer (4f2321c) —
            # a message that is safe today is a leak one refactor from now,
            # and this body goes out to an unauthenticated caller.
            return _challenge(cfg, (
                "authorization window too short: it must leave at least "
                f"{MIN_USABLE_SECONDS}s of work time plus a "
                f"{SETTLEMENT_MARGIN_SECONDS}s settlement margin"
            ))

        # Claim the authorization after the facilitator accepts it and BEFORE
        # any retrieval pass, so a resubmitted header cannot make us do the
        # work a second time. The claim is never released — the authorization
        # stays live on chain — but it is no longer a dead end: see
        # `_resubmitted_authorization` for what a replay is answered with.
        claim = ledger.claim(
            nonce, request_id,
            network=requirements_dict.get("network"),
            asset=requirements_dict.get("asset"),
            amount=requirements_dict.get("maxAmountRequired"),
            pay_to=requirements_dict.get("payTo"),
            payer=verification.payer,
            price=cfg.price,
            price_version=PRICE_TABLE_VERSION,
        )
        if not claim.claimed:
            return _resubmitted_authorization(
                claim, cfg, facilitator, payment_payload, requirements_dict,
                req.query,
            )

    started = time.monotonic()
    result = run_research(req.query, max_results=req.max_results, request_id=request_id)
    _meter(result, request_id, started, paid=cfg.require_payment)

    def _refund_credits_if_needed(reason: str) -> None:
        if not paid_with_credits or not credit_account:
            return
        try:
            credit_ledger.refund(
                credit_account, request_id=request_id, note=reason,
            )
        except RefundNotAllowed:
            pass

    # The window may have closed while we worked. Settling now would present an
    # expired authorization; the buyer is not charged and is told to retry with
    # a fresh one, which is the honest outcome for our own slowness.
    if deadline is not None and deadline.expired():
        result["billable"] = False
        result["status"] = "unavailable"
        result["refusal_reason"] = "retrieval_unavailable"
        result["error"] = ErrorCode.DEADLINE_EXCEEDED.value
        result["payment"] = {"settled": False, "reason": "deadline_exceeded_before_settlement"}
        _refund_credits_if_needed("refund_deadline_exceeded")
        if paid_with_credits:
            result["payment"] = {
                "settled": False,
                "mode": "credits",
                "reason": "deadline_exceeded_credits_refunded",
            }
        if not paid_with_credits and cfg.require_payment:
            ledger.record_delivery(
                request_id, status=result["status"], billable=False,
                custody_root=result.get("custody_root"), query=req.query, response=result,
            )
        outcomes.record(result["status"], bool(result["custody_valid"]), False,
                        paid=False)
        return JSONResponse(status_code=503, content=result)

    metrics.increment("veritas_research_total", {"status": result["status"]})
    record = store.save(result)
    result["custody_receipt"] = record
    # Only paid traffic scores. /v1/trust is free and unauthenticated, so
    # counting free requests would let anyone manufacture our reputation
    # (constitution gap G7). Free outcomes are still recorded and reported.
    outcomes.record(
        result["status"],
        bool(result["custody_valid"]),
        bool(result["billable"]),
        paid=cfg.require_payment and (not paid_with_credits or bool(result["billable"])),
    )

    # Record what we produced BEFORE settlement is attempted, and fsync it. A
    # crash between the two then leaves a durable statement that we owe this
    # buyer a deliverable and may or may not have been paid — which is
    # reconcilable — rather than silence, which is not. Non-billable work
    # abandons the authorization, so the ledger refuses to settle it.
    # Credit-paid requests never claim an x402 nonce, so they skip this ledger.
    if cfg.require_payment and not paid_with_credits:
        ledger.record_delivery(
            request_id, status=result["status"], billable=bool(result["billable"]),
            custody_root=result.get("custody_root"), query=req.query, response=result,
        )

    # Retrieval failures are ours, not the buyer's: never settle for them.
    # Credit debits are refunded so the buyer is not charged for our outage.
    if result["status"] == "unavailable":
        _refund_credits_if_needed("refund_retrieval_unavailable")
        result["payment"] = {
            "settled": False,
            "reason": (
                "not_billable_retrieval_unavailable_credits_refunded"
                if paid_with_credits
                else "not_billable_retrieval_unavailable"
            ),
            **({"mode": "credits"} if paid_with_credits else {}),
        }
        # The registry code is additive: the full research body stays because
        # the unavailability report is itself the deliverable here.
        result["error"] = ErrorCode.RETRIEVAL_UNAVAILABLE.value
        return JSONResponse(status_code=503, content=result)

    if paid_with_credits:
        result["payment"] = {
            "settled": True,
            "mode": "credits",
            "reason": "prepaid_credits",
            "account": credit_account,
            "balance": credit_ledger.balance(credit_account) if credit_account else None,
        }
        return result

    if cfg.require_payment and facilitator is not None:
        return _settle_and_respond(
            result, request_id, facilitator, payment_payload, requirements_dict,
        )

    result["payment"] = {"settled": False, "mode": cfg.mode, "reason": "free_mode"}
    return result


@app.post(NOTARIZE_PATH)
async def notarize(req: NotarizeRequest, request: Request):
    """Paid observe-once notary. Same money-path order as research (N0-B).

    Shares the research concurrency semaphore: outbound fetch is the expensive
    work, not a second payer or engine. Credits debit before work, so an
    unexpected exception after the debit is reversed here (same guard as
    research — invariant 3).
    """
    if not research_slots.acquire(blocking=False):
        metrics.increment("veritas_research_shed_total")
        return JSONResponse(
            status_code=503,
            content=error_envelope(
                ErrorCode.SERVICE_OVERLOADED,
                f"all {MAX_CONCURRENT_RESEARCH} research slots are in use; "
                "nothing was done and nothing is owed",
            ),
            headers={"Retry-After": OVERLOAD_RETRY_AFTER},
        )
    # Same charge-publish / crash-refund shape as `research`: credits move
    # before observe, so a raise after debit would bill for our failure.
    charge: dict[str, str] = {}
    try:
        return await run_in_threadpool(
            _notarize,
            req,
            request.headers.get("X-PAYMENT"),
            request.headers.get(SESSION_HEADER),
            charge,
        )
    except Exception:
        _refund_unfinished_charge(charge)
        raise
    finally:
        research_slots.release()


def _notarize(
    req: NotarizeRequest,
    payment_header: str | None,
    session_header: str | None = None,
    charge: dict[str, str] | None = None,
):
    """verify → claim → observe → fsync delivery → settle (or credits debit/refund)."""
    cfg = get_payment_config()
    payment_payload: dict[str, Any] | None = None
    requirements_dict: dict[str, Any] | None = None
    facilitator = None
    deadline: Deadline | None = None
    credit_account: str | None = None
    paid_with_credits = False
    request_id = str(uuid.uuid4())
    resource = notarize_resource_url()

    if cfg.mode == "misconfigured":
        return JSONResponse(
            status_code=503,
            content=error_envelope(ErrorCode.PAYMENT_MISCONFIGURED, cfg.config_errors),
        )

    if cfg.require_payment and not payment_header and session_header:
        try:
            session = siwx_store.resolve(session_header)
        except SiwxSessionError:
            return JSONResponse(
                status_code=401,
                content=error_envelope(
                    ErrorCode.SESSION_INVALID,
                    "SIWx session missing, unknown, or expired",
                ),
            )
        try:
            atomic = int(to_atomic_amount(cfg.price, cfg.network))
        except (PriceError, TypeError, ValueError):
            return JSONResponse(
                status_code=503,
                content=error_envelope(
                    ErrorCode.PAYMENT_MISCONFIGURED,
                    "price configuration rejected at credit debit",
                ),
            )
        try:
            credit_ledger.debit(
                session.address,
                atomic,
                request_id=request_id,
                note="notarize_debit",
            )
        except InsufficientCredits:
            return JSONResponse(
                status_code=402,
                content=error_envelope(
                    ErrorCode.CREDITS_INSUFFICIENT,
                    "prepaid credits insufficient for this notarize debit",
                    balance=credit_ledger.balance(session.address),
                    required=atomic,
                ),
            )
        credit_account = session.address
        paid_with_credits = True
        # Debit is committed — publish so a crash after this still reverses it.
        if charge is not None:
            charge["account"] = session.address
            charge["request_id"] = request_id
        deadline = Deadline.after(MAX_WORK_SECONDS)

    if cfg.require_payment and not paid_with_credits:
        try:
            requirements = build_payment_requirements(
                pay_to=cfg.pay_to,
                network=cfg.network,
                price=cfg.price,
                resource=resource,
            )
        except PriceError:
            return JSONResponse(
                status_code=500,
                content=error_envelope(
                    ErrorCode.PAYMENT_MISCONFIGURED,
                    "price configuration rejected at challenge construction",
                ),
            )
        requirements_dict = requirements.to_dict()

        if not payment_header:
            return _challenge(cfg, resource=resource)

        payment_payload = decode_payment_header(payment_header)
        if payment_payload is None:
            return _challenge(
                cfg,
                "X-PAYMENT header is not valid base64-encoded JSON",
                resource=resource,
            )

        nonce = extract_nonce(payment_payload)
        if nonce is None:
            reason = (
                ErrorCode.PAYMENT_NONCE_MALFORMED
                if _carries_a_nonce_field(payment_payload)
                else ErrorCode.PAYMENT_NONCE_MISSING
            )
            return JSONResponse(status_code=409, content=error_envelope(
                reason,
                "This payment authorization cannot be admitted. Request a "
                "fresh 402 challenge and sign a new authorization.",
            ))

        facilitator = get_facilitator(cfg.facilitator, live=True)
        verification = facilitator.verify(payment_payload, requirements_dict)
        if not verification.is_valid:
            reason = verification.invalid_reason or "payment_invalid"
            if reason.startswith(VERIFICATION_OUTAGE_PREFIXES):
                return JSONResponse(status_code=503, content=error_envelope(
                    ErrorCode.PAYMENT_VERIFICATION_UNAVAILABLE, reason,
                ))
            return _challenge(cfg, reason, resource=resource)

        try:
            deadline = Deadline.for_authorization(
                valid_before=_authorization_valid_before(payment_payload),
                max_work_seconds=MAX_WORK_SECONDS,
            )
        except DeadlineTooShort:
            return _challenge(cfg, (
                "authorization window too short: it must leave at least "
                f"{MIN_USABLE_SECONDS}s of work time plus a "
                f"{SETTLEMENT_MARGIN_SECONDS}s settlement margin"
            ), resource=resource)

        claim = ledger.claim(
            nonce, request_id,
            network=requirements_dict.get("network"),
            asset=requirements_dict.get("asset"),
            amount=requirements_dict.get("maxAmountRequired"),
            pay_to=requirements_dict.get("payTo"),
            payer=verification.payer,
            price=cfg.price,
            price_version=PRICE_TABLE_VERSION,
        )
        if not claim.claimed:
            # Bind resubmits to the notarized URL (stored as `query` on the envelope).
            return _resubmitted_authorization(
                claim, cfg, facilitator, payment_payload, requirements_dict,
                req.url,
            )

    started = time.monotonic()
    result = observe(
        req.url,
        request_id=request_id,
        retention_class=req.retention_class,
        declared_license=req.declared_license,
        robots_override=req.robots_override,
    )
    _meter(result, request_id, started, paid=cfg.require_payment)

    def _refund_credits_if_needed(reason: str) -> None:
        if not paid_with_credits or not credit_account:
            return
        try:
            credit_ledger.refund(
                credit_account, request_id=request_id, note=reason,
            )
        except RefundNotAllowed:
            pass

    if deadline is not None and deadline.expired():
        result["billable"] = False
        result["status"] = "unavailable"
        result["refusal_reason"] = "fetch_unavailable"
        result["error"] = ErrorCode.DEADLINE_EXCEEDED.value
        result["payment"] = {"settled": False, "reason": "deadline_exceeded_before_settlement"}
        _refund_credits_if_needed("refund_deadline_exceeded")
        if paid_with_credits:
            result["payment"] = {
                "settled": False,
                "mode": "credits",
                "reason": "deadline_exceeded_credits_refunded",
            }
        if not paid_with_credits and cfg.require_payment:
            ledger.record_delivery(
                request_id, status=result["status"], billable=False,
                custody_root=result.get("custody_root"), query=req.url, response=result,
            )
        outcomes.record(result["status"], bool(result.get("custody_valid")), False,
                        paid=False)
        return JSONResponse(status_code=503, content=result)

    metrics.increment("veritas_research_total", {"status": result["status"]})
    record = store.save(result)
    result["custody_receipt"] = record
    outcomes.record(
        result["status"],
        bool(result.get("custody_valid")),
        bool(result.get("billable")),
        paid=cfg.require_payment and (not paid_with_credits or bool(result.get("billable"))),
    )

    # fsync delivery before settlement — evidence text (incl. retention class)
    # lives on the response body stored by the ledger.
    if cfg.require_payment and not paid_with_credits:
        ledger.record_delivery(
            request_id, status=result["status"], billable=bool(result.get("billable")),
            custody_root=result.get("custody_root"), query=req.url, response=result,
        )

    if result["status"] == "unavailable":
        _refund_credits_if_needed("refund_fetch_unavailable")
        result["payment"] = {
            "settled": False,
            "reason": (
                "not_billable_fetch_unavailable_credits_refunded"
                if paid_with_credits
                else "not_billable_fetch_unavailable"
            ),
            **({"mode": "credits"} if paid_with_credits else {}),
        }
        result["error"] = ErrorCode.RETRIEVAL_UNAVAILABLE.value
        return JSONResponse(status_code=503, content=result)

    if paid_with_credits:
        result["payment"] = {
            "settled": True,
            "mode": "credits",
            "reason": "prepaid_credits",
            "account": credit_account,
            "balance": credit_ledger.balance(credit_account) if credit_account else None,
        }
        return result

    if cfg.require_payment and facilitator is not None:
        return _settle_and_respond(
            result, request_id, facilitator, payment_payload, requirements_dict,
        )

    result["payment"] = {"settled": False, "mode": cfg.mode, "reason": "free_mode"}
    return result


@app.post("/v1/verify")
async def verify(req: VerifyRequest):
    """Verify a content hash — with origin re-fetch when bound (P7 product).

    Prefer ``url``+``content_hash`` or ``request_id`` so the check is not pure
    arithmetic on caller-supplied pairs. The legacy ``content``+``content_hash``
    path remains for offline re-hash convenience and is labeled
    ``binding: caller_supplied`` (not independent).
    """
    # --- Independent: receipt → re-fetch stored URL ---
    if req.request_id:
        presence = store.lookup(req.request_id)
        if presence is ReceiptPresence.GONE:
            return JSONResponse(
                status_code=410,
                content=error_envelope(
                    ErrorCode.RECEIPT_GONE, request_id=req.request_id
                ),
            )
        if presence is not ReceiptPresence.PRESENT:
            return JSONResponse(
                status_code=404,
                content=error_envelope(
                    ErrorCode.RECEIPT_NOT_FOUND, request_id=req.request_id
                ),
            )
        record = store.load(req.request_id)
        if record is None:
            return JSONResponse(
                status_code=404,
                content=error_envelope(
                    ErrorCode.RECEIPT_NOT_FOUND, request_id=req.request_id
                ),
            )
        url = record.get("query")
        hashes = record.get("evidence_hashes") or []
        published = req.content_hash or (hashes[0] if hashes else None)
        if not isinstance(url, str) or not url or not published:
            return {
                "valid": False,
                "binding": "receipt_refetch",
                "match": False,
                "reason": "receipt_incomplete",
                "request_id": req.request_id,
                "note": (
                    "receipt lacked a URL or published content_hash; "
                    "cannot re-fetch"
                ),
            }
        from veritas.notary.refetch import refetch_verify

        result = await run_in_threadpool(refetch_verify, url, published)
        result["binding"] = "receipt_refetch"
        result["request_id"] = req.request_id
        return result

    # --- Independent: caller names URL + published hash; we re-fetch ---
    if req.url and req.content_hash:
        from veritas.notary.refetch import refetch_verify

        return await run_in_threadpool(refetch_verify, req.url, req.content_hash)

    # --- Legacy convenience: arithmetic on caller-supplied pair ---
    if req.content is not None and req.content_hash:
        ok, detail = verify_content_hash(req.content, req.content_hash)
        return {
            "valid": ok,
            "binding": "caller_supplied",
            "note": (
                "hashes content you supplied against a hash you supplied; "
                "not an origin re-fetch — prefer url+content_hash or request_id"
            ),
            **detail,
        }

    return JSONResponse(
        status_code=422,
        content=error_envelope(
            ErrorCode.INVALID_REQUEST,
            (
                "provide url+content_hash (origin re-fetch), "
                "request_id (receipt re-fetch), or content+content_hash "
                "(legacy non-independent arithmetic)"
            ),
        ),
    )


@app.post(ATTESTATION_VERIFY_PATH)
async def verify_attestation_endpoint(req: VerifyAttestationRequest):
    """Check an N1.1 EIP-191 EvidenceRecord attestation (free, no payment).

    Returns whether the signature recovers to the claimed (or expected)
    operator address over the bound fields. Honest limits: not proof the
    origin served this body to others; not an on-chain anchor; settlements
    remain operator-reported elsewhere.
    """
    from veritas.notary.sign import SCHEME, verify_attestation

    ok, reason = verify_attestation(
        req.evidence_record,
        req.attestation,
        expected_signer=req.expected_signer,
    )
    body: dict[str, Any] = {
        "valid": ok,
        "reason": reason,
        "scheme": req.attestation.get("scheme") or SCHEME,
        "note": (
            "EIP-191 recovery over bound record fields; "
            "not an on-chain anchor and not a re-fetch of the origin"
        ),
    }
    if isinstance(req.attestation.get("signer"), str):
        body["claimed_signer"] = req.attestation["signer"]
    return body


@app.get("/v1/receipts/{request_id}")
async def receipt(request_id: str):
    """Retrieve a stored custody record so results stay auditable after the call.

    200 — body present. 410 receipt_gone — we held it and retention deleted it.
    404 receipt_not_found — never seen. Collapsing pruned ids into 404 would
    make the endpoint unusable as an audit surface (O.6 / O10).
    """
    presence = store.lookup(request_id)
    if presence is ReceiptPresence.PRESENT:
        record = store.load(request_id)
        if record is not None:
            return record
        # Race: pruned between lookup and load → gone, not unknown.
        presence = store.lookup(request_id)
    if presence is ReceiptPresence.GONE:
        return JSONResponse(status_code=410, content=error_envelope(
            ErrorCode.RECEIPT_GONE, request_id=request_id,
        ))
    return JSONResponse(status_code=404, content=error_envelope(
        ErrorCode.RECEIPT_NOT_FOUND, request_id=request_id,
    ))


@app.get("/v1/trust")
async def trust():
    s = score_service()
    return s.to_dict()


@app.get("/v1/schema")
async def schema():
    """The wire contract as JSON Schema, generated from veritas.schema."""
    from veritas.schema import response_json_schema

    return {
        "response": response_json_schema(),
        "error_envelope": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "VeritasErrorEnvelope",
            "type": "object",
            "required": ["error"],
            "properties": {
                "error": {"type": "string", "enum": sorted(ERROR_REGISTRY)},
                "detail": {},
            },
            "description": (
                "All non-402 error responses. 402s use the x402 challenge "
                "shape instead; see /v1/errors."
            ),
        },
        "openapi": "/openapi.json",
    }


@app.get("/v1/errors")
async def errors():
    """The registered failure surface, so an agent can learn it before paying."""
    return {
        "errors": ERROR_REGISTRY,
        "exceptions": {
            "payment_challenge": (
                "402 responses use the x402 challenge shape (x402Version, accepts, "
                "free-text error), owned by the x402 spec rather than this registry."
            ),
        },
    }


@app.get("/v1/constitution")
async def constitution():
    """The venue constitution: enforced-or-aspirational articles, free to read."""
    return build_constitution()


@app.get("/v1/identity")
async def identity():
    cfg = get_payment_config()
    return build_identity(pay_to=cfg.pay_to, network=cfg.network, price=cfg.price)


class SiwxChallengeRequest(BaseModel):
    address: str | None = Field(
        default=None,
        description="Optional 0x address; when set the challenge includes a ready-to-sign message.",
    )


class SiwxVerifyRequest(BaseModel):
    message: str = Field(..., min_length=1)
    signature: str = Field(..., min_length=1)


def _siwx_domain_and_uri() -> tuple[str, str]:
    """Domain and URI advertised in SIWx challenges (from public URL)."""
    base = (os.getenv("VERITAS_PUBLIC_URL") or "").strip().rstrip("/")
    if base:
        # hostname without scheme for EIP-4361 domain
        without = base.split("://", 1)[-1]
        domain = without.split("/", 1)[0]
        uri = f"{base}/v1/siwx/verify"
        return domain, uri
    return "localhost", "http://localhost/v1/siwx/verify"


@app.post("/v1/siwx/challenge")
async def siwx_challenge(req: SiwxChallengeRequest):
    """Issue a one-time SIWx challenge for credit-session establishment (M7)."""
    cfg = get_payment_config()
    domain, uri = _siwx_domain_and_uri()
    chain_id = (cfg.network or "eip155:84532").split(":")[-1]
    try:
        challenge = siwx_store.create_challenge(
            domain=domain,
            uri=uri,
            chain_id=chain_id,
            address=req.address,
        )
    except SiwxError:
        return JSONResponse(
            status_code=422,
            content=error_envelope(
                ErrorCode.INVALID_REQUEST,
                "SIWx challenge request rejected",
            ),
        )
    return challenge


@app.post("/v1/siwx/verify")
async def siwx_verify(req: SiwxVerifyRequest):
    """Verify a SIWx signature and issue an X-VERITAS-SESSION token (M7)."""
    cfg = get_payment_config()
    domain, uri = _siwx_domain_and_uri()
    chain_id = (cfg.network or "eip155:84532").split(":")[-1]
    try:
        session = siwx_store.issue_session(
            message=req.message,
            signature=req.signature,
            expected_domain=domain,
            expected_uri=uri,
            expected_chain_id=chain_id,
        )
    except SiwxVerifyError:
        # Never surface recovery/parse exception detail to the caller.
        return JSONResponse(
            status_code=401,
            content=error_envelope(
                ErrorCode.SIWX_INVALID,
                "SIWx signature or challenge verification failed",
            ),
        )
    except SiwxError:
        return JSONResponse(
            status_code=422,
            content=error_envelope(
                ErrorCode.INVALID_REQUEST,
                "SIWx verify request rejected",
            ),
        )
    return session


@app.get("/v1/credits")
async def credits_balance(request: Request):
    """Return prepaid credit balance for the SIWx session (M7)."""
    token = request.headers.get(SESSION_HEADER)
    if not token:
        return JSONResponse(
            status_code=401,
            content=error_envelope(
                ErrorCode.SESSION_INVALID,
                f"{SESSION_HEADER} required",
            ),
        )
    try:
        session = siwx_store.resolve(token)
    except SiwxSessionError:
        return JSONResponse(
            status_code=401,
            content=error_envelope(
                ErrorCode.SESSION_INVALID,
                "SIWx session missing, unknown, or expired",
            ),
        )
    return credit_ledger.summary(session.address)


@app.post(CREDITS_TOPUP_PATH)
async def credits_topup(request: Request):
    """Top up prepaid credits by settling one x402 payment (M7).

    Free/misconfigured modes refuse — credits are not invented. On settle
    success the paid atomic amount is granted as a ``topup`` journal entry.
    """
    cfg = get_payment_config()
    if cfg.mode == "misconfigured":
        return JSONResponse(
            status_code=503,
            content=error_envelope(ErrorCode.PAYMENT_MISCONFIGURED, cfg.config_errors),
        )
    if not cfg.require_payment:
        return JSONResponse(
            status_code=503,
            content=error_envelope(
                ErrorCode.CREDITS_TOPUP_UNAVAILABLE,
                "credit top-up requires live payment mode; free mode cannot invent credits",
            ),
        )
    token = request.headers.get(SESSION_HEADER)
    if not token:
        return JSONResponse(
            status_code=401,
            content=error_envelope(
                ErrorCode.SESSION_INVALID,
                f"{SESSION_HEADER} required to attribute top-up credits",
            ),
        )
    try:
        session = siwx_store.resolve(token)
    except SiwxSessionError:
        return JSONResponse(
            status_code=401,
            content=error_envelope(
                ErrorCode.SESSION_INVALID,
                "SIWx session missing, unknown, or expired",
            ),
        )

    payment_header = request.headers.get("X-PAYMENT")
    base = (os.getenv("VERITAS_PUBLIC_URL") or "").strip().rstrip("/")
    topup_resource = f"{base}{CREDITS_TOPUP_PATH}" if base else CREDITS_TOPUP_PATH
    try:
        requirements = build_payment_requirements(
            pay_to=cfg.pay_to,
            network=cfg.network,
            price=cfg.price,
            resource=topup_resource,
        )
    except PriceError:
        return JSONResponse(
            status_code=503,
            content=error_envelope(
                ErrorCode.PAYMENT_MISCONFIGURED,
                "price configuration rejected at top-up challenge",
            ),
        )
    requirements_dict = requirements.to_dict()
    if not payment_header:
        return JSONResponse(
            status_code=402,
            content=build_402_challenge(
                cfg.pay_to, cfg.network, cfg.price, topup_resource,
                error="X-PAYMENT required to top up credits",
            ),
            headers=PAYMENT_REQUIRED_HEADER,
        )
    payment_payload = decode_payment_header(payment_header)
    if payment_payload is None:
        return JSONResponse(
            status_code=402,
            content=build_402_challenge(
                cfg.pay_to, cfg.network, cfg.price, topup_resource,
                error="X-PAYMENT header is not valid base64-encoded JSON",
            ),
            headers=PAYMENT_REQUIRED_HEADER,
        )
    nonce = extract_nonce(payment_payload)
    if nonce is None:
        return JSONResponse(
            status_code=409,
            content=error_envelope(
                ErrorCode.PAYMENT_NONCE_MISSING,
                "top-up payment authorization has no usable nonce",
            ),
        )
    facilitator = get_facilitator(cfg.facilitator, live=True)
    verification = facilitator.verify(payment_payload, requirements_dict)
    if not verification.is_valid:
        reason = verification.invalid_reason or "payment_invalid"
        if reason.startswith(VERIFICATION_OUTAGE_PREFIXES):
            return JSONResponse(
                status_code=503,
                content=error_envelope(ErrorCode.PAYMENT_VERIFICATION_UNAVAILABLE, reason),
            )
        return JSONResponse(
            status_code=402,
            content=build_402_challenge(
                cfg.pay_to, cfg.network, cfg.price, topup_resource, error=reason,
            ),
            headers=PAYMENT_REQUIRED_HEADER,
        )
    request_id = str(uuid.uuid4())
    claim = ledger.claim(
        nonce, request_id,
        network=requirements_dict.get("network"),
        asset=requirements_dict.get("asset"),
        amount=requirements_dict.get("maxAmountRequired"),
        pay_to=requirements_dict.get("payTo"),
        payer=verification.payer,
        price=cfg.price,
        price_version=PRICE_TABLE_VERSION,
    )
    if not claim.claimed:
        return JSONResponse(
            status_code=409,
            content=error_envelope(
                ErrorCode.PAYMENT_NONCE_ALREADY_SPENT,
                "this top-up authorization was already used",
            ),
        )
    # Top-up is the deliverable: record delivery then settle, then grant credits.
    topup_body = {
        "status": "completed",
        "billable": True,
        "kind": "credits_topup",
        "account": session.address,
        "request_id": request_id,
    }
    ledger.record_delivery(
        request_id,
        status="completed",
        billable=True,
        custody_root=None,
        query="credits_topup",
        response=topup_body,
    )
    settlement = facilitator.settle(payment_payload, requirements_dict)
    ledger.record_settlement(
        request_id,
        outcome=settlement.outcome,
        transaction=settlement.transaction,
        network=settlement.network,
        payer=settlement.payer,
        reason=settlement.error_reason,
    )
    metrics.increment("veritas_settlements_total", {"outcome": settlement.outcome})
    if settlement.outcome != "settled":
        # Do not grant credits without settled payment. Indeterminate is not
        # a grant: funds may have moved, but we do not invent balance on maybe.
        return JSONResponse(
            status_code=402 if settlement.outcome == "failed" else 200,
            content={
                "topped_up": False,
                "reason": (
                    "settlement_failed"
                    if settlement.outcome == "failed"
                    else "settlement_indeterminate_no_credit_grant"
                ),
                "payment": settlement.to_dict(),
                "balance": credit_ledger.balance(session.address),
            },
            headers=_payment_response_header(settlement.to_dict()),
        )
    try:
        atomic = int(requirements_dict.get("maxAmountRequired") or "0")
    except (TypeError, ValueError):
        atomic = 0
    if atomic <= 0:
        return JSONResponse(
            status_code=503,
            content=error_envelope(
                ErrorCode.PAYMENT_MISCONFIGURED,
                "top-up atomic amount unusable",
            ),
        )
    entry = credit_ledger.topup(
        session.address,
        atomic,
        request_id=request_id,
        note="x402_topup_settled",
    )
    return JSONResponse(
        status_code=200,
        content={
            "topped_up": True,
            "account": session.address,
            "granted": atomic,
            "entry_id": entry.id,
            "balance": credit_ledger.balance(session.address),
            "payment": settlement.to_dict(),
        },
        headers=_payment_response_header(settlement.to_dict()),
    )


@app.get("/.well-known/x402")
async def well_known():
    cfg = get_payment_config()
    body: dict[str, Any] = {
        "x402Version": 1,
        "resources": [
            {"resource": resource_url(), "method": "POST"},
            {"resource": notarize_resource_url(), "method": "POST"},
        ],
        "facilitator": cfg.facilitator,
        "network": cfg.network,
        "mode": cfg.mode,
        # An empty accepts is an honest "no offer"; configured_price is the
        # price that would apply in live mode — config, not an offer.
        "accepts": [],
        "configured_price": cfg.price,
        # Discovery must be self-traversing: one document reaches every
        # machine-readable surface. Relative paths, so no base URL is faked.
        "links": {
            "identity": "/v1/identity",
            "health": "/health",
            "readiness": "/readyz",
            "trust": "/v1/trust",
            "constitution": "/v1/constitution",
            "errors": "/v1/errors",
            "schema": "/v1/schema",
            "openapi": "/openapi.json",
            "llms": "/llms.txt",
            "siwx_challenge": "/v1/siwx/challenge",
            "siwx_verify": "/v1/siwx/verify",
            "credits": "/v1/credits",
            "credits_topup": CREDITS_TOPUP_PATH,
            # Advertised only because POST /v1/notarize exists (N0.5).
            "notarize": NOTARIZE_PATH,
            # Free N1.2 surface: agents re-check operator EIP-191 attestations.
            "attestations_verify": ATTESTATION_VERIFY_PATH,
            # Only advertised when it exists: absent, the endpoint 404s and
            # its absence should not be a thing to probe for.
            **({"metrics": "/metrics"} if METRICS_ENABLED else {}),
        },
    }
    if cfg.is_live_ready():
        try:
            body["accepts"] = [build_payment_requirements(
                cfg.pay_to, cfg.network, cfg.price, resource_url(),
            ).to_dict()]
        except PriceError:
            # Category only, same as the /v1/research path: the exception
            # text describes server-side configuration.
            body["error"] = "payment_misconfigured: price configuration rejected"
    return body


@app.get("/metrics")
async def metrics_endpoint(request: Request):
    """Prometheus counters, behind a token because they include revenue.

    `veritas_settlements_total` is a revenue figure. Serving that unpaid and
    unauthenticated would publish a competitor's view of the business, which
    would be a strange default for a service whose product is carefulness
    about what it discloses. Absent a configured token the endpoint does not
    exist at all — 404, not 401, so its absence leaks nothing either.
    """
    if not METRICS_ENABLED:
        return JSONResponse(status_code=404, content=error_envelope(
            ErrorCode.RECEIPT_NOT_FOUND, "metrics are not enabled on this instance",
        ))
    if not hmac.compare_digest(_presented_metrics_token(request), METRICS_TOKEN):
        return JSONResponse(status_code=401, content=error_envelope(
            ErrorCode.INVALID_REQUEST, "metrics require the configured bearer token",
        ))
    return PlainTextResponse(
        metrics.render(), media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/llms.txt")
async def llms_txt():
    """Agent-readable discovery index; the repo-root llms.txt mirrors this."""
    return PlainTextResponse(LLMS_TXT)


def main() -> None:
    """Console entry point (`veritas-server`)."""
    import uvicorn

    configure_logging()
    uvicorn.run(
        "veritas.server:app",
        host=os.getenv("VERITAS_HOST", "127.0.0.1"),
        port=int(os.getenv("VERITAS_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
