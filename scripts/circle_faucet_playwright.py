#!/usr/bin/env python3
"""Request testnet USDC from Circle's public faucet via Playwright.

Target: https://faucet.circle.com/ — Base Sepolia USDC (20 USDC / address / 2h).

Honest limits:
* reCAPTCHA blocks fully unattended funding. Use ``--headed --wait-human N``
  so a human can complete captcha and click Send.
* Does not invent balances — probes chain via public RPC after the attempt.

Usage::

    python scripts/circle_faucet_playwright.py --address 0x... --network "Base Sepolia"
    python scripts/circle_faucet_playwright.py --address 0x... --headed --wait-human 120
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FAUCET_URL = "https://faucet.circle.com/"
USDC_BASE_SEPOLIA = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
DEFAULT_RPC = "https://sepolia.base.org"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def eth_call_balance(rpc: str, token: str, holder: str) -> dict[str, Any]:
    addr = holder.lower().replace("0x", "").zfill(64)
    data = "0x70a08231" + addr
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [{"to": token, "data": data}, "latest"],
    }
    req = urllib.request.Request(
        rpc,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "veritas-circle-faucet/0.8.1",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310
        payload = json.loads(resp.read().decode())
    if "error" in payload:
        return {"ok": False, "error": payload["error"]}
    raw = int(payload["result"], 16)
    return {
        "ok": True,
        "atomic": raw,
        "usdc": raw / 1_000_000,
        "token": token,
        "holder": holder,
        "rpc": rpc,
    }


def request_faucet(
    address: str,
    *,
    network_label: str = "Base Sepolia",
    headed: bool = False,
    wait_human_sec: int = 0,
    timeout_ms: int = 90_000,
) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    report: dict[str, Any] = {
        "started_at": _now(),
        "address": address,
        "network_label": network_label,
        "faucet_url": FAUCET_URL,
        "headed": headed,
        "steps": [],
        "submitted": False,
        "captcha_blocked": False,
        "notes": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        page.goto(FAUCET_URL, wait_until="domcontentloaded", timeout=timeout_ms)
        report["steps"].append({"step": "goto", "title": page.title(), "url": page.url})

        try:
            for sel in (
                'button:has-text("Arc Testnet")',
                'button:has-text("Base Sepolia")',
                'button:has-text("Network")',
                '[role="combobox"]',
            ):
                loc = page.locator(sel).first
                if loc.count() and loc.is_visible():
                    loc.click(timeout=5_000)
                    report["steps"].append({"step": "open_network", "sel": sel})
                    break
            page.wait_for_timeout(400)
            opted = False
            for sel in (
                f'span[title="{network_label}"]',
                f'li:has-text("{network_label}")',
                f'div[role="option"]:has-text("{network_label}")',
            ):
                opt = page.locator(sel).first
                if opt.count():
                    opt.click(timeout=8_000, force=True)
                    report["steps"].append(
                        {"step": "select_network", "network": network_label, "sel": sel}
                    )
                    opted = True
                    break
            if not opted:
                page.get_by_text(network_label, exact=True).first.click(
                    timeout=8_000, force=True
                )
                report["steps"].append(
                    {
                        "step": "select_network",
                        "network": network_label,
                        "sel": "get_by_text",
                    }
                )
            page.wait_for_timeout(500)
        except Exception as exc:  # noqa: BLE001
            report["steps"].append({"step": "network_select_error", "error": str(exc)})
            report["notes"].append("network select failed — try --headed")

        try:
            for sel in (
                'input[placeholder*="0x" i]',
                'input[placeholder*="address" i]',
                'input[type="text"]',
            ):
                loc = page.locator(sel).first
                if loc.count() and loc.is_visible():
                    loc.fill(address)
                    report["steps"].append({"step": "fill_address", "sel": sel})
                    break
        except Exception as exc:  # noqa: BLE001
            report["steps"].append({"step": "fill_address_error", "error": str(exc)})

        frames = [f.url for f in page.frames]
        if any("recaptcha" in (u or "").lower() for u in frames):
            report["captcha_blocked"] = True
            report["notes"].append(
                "reCAPTCHA present — use --headed --wait-human and complete challenge"
            )

        if wait_human_sec > 0 and headed:
            report["notes"].append(
                f"waiting {wait_human_sec}s for human captcha + click Send"
            )
            time.sleep(wait_human_sec)
        else:
            try:
                clicked = False
                for sel in (
                    'button:has-text("Send 20 USDC")',
                    'button:has-text("Send 20")',
                    'button:has-text("USDC")',
                ):
                    loc = page.locator(sel).first
                    if loc.count() and loc.is_visible():
                        loc.click(timeout=10_000)
                        report["steps"].append({"step": "click_send", "sel": sel})
                        clicked = True
                        break
                page.wait_for_timeout(8_000)
                report["submitted"] = clicked
            except Exception as exc:  # noqa: BLE001
                report["steps"].append({"step": "click_send_error", "error": str(exc)})
                report["notes"].append("Send click failed (often captcha)")

        try:
            body_text = page.locator("body").inner_text(timeout=5_000)[:2000]
            report["page_text_snippet"] = body_text
            lower = body_text.lower()
            if "limit exceeded" in lower:
                report["notes"].append("Limit Exceeded visible on page")
            if "unusual traffic" in lower or "not a bot" in lower:
                report["captcha_blocked"] = True
                report["notes"].append("bot detection / captcha challenge visible")
            # Verify network label applied
            if network_label.lower() in lower:
                report["notes"].append(f"page text mentions {network_label}")
        except Exception as exc:  # noqa: BLE001
            report["steps"].append({"step": "read_body_error", "error": str(exc)})

        browser.close()

    report["finished_at"] = _now()
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--address", required=True)
    ap.add_argument("--network", default="Base Sepolia")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--wait-human", type=int, default=0)
    ap.add_argument("--rpc", default=DEFAULT_RPC)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    bal_before = eth_call_balance(args.rpc, USDC_BASE_SEPOLIA, args.address)
    faucet = request_faucet(
        args.address,
        network_label=args.network,
        headed=args.headed,
        wait_human_sec=args.wait_human,
    )
    if faucet.get("submitted") and not faucet.get("captcha_blocked"):
        time.sleep(8)
    bal_after = eth_call_balance(args.rpc, USDC_BASE_SEPOLIA, args.address)

    report = {
        "faucet": faucet,
        "balance_before": bal_before,
        "balance_after": bal_after,
        "funded": bool(
            bal_after.get("ok")
            and bal_before.get("ok")
            and bal_after.get("atomic", 0) > bal_before.get("atomic", 0)
        ),
        "has_balance": bool(bal_after.get("ok") and bal_after.get("atomic", 0) > 0),
    }
    out = Path(args.out) if args.out else Path(".veritas_dogfood") / (
        f"faucet_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"wrote {out}", file=sys.stderr)
    if report["has_balance"] or report["funded"]:
        return 0
    if faucet.get("captcha_blocked"):
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
