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
from veritas.observability import Metrics, configure_logging, log_request
from veritas.payment_config import get_payment_config
from veritas.pipeline import run_research
from veritas.pricing import PRICE_TABLE_VERSION, current_price_point
from veritas.trust import OutcomeLog, score_service
from veritas.x402 import (
    PriceError,
    build_402_challenge,
    build_payment_requirements,
    decode_payment_header,
    extract_nonce,
    payment_authorization,
)

app = FastAPI(title="Veritas Research", version=__version__)

RESOURCE_PATH = "/v1/research"

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
    """The absolute URL of the paid resource, as x402 expects in `resource`.

    Falls back to the bare path only when no public URL is configured, which
    live mode refuses (see veritas/payment_config.py) — so a published
    challenge always names something a counterparty can dial.
    """
    base = (os.getenv("VERITAS_PUBLIC_URL") or "").strip().rstrip("/")
    return f"{base}{RESOURCE_PATH}" if base else RESOURCE_PATH


store = CustodyStore()
outcomes = OutcomeLog()
ledger = Ledger()

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


class VerifyRequest(BaseModel):
    content: str = Field(max_length=MAX_VERIFY_CONTENT_CHARS)
    content_hash: str = Field(max_length=256)


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


def _challenge(cfg, error: str | None = None) -> JSONResponse:
    kwargs = {"error": error} if error else {}
    return JSONResponse(
        status_code=402,
        content=build_402_challenge(
            cfg.pay_to, cfg.network, cfg.price, resource_url(), **kwargs,
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
    try:
        return await run_in_threadpool(
            _research, req, request.headers.get("X-PAYMENT"),
        )
    finally:
        research_slots.release()


def _research(req: ResearchRequest, payment_header: str | None):
    cfg = get_payment_config()
    payment_payload: dict[str, Any] | None = None
    requirements_dict: dict[str, Any] | None = None
    facilitator = None
    deadline: Deadline | None = None
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

    if cfg.require_payment:
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

    # The window may have closed while we worked. Settling now would present an
    # expired authorization; the buyer is not charged and is told to retry with
    # a fresh one, which is the honest outcome for our own slowness.
    if deadline is not None and deadline.expired():
        result["billable"] = False
        result["status"] = "unavailable"
        result["refusal_reason"] = "retrieval_unavailable"
        result["error"] = ErrorCode.DEADLINE_EXCEEDED.value
        result["payment"] = {"settled": False, "reason": "deadline_exceeded_before_settlement"}
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
    outcomes.record(result["status"], bool(result["custody_valid"]),
                    bool(result["billable"]), paid=cfg.require_payment)

    # Record what we produced BEFORE settlement is attempted, and fsync it. A
    # crash between the two then leaves a durable statement that we owe this
    # buyer a deliverable and may or may not have been paid — which is
    # reconcilable — rather than silence, which is not. Non-billable work
    # abandons the authorization, so the ledger refuses to settle it.
    if cfg.require_payment:
        ledger.record_delivery(
            request_id, status=result["status"], billable=bool(result["billable"]),
            custody_root=result.get("custody_root"), query=req.query, response=result,
        )

    # Retrieval failures are ours, not the buyer's: never settle for them.
    if result["status"] == "unavailable":
        result["payment"] = {"settled": False, "reason": "not_billable_retrieval_unavailable"}
        # The registry code is additive: the full research body stays because
        # the unavailability report is itself the deliverable here.
        result["error"] = ErrorCode.RETRIEVAL_UNAVAILABLE.value
        return JSONResponse(status_code=503, content=result)

    if cfg.require_payment and facilitator is not None:
        return _settle_and_respond(
            result, request_id, facilitator, payment_payload, requirements_dict,
        )

    result["payment"] = {"settled": False, "mode": cfg.mode, "reason": "free_mode"}
    return result


@app.post("/v1/verify")
async def verify(req: VerifyRequest):
    """Let any agent independently re-check an evidence hash we published."""
    ok, detail = verify_content_hash(req.content, req.content_hash)
    return {"valid": ok, **detail}


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


@app.get("/.well-known/x402")
async def well_known():
    cfg = get_payment_config()
    body: dict[str, Any] = {
        "x402Version": 1,
        "resources": [{"resource": resource_url(), "method": "POST"}],
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
