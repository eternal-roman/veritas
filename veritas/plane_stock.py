"""One-shot control-plane stock — reduce multi-agent stock lag.

Run: ``python -m veritas.plane_stock``

Prints JSON: tip, claim, open PRs (via ``gh`` if available), RPC probe bits.
Agents should stock from this instead of divergent memory / partial ``gh`` calls.

Does not invent settlement. Does not open PRs.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


def _run(cmd: list[str], timeout: float = 30.0) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode, out.strip()
    except Exception as e:  # noqa: BLE001
        return 1, f"{type(e).__name__}: {e}"


def _git_tip() -> dict[str, Any]:
    code, out = _run(["git", "rev-parse", "--short", "origin/main"])
    if code != 0:
        code, out = _run(["git", "rev-parse", "--short", "HEAD"])
    sha = out.splitlines()[-1] if out else "?"
    _, subj = _run(["git", "log", "-1", "--format=%s", "origin/main"])
    if not subj:
        _, subj = _run(["git", "log", "-1", "--format=%s", "HEAD"])
    return {"sha": sha, "subject": subj.splitlines()[-1] if subj else ""}


def _claim(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"status": "unknown", "path": str(path)}
    text = path.read_text(encoding="utf-8")
    status = "unknown"
    m = re.search(r"\*\*status:\*\*\s*(\w+)", text)
    if m:
        status = m.group(1)
    return {"status": status, "path": str(path)}


def _open_prs() -> dict[str, Any]:
    code, out = _run(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "open",
            "--limit",
            "20",
            "--json",
            "number,title,headRefName,isDraft,url",
        ]
    )
    if code != 0:
        return {
            "ok": False,
            "error": out[:500],
            "product": [],
            "docs": [],
            "all": [],
        }
    try:
        rows = json.loads(out) if out else []
    except json.JSONDecodeError:
        return {"ok": False, "error": "json decode", "product": [], "docs": [], "all": []}
    product: list[dict[str, Any]] = []
    docs: list[dict[str, Any]] = []
    for r in rows:
        title = str(r.get("title") or "")
        head = str(r.get("headRefName") or "")
        entry = {
            "number": r.get("number"),
            "title": title,
            "head": head,
            "draft": bool(r.get("isDraft")),
            "url": r.get("url"),
        }
        is_docs = (
            head.startswith("docs/")
            or title.lower().startswith("docs")
            or "restock" in title.lower()
            or "hygiene" in title.lower()
        )
        if is_docs:
            docs.append(entry)
        else:
            product.append(entry)
    return {"ok": True, "error": None, "product": product, "docs": docs, "all": rows}


def stock(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or Path.cwd()
    claim_path = root / "docs" / "program" / "flywheel-claim.md"
    tip = _git_tip()
    claim = _claim(claim_path)
    prs = _open_prs()
    rpc = os.environ.get("VERITAS_RPC_URL")
    fac = os.environ.get("VERITAS_FACILITATOR_URL") or os.environ.get(
        "X402_FACILITATOR_URL"
    )
    free_hold = claim.get("status") == "free" and not prs.get("product")
    return {
        "tip": tip,
        "claim": claim,
        "open_prs": prs,
        "env": {
            "VERITAS_RPC_URL": "set" if rpc else "unset (public testnet default available)",
            "facilitator": "set" if fac else "unset (public default available)",
        },
        "idle_true_candidate": free_hold,
        "not_x402_settlement": True,
        "stock_protocol": "plane_stock_v1",
    }


def main() -> None:
    print(json.dumps(stock(), indent=2))


if __name__ == "__main__":
    main()
