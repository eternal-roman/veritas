"""Machine-readable integration registry, served at ``GET /v1/hooks``.

Discovery's ``links`` object reaches every HTTP surface, but an agent
deciding whether and how to integrate needs more than routes: which CLI
tools exist and what their exit codes mean, which MCP tools a local stdio
server exposes, which headers carry payment and session state, and where
the durable signal stores live. That inventory existed only as prose spread
across README/AGENTS.md — this module is its single machine-readable source.

Constitution A28 binds it: every HTTP route the app mounts is either listed
here or named in ``EXCLUDED_ROUTE_PATHS``; the registry never advertises a
surface that does not exist; and the absence of push delivery is stated
outright rather than left to be inferred. ``tests/test_hooks.py`` reconciles
the registry against the live app in both directions.

This module must never import ``veritas.server`` (the server imports it);
paths are literals here and the tests compare them against ``app.routes``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from . import __version__
from .hashing import compute_content_hash
from .mcp_server import MCP_TOOL_NAMES
from .observability import METRIC_HELP

HOOKS_VERSION = "1.0"

VALID_KINDS = {"http", "mcp-tool", "cli", "header", "store"}
VALID_ACCESS = {"free", "payment-gated", "session-gated", "token-gated", "local"}

#: Routes the app mounts that the registry deliberately does not carry:
#: human HTML consoles only. Their machine-readable equivalent is
#: /openapi.json, which is registered.
EXCLUDED_ROUTE_PATHS = frozenset({"/docs", "/redoc", "/docs/oauth2-redirect"})

#: Interface keys each kind must carry, enforced at construction so a
#: malformed record fails at import, not at serve time.
_REQUIRED_INTERFACE_KEYS: dict[str, tuple[str, ...]] = {
    "http": ("method", "path"),
    "mcp-tool": ("tool", "server", "transport"),
    "cli": ("command", "exit_codes"),
    "header": ("header", "direction"),
    "store": ("location", "format", "read_via"),
}

#: No webhook, subscription, or callback machinery exists anywhere in this
#: codebase. Stating that here is load-bearing: an agent that assumes push
#: delivery waits forever. Flipping ``available`` requires shipping real
#: push code and updating ``validate_hooks``, which pins this to False.
PUSH: dict[str, Any] = {
    "available": False,
    "note": (
        "Every signal is pull: HTTP GET, CLI JSON on stdout, or files under "
        "the runtime directory. No webhook, subscription, or callback "
        "machinery exists."
    ),
}


def _hook(
    id: str,
    kind: str,
    name: str,
    description: str,
    access: str,
    interface: dict[str, Any],
    **extra: Any,
) -> dict[str, Any]:
    if kind not in VALID_KINDS:
        raise ValueError(f"{id}: invalid kind {kind!r}")
    if access not in VALID_ACCESS:
        raise ValueError(f"{id}: invalid access {access!r}")
    for key in _REQUIRED_INTERFACE_KEYS[kind]:
        if key not in interface:
            raise ValueError(f"{id}: {kind} interface missing {key!r}")
    record: dict[str, Any] = {
        "id": id,
        "kind": kind,
        "name": name,
        "description": description,
        "access": access,
        "interface": interface,
    }
    record.update(extra)
    return record


def _http(id: str, method: str, path: str, description: str,
          access: str = "free", **extra: Any) -> dict[str, Any]:
    return _hook(
        id, "http", path, description, access,
        {"method": method, "path": path}, **extra,
    )


def _mcp(tool: str, description: str) -> dict[str, Any]:
    return _hook(
        f"mcp_{tool}", "mcp-tool", tool, description, "local",
        {"tool": tool, "server": "veritas-mcp", "transport": "stdio"},
    )


def _cli(command: str, description: str, exit_codes: dict[str, str]) -> dict[str, Any]:
    return _hook(
        f"cli_{command.replace('veritas-', '').replace('-', '_')}",
        "cli", command, description, "local",
        {"command": command, "exit_codes": exit_codes},
    )


_EXIT_OK = {"0": "ok", "nonzero": "error"}

HOOKS: tuple[dict[str, Any], ...] = (
    # ------------------------------------------------------------- HTTP —
    _http("well_known", "GET", "/.well-known/x402",
          "Discovery document: payment requirements plus a links object that "
          "reaches every machine-readable surface."),
    _http("llms_txt", "GET", "/llms.txt",
          "Agent-readable plain-text index of the service."),
    _http("hooks", "GET", "/v1/hooks",
          "This registry: every integration surface, with push absence stated."),
    _http("identity", "GET", "/v1/identity",
          "Identity document with a stable content hash."),
    _http("constitution", "GET", "/v1/constitution",
          "The venue constitution: each article enforced or marked aspirational."),
    _http("schema", "GET", "/v1/schema",
          "The research wire contract as JSON Schema, plus the error envelope."),
    _http("errors", "GET", "/v1/errors",
          "Registered error codes with HTTP status and retriability."),
    _http("openapi", "GET", "/openapi.json",
          "OpenAPI description of every HTTP route."),
    _http("health", "GET", "/health",
          "Liveness plus payment mode; never rate limited."),
    _http("readyz", "GET", "/readyz",
          "Readiness; 503 when the process is alive but cannot serve."),
    _http("payment_config", "GET", "/v1/payment-config",
          "Payment mode and the current price point (configuration, not an offer)."),
    _http("research", "POST", "/v1/research",
          "The paid product: evidence-grounded research with custody chain; "
          "402 challenge in live mode, X-PAYMENT or credit session to proceed.",
          access="payment-gated"),
    _http("notarize", "POST", "/v1/notarize",
          "Paid observe-once evidence notary for a URL; same payment gates "
          "as research; unavailable is never billable.",
          access="payment-gated"),
    _http("verify", "POST", "/v1/verify",
          "Origin re-fetch verification of a published content hash."),
    _http("attestations_verify", "POST", "/v1/attestations/verify",
          "Free check of an EIP-191 EvidenceRecord attestation."),
    _http("packs_verify", "POST", "/v1/packs/verify",
          "Free integrity check of a portable EvidencePack."),
    _http("evidence_log", "GET", "/v1/log",
          "Operator-local Merkle evidence log root and count."),
    _http("evidence_log_proof", "GET", "/v1/log/proof",
          "Merkle inclusion proof for a log index."),
    _http("evidence_log_verify", "POST", "/v1/log/verify",
          "Free offline verification of an inclusion proof."),
    _http("receipts", "GET", "/v1/receipts/{request_id}",
          "Durable custody receipt; 410 when pruned, 404 when never issued."),
    _http("trust", "GET", "/v1/trust",
          "Behaviour-derived trust score; UNPROVEN below 10 paid outcomes."),
    _http("siwx_challenge", "POST", "/v1/siwx/challenge",
          "Issue a SIWx challenge for credit-session establishment."),
    _http("siwx_verify", "POST", "/v1/siwx/verify",
          "Verify a SIWx signature and receive an X-VERITAS-SESSION token."),
    _http("credits", "GET", "/v1/credits",
          "Prepaid credit balance for the presented session.",
          access="session-gated"),
    _http("credits_topup", "POST", "/v1/credits/topup",
          "Settle one x402 payment and grant prepaid credits (live mode only).",
          access="payment-gated"),
    _http("metrics", "GET", "/metrics",
          "Prometheus counters; settlement counters are revenue, so the "
          "route exists only when VERITAS_METRICS_TOKEN is configured.",
          access="token-gated", absent_without_config=True),
    # -------------------------------------------------- MCP (stdio) —
    _mcp("research", "Evidence-grounded research over the local free-mode engine."),
    _mcp("verify", "Re-check a published content hash."),
    _mcp("verify_attestation", "Check an EIP-191 EvidenceRecord attestation."),
    _mcp("verify_pack", "Check a portable EvidencePack's integrity."),
    _mcp("verify_log_inclusion", "Verify a local Merkle inclusion proof."),
    _mcp("trust", "Behaviour-derived trust score, honestly UNPROVEN when thin."),
    _mcp("constitution", "The venue constitution document."),
    # --------------------------------------------------------- CLIs —
    _cli("veritas-server", "Serve the HTTP surface (free mode by default).", _EXIT_OK),
    _cli("veritas-agent", "Zero-touch bootstrap: config plus wallet, then serve.", _EXIT_OK),
    _cli("veritas-mcp", "Serve the engine as local MCP tools over stdio.", _EXIT_OK),
    _cli("veritas-ops",
         "Operator reports off the ledger as JSON: revenue, owed, reconcile, "
         "reconcile-chain, existence, usage, pricing, authorization, prune.",
         _EXIT_OK),
    _cli("veritas-money-loop",
         "Compose one settle-then-reconcile pass and report it.", _EXIT_OK),
    _cli("veritas-diligence",
         "Vet an x402 seller off its published documents; the verdict is "
         "also the exit code.",
         {"0": "pass", "1": "fail", "2": "unverifiable", "3": "bad_input"}),
    _cli("veritas-buy",
         "Guided buyer journey: discover → diligence → unpaid pay-surface "
         "probe → optional verify/receipt. Never settles payment.",
         {
             "0": "ok",
             "1": "diligence_fail",
             "2": "unverifiable",
             "3": "bad_input",
             "4": "probe_error",
         }),
    _cli("veritas-audit",
         "Audit an attested pack against its origin; the verdict is also "
         "the exit code.",
         {"0": "confirmed", "1": "diverged", "2": "unobserved", "3": "bad_input"}),
    _cli("veritas-verify",
         "Single-file zero-dependency receipt verifier (vendor by copying "
         "veritas/verifier.py).", _EXIT_OK),
    _cli("veritas-evolver",
         "Evolutionary idea engine for the Evolver role: journaled "
         "first-principles recombination; WATCH output, never approval.",
         _EXIT_OK),
    # ------------------------------------------------------ headers —
    _hook("header_x_payment", "header", "X-PAYMENT",
          "Base64 x402 payment payload answering a 402 challenge.",
          "free", {"header": "X-PAYMENT", "direction": "request"}),
    _hook("header_x_payment_response", "header", "X-PAYMENT-RESPONSE",
          "Settlement result attached to a paid 200 response.",
          "free", {"header": "X-PAYMENT-RESPONSE", "direction": "response"}),
    _hook("header_payment_required", "header", "Payment-Required",
          "Marks a 402 as an x402 challenge (value: x402).",
          "free", {"header": "Payment-Required", "direction": "response"}),
    _hook("header_veritas_session", "header", "X-VERITAS-SESSION",
          "SIWx credit-session token spending prepaid credits.",
          "free", {"header": "X-VERITAS-SESSION", "direction": "request"}),
    # ------------------------------------------- durable signal stores —
    _hook("store_receipts", "store", "custody receipts",
          "One JSON custody receipt per request, durable until retention "
          "prunes it to a tombstone.",
          "free",
          {"location": "$VERITAS_RUNTIME_DIR/receipts/", "format": "json",
           "read_via": "GET /v1/receipts/{request_id}"}),
    _hook("store_ledger", "store", "money ledger",
          "Authorizations, deliveries, settlement attempts, and usage — this "
          "instance's own records; chain reconcile is the independent check.",
          "local",
          {"location": "$VERITAS_RUNTIME_DIR/ledger.sqlite3", "format": "sqlite",
           "read_via": "veritas-ops {revenue,owed,reconcile,reconcile-chain,usage}"}),
    _hook("store_trust_outcomes", "store", "trust outcome log",
          "Recorded outcome counters behind the trust score; only paid "
          "outcomes score.",
          "free",
          {"location": "$VERITAS_RUNTIME_DIR/trust.sqlite3", "format": "sqlite",
           "read_via": "GET /v1/trust"}),
    _hook("store_credits", "store", "credit ledger",
          "Prepaid credit balances and their debit/refund journal.",
          "session-gated",
          {"location": "$VERITAS_RUNTIME_DIR/credits.sqlite3", "format": "sqlite",
           "read_via": "GET /v1/credits"}),
    _hook("store_evidence_log", "store", "Merkle evidence log",
          "Operator-local append-only evidence log (not public CT, not "
          "on-chain).",
          "free",
          {"location": "$VERITAS_RUNTIME_DIR (operator-local)", "format": "merkle-log",
           "read_via": "GET /v1/log, GET /v1/log/proof, POST /v1/log/verify"}),
    _hook("store_metrics", "store", "Prometheus counters",
          "In-process counters; ephemeral per node, declared names only.",
          "token-gated",
          {"location": "in-process", "format": "prometheus-text",
           "read_via": "GET /metrics (VERITAS_METRICS_TOKEN required)"},
          names=sorted(METRIC_HELP)),
)


# The MCP records above carry individual descriptions but must never drift
# from what veritas-mcp actually registers; drift fails at import, not serve.
_mcp_drift = {
    h["interface"]["tool"] for h in HOOKS if h["kind"] == "mcp-tool"
} ^ set(MCP_TOOL_NAMES)
if _mcp_drift:
    raise ValueError(f"hooks registry disagrees with MCP_TOOL_NAMES: {sorted(_mcp_drift)}")


def http_paths() -> frozenset[str]:
    """Every HTTP path the registry carries, for reconciliation tests."""
    return frozenset(
        h["interface"]["path"] for h in HOOKS if h["kind"] == "http"
    )


def build_hooks() -> dict[str, Any]:
    """Return the served registry document with a stable content hash."""
    doc: dict[str, Any] = {
        "name": "Veritas integration registry",
        "hooks_version": HOOKS_VERSION,
        "veritas_version": __version__,
        "push": dict(PUSH),
        "excluded_routes": sorted(EXCLUDED_ROUTE_PATHS),
        "hooks": [dict(h) for h in HOOKS],
    }
    # Hash the stable body only; generatedAt is added after (see
    # veritas/identity.py for the defect this ordering prevents).
    doc["content_hash"] = compute_content_hash(json.dumps(doc, sort_keys=True))
    doc["generatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return doc


def validate_hooks(doc: dict[str, Any]) -> list[str]:
    """Return a list of registry-document violations; empty means conformant."""
    problems: list[str] = []

    for key in ("name", "hooks_version", "veritas_version", "push", "hooks", "content_hash"):
        if key not in doc:
            problems.append(f"missing field: {key}")
    if problems:
        return problems

    push = doc["push"]
    if push.get("available") is not False:
        problems.append(
            "push.available must be False: no push machinery exists; "
            "flipping this requires shipping it and changing this validator"
        )
    if not push.get("note"):
        problems.append("push.note missing")

    seen_ids: set[str] = set()
    for record in doc["hooks"]:
        rid = record.get("id", "<missing id>")
        if rid in seen_ids:
            problems.append(f"duplicate hook id: {rid}")
        seen_ids.add(rid)
        kind = record.get("kind")
        if kind not in VALID_KINDS:
            problems.append(f"{rid}: invalid kind {kind!r}")
            continue
        if record.get("access") not in VALID_ACCESS:
            problems.append(f"{rid}: invalid access {record.get('access')!r}")
        if not record.get("description"):
            problems.append(f"{rid}: missing description")
        interface = record.get("interface", {})
        for key in _REQUIRED_INTERFACE_KEYS[kind]:
            if key not in interface:
                problems.append(f"{rid}: {kind} interface missing {key!r}")
        if kind == "http" and not str(interface.get("path", "")).startswith("/"):
            problems.append(f"{rid}: http path must start with '/'")

    return problems
