"""Routine G9 compose: local reconcile + chain classify + optional alert.

``veritas-ops reconcile-chain`` is a method. Production still needed a
loop that runs it on a schedule and tells someone when the report is not
clean. This module is that loop.

It does not rewrite the ledger, invent revenue, default a mainnet RPC,
or claim the chain is settled because the facilitator said so. Alert
bodies carry counts and request ids — never an ``X-PAYMENT`` payload.

``VERITAS_RECONCILE_ALERT_URL`` is scheme-checked with
``require_http_url``. Unset means the report stays on stdout only.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from veritas import __version__
from veritas.ledger import Ledger
from veritas.safeurl import UnsafeUrlError, require_http_url

ALERT_URL_ENV = "VERITAS_RECONCILE_ALERT_URL"
DEFAULT_INTERVAL_SECONDS = 300
ALERT_TIMEOUT_SECONDS = 10.0

USER_AGENT = f"veritas-reconcile-loop/{__version__}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _chain_needs_attention(chain: dict[str, Any]) -> bool:
    if chain.get("error"):
        return True
    for key in ("mismatched", "not_found", "failed", "rpc_not_configured"):
        value = chain.get(key)
        if isinstance(value, int) and value > 0:
            return True
        if isinstance(value, list) and value:
            return True
    classifications = chain.get("classifications") or chain.get("results") or []
    if isinstance(classifications, list):
        for row in classifications:
            if not isinstance(row, dict):
                continue
            status = (row.get("status") or row.get("classification") or "").lower()
            if status and status not in {"confirmed", "ok", "match"}:
                return True
    return False


def send_alert(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST the report to an operator webhook. Never raises into the loop."""
    try:
        safe = require_http_url(url)
    except UnsafeUrlError as exc:
        return {"ok": False, "error": f"alert_url_refused:{type(exc).__name__}"}
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    request = urllib.request.Request(
        safe,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(  # nosec B310 - scheme checked by require_http_url
            request, timeout=ALERT_TIMEOUT_SECONDS,
        ) as response:
            return {"ok": 200 <= response.status < 300, "status": response.status}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "error": "alert_http_error"}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "error": f"alert_transport:{type(exc).__name__}"}


def run_once(
    ledger: Ledger | None = None,
    *,
    alert_url: str | None = None,
    transport: Any = None,
) -> dict[str, Any]:
    """One local reconcile + one chain classify. Optionally alert."""
    store = ledger or Ledger()
    from veritas.ops_cli import _reconcile

    local = _reconcile(store)
    chain = store.reconcile_against_chain(transport=transport)
    needs_alert = (not local.get("clean", True)) or _chain_needs_attention(chain)
    report: dict[str, Any] = {
        "ran_at": _now(),
        "local": local,
        "chain": chain,
        "needs_alert": needs_alert,
        "alerted": False,
        "alert": None,
        "limitation": (
            "Routine compose of intra-instance reconcile and report-only "
            "chain classify. Does not rewrite the ledger. Mainnet still "
            "needs VERITAS_RPC_URL."
        ),
    }
    dest = alert_url if alert_url is not None else (os.getenv(ALERT_URL_ENV) or "").strip()
    if needs_alert and dest:
        # Strip the bulky local summary / deliverable blobs before shipping.
        alert_body = {
            "ran_at": report["ran_at"],
            "needs_alert": True,
            "local_clean": local.get("clean"),
            "needs_attention": local.get("needs_attention"),
            "chain": {
                k: chain[k]
                for k in (
                    "candidates", "confirmed", "mismatched", "not_found",
                    "failed", "rpc_not_configured", "error", "note",
                )
                if k in chain
            },
        }
        result = send_alert(dest, alert_body)
        report["alert"] = result
        report["alerted"] = bool(result.get("ok"))
    return report


def run_loop(
    *,
    interval: int = DEFAULT_INTERVAL_SECONDS,
    once: bool = False,
    ledger: Ledger | None = None,
    alert_url: str | None = None,
    sleep: Any = time.sleep,
    transport: Any = None,
) -> dict[str, Any]:
    """Run ``run_once`` once, or forever at ``interval`` seconds.

    ``sleep`` is injectable so tests do not wait. The last report is
    returned; a forever loop only returns if ``once`` is true or the
    caller stops iterating — this function itself loops until ``once``.
    """
    if interval < 1:
        raise ValueError("interval must be a positive number of seconds")
    report = run_once(ledger, alert_url=alert_url, transport=transport)
    if once:
        return report
    while True:  # pragma: no cover - the CLI daemon path
        sleep(interval)
        report = run_once(ledger, alert_url=alert_url, transport=transport)
