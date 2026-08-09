"""Stage-1 existence scorecard — measured landmass, never invented demand.

Answers what the vision path (REFOUNDING Stage 1 / VISION.md) needs operators
and agents to track without restating stale card facts:

* how many **self-dogfood** testnet settlements have evidence on disk
* that **unsolicited** and **mainnet** remain zero until measured elsewhere
* which Stage-1 human residues remain (PyPI / TLS / mainnet pay-to)
* which agent-ready surfaces already ship (notary, dogfood, money_loop, …)
* optional **network probes** (``--probe``): PyPI project presence and public
  host ``/health`` when ``VERITAS_PUBLIC_URL`` is set — measured, never assumed

This module does **not** claim unsolicited demand, mainnet success, or
commercial product-worth. Run::

    python -m veritas.existence
    python -m veritas.existence --probe
    veritas-ops existence
    veritas-ops existence --probe
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from veritas import __version__

SCHEMA = "veritas.existence.v1"

# Repo-relative default: durable settlement transcripts from live contact.
DEFAULT_SETTLEMENT_DIR = Path("docs") / "program" / "fable" / "settlement"

# Human Stage-1 residues (REFOUNDING §4). Agents prepare 90%; humans finish.
STAGE1_HUMAN = (
    "pypi_trusted_publisher",
    "public_tls_host",
    "mainnet_pay_to",
    "registry_listing",
)

PYPI_PROJECT = "veritas-research"
PYPI_JSON_URL = f"https://pypi.org/pypi/{PYPI_PROJECT}/json"
DEFAULT_PROBE_TIMEOUT = 10

HttpGet = Callable[[str], tuple[int, bytes]]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _is_tx_hash(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    s = value.strip()
    if not (s.startswith("0x") or s.startswith("0X")):
        return False
    body = s[2:]
    return len(body) == 64 and all(c in "0123456789abcdefABCDEF" for c in body)


def _walk_tx_hashes(obj: Any, out: list[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("transaction", "tx_hash", "transactionHash") and _is_tx_hash(v):
                out.append(v.lower())
            else:
                _walk_tx_hashes(v, out)
    elif isinstance(obj, list):
        for item in obj:
            _walk_tx_hashes(item, out)


def scan_settlement_evidence(evidence_dir: Path) -> dict[str, Any]:
    """Count confirmed self-dogfood settlements from on-disk JSON transcripts.

    A file counts when ``acceptance.met`` is true **and** a 32-byte 0x
    transaction hash appears (acceptance.transaction or nested proof).
    Both transcript families count: ``settlement_*.json`` (direct recipe) and
    ``money_loop_*.json`` (composed 0.1-R runs) — the first live money-loop
    run was invisible to the scorecard because only the former was globbed,
    which made the measured signal undercount the evidence on disk.
    """
    confirmed: list[dict[str, Any]] = []
    incomplete = 0
    unreadable = 0

    if not evidence_dir.is_dir():
        return {
            "evidence_dir": str(evidence_dir),
            "files_scanned": 0,
            "testnet_settlements_confirmed": 0,
            "incomplete_or_failed_runs": 0,
            "unreadable": 0,
            "transactions": [],
            "by_file": [],
        }

    files = sorted(
        set(evidence_dir.glob("settlement_*.json"))
        | set(evidence_dir.glob("money_loop_*.json"))
    )
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            unreadable += 1
            continue

        acc = data.get("acceptance") if isinstance(data, dict) else None
        met = bool(isinstance(acc, dict) and acc.get("met") is True)
        txs: list[str] = []
        if isinstance(acc, dict) and _is_tx_hash(acc.get("transaction")):
            txs.append(str(acc["transaction"]).lower())
        _walk_tx_hashes(data, txs)
        # de-dupe preserve order
        seen: set[str] = set()
        uniq: list[str] = []
        for t in txs:
            if t not in seen:
                seen.add(t)
                uniq.append(t)

        if met and uniq:
            confirmed.append(
                {
                    "file": path.name,
                    "transaction": uniq[0],
                    "all_transactions": uniq,
                }
            )
        else:
            incomplete += 1

    # Unique txs across files (same settle re-logged should not inflate n).
    all_tx: list[str] = []
    seen_tx: set[str] = set()
    for row in confirmed:
        t = row["transaction"]
        if t not in seen_tx:
            seen_tx.add(t)
            all_tx.append(t)

    return {
        "evidence_dir": str(evidence_dir),
        "files_scanned": len(files),
        "testnet_settlements_confirmed": len(all_tx),
        "incomplete_or_failed_runs": incomplete,
        "unreadable": unreadable,
        "transactions": all_tx,
        "by_file": confirmed,
    }


def _agent_surfaces(root: Path) -> dict[str, bool]:
    return {
        "notary_package": (root / "veritas" / "notary" / "observe.py").is_file(),
        "verifier_entrypoint": (root / "veritas" / "verifier.py").is_file(),
        "money_loop": (root / "veritas" / "money_loop.py").is_file(),
        "product_worth": (
            root / "veritas" / "evaluations" / "product_worth.py"
        ).is_file(),
        "buyer_journey": (root / "veritas" / "buyer_journey.py").is_file(),
        "dogfood_commerce": (
            root / "scripts" / "dogfood_agent_commerce.py"
        ).is_file(),
        "circle_faucet_playwright": (
            root / "scripts" / "circle_faucet_playwright.py"
        ).is_file(),
        "release_workflow": (root / ".github" / "workflows" / "release.yml").is_file(),
        "chain_reconcile": (root / "veritas" / "chain_reconcile.py").is_file(),
        "existence_scorecard": (root / "veritas" / "existence.py").is_file(),
    }


def _default_http_get(
    url: str, *, timeout: int = DEFAULT_PROBE_TIMEOUT
) -> tuple[int, bytes]:
    request = urllib.request.Request(  # noqa: S310 - public HTTPS endpoints only
        url,
        headers={
            "User-Agent": f"veritas-existence/{__version__}",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(  # nosec B310 - caller supplies public URLs
            request, timeout=timeout
        ) as response:
            return int(response.status), response.read(65_536)
    except urllib.error.HTTPError as exc:
        body = b""
        if exc.fp is not None:
            try:
                body = exc.read(65_536)
            except OSError:
                body = b""
        return int(exc.code), body


def probe_pypi(
    *,
    http_get: HttpGet | None = None,
    project: str = PYPI_PROJECT,
) -> dict[str, Any]:
    """GET PyPI JSON API. 404 = not published; 200 = published (measured).

    Never invents publication. Network/errors → published null + error.
    """
    get = http_get or _default_http_get
    url = f"https://pypi.org/pypi/{project}/json"
    try:
        status, body = get(url)
    except (OSError, urllib.error.URLError, ValueError) as exc:
        return {
            "project": project,
            "url": url,
            "http_status": None,
            "published": None,
            "probed": True,
            "error": f"{type(exc).__name__}: {exc}",
            "note": "probe failed — do not treat as published or unpublished",
        }

    if status == 404:
        return {
            "project": project,
            "url": url,
            "http_status": 404,
            "published": False,
            "probed": True,
            "error": None,
            "note": (
                "Package not on PyPI (404). Human: create project + trusted "
                "publisher (ROADMAP P.5 / release.yml)."
            ),
        }
    if status == 200:
        version = None
        try:
            data = json.loads(body.decode("utf-8"))
            if isinstance(data, dict):
                info = data.get("info")
                if isinstance(info, dict):
                    version = info.get("version")
        except (UnicodeDecodeError, ValueError):
            version = None
        return {
            "project": project,
            "url": url,
            "http_status": 200,
            "published": True,
            "pypi_version": version,
            "probed": True,
            "error": None,
            "note": "Published on PyPI — still confirm trusted publisher + install path.",
        }
    return {
        "project": project,
        "url": url,
        "http_status": status,
        "published": None,
        "probed": True,
        "error": f"unexpected_http_status:{status}",
        "note": "Non-404/200 from PyPI — treat as unverifiable",
    }


def probe_public_host(
    public_url: str,
    *,
    http_get: HttpGet | None = None,
) -> dict[str, Any]:
    """Probe ``{public_url}/health`` when an operator set VERITAS_PUBLIC_URL."""
    get = http_get or _default_http_get
    base = public_url.strip().rstrip("/")
    if not base:
        return {
            "probed": False,
            "skipped": True,
            "reason": "VERITAS_PUBLIC_URL unset",
        }
    health = urljoin(base + "/", "health")
    try:
        status, body = get(health)
    except (OSError, urllib.error.URLError, ValueError) as exc:
        return {
            "probed": True,
            "url": health,
            "http_status": None,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "https": base.startswith("https://"),
        }

    ok = status == 200
    mode = None
    try:
        data = json.loads(body.decode("utf-8"))
        if isinstance(data, dict):
            mode = data.get("mode") or data.get("payment_mode")
    except (UnicodeDecodeError, ValueError):
        pass

    return {
        "probed": True,
        "url": health,
        "http_status": status,
        "ok": ok,
        "https": base.startswith("https://"),
        "health_mode": mode,
        "error": None if ok else f"health_status:{status}",
        "note": (
            "Host answered /health"
            if ok
            else "Public URL set but /health not OK — DNS/TLS/serve still human ops"
        ),
    }


def _stage1_agent_prep(
    *,
    surfaces: dict[str, bool],
    stage1: dict[str, Any],
    probes: dict[str, Any] | None,
) -> dict[str, Any]:
    """Agent-done prep vs human residues (VISION Stage-1 / REFOUNDING §4)."""
    agent_done = {
        "release_workflow_oidc": bool(surfaces.get("release_workflow")),
        "buyer_journey_cli": bool(surfaces.get("buyer_journey")),
        "existence_scorecard": bool(surfaces.get("existence_scorecard")),
        "money_loop": bool(surfaces.get("money_loop")),
        "dogfood_commerce": bool(surfaces.get("dogfood_commerce")),
        "verifier_entrypoint": bool(surfaces.get("verifier_entrypoint")),
        "chain_reconcile": bool(surfaces.get("chain_reconcile")),
    }
    human = list(STAGE1_HUMAN)
    pypi_probe = (probes or {}).get("pypi") if probes else None
    host_probe = (probes or {}).get("public_host") if probes else None

    human_status: dict[str, str] = {
        "pypi_trusted_publisher": "human_required",
        "public_tls_host": "human_required",
        "mainnet_pay_to": "human_required",
        "registry_listing": "human_required",
    }
    if isinstance(pypi_probe, dict) and pypi_probe.get("published") is True:
        human_status["pypi_trusted_publisher"] = (
            "package_visible_on_pypi — still confirm trusted publisher OIDC"
        )
    elif isinstance(pypi_probe, dict) and pypi_probe.get("published") is False:
        human_status["pypi_trusted_publisher"] = (
            "not_on_pypi — create project + trusted publisher (release.yml ready)"
        )

    if isinstance(host_probe, dict) and host_probe.get("ok") is True:
        human_status["public_tls_host"] = (
            "health_ok — still confirm DNS/public agents can reach it"
            if host_probe.get("https")
            else "health_ok_but_not_https — TLS still human"
        )
    elif stage1.get("env_hints", {}).get("VERITAS_PUBLIC_URL_https"):
        human_status["public_tls_host"] = "env_https_set — probe with --probe"

    if stage1.get("env_hints", {}).get("looks_mainnet_network") and stage1.get(
        "env_hints", {}
    ).get("VERITAS_PAY_TO_set"):
        human_status["mainnet_pay_to"] = (
            "env_mainnetish_pay_to — funding + first mainnet settle still human"
        )

    return {
        "vision_stage": "1_public_existence",
        "agent_prep_complete": all(agent_done.values()),
        "agent_done": agent_done,
        "human_residues": human,
        "human_status": human_status,
        "runbook_human_minutes": [
            {
                "id": "pypi_trusted_publisher",
                "action": (
                    f"Create PyPI project `{PYPI_PROJECT}` and configure this "
                    "repo's release.yml as a trusted publisher (OIDC)."
                ),
                "agent_ready": bool(surfaces.get("release_workflow")),
            },
            {
                "id": "public_tls_host",
                "action": (
                    "Point DNS + TLS at a host running veritas-server; set "
                    "VERITAS_PUBLIC_URL=https://… then re-run existence --probe."
                ),
                "agent_ready": True,
            },
            {
                "id": "mainnet_pay_to",
                "action": (
                    "Approve cold mainnet VERITAS_PAY_TO + network eip155:8453; "
                    "fund; first mainnet settle is human-owned."
                ),
                "agent_ready": bool(surfaces.get("money_loop")),
            },
            {
                "id": "registry_listing",
                "action": (
                    "List the public host on Bazaar/x402 registry so strangers "
                    "can discover without a private base URL."
                ),
                "agent_ready": True,
            },
        ],
        "not_publicly_existable_until": human,
    }


def _stage1_residues(
    *,
    pypi_published: bool | None = False,
) -> dict[str, Any]:
    """Env-visible residues only — never invent PyPI/TLS success."""
    public_url = (os.environ.get("VERITAS_PUBLIC_URL") or "").strip()
    pay_to = (os.environ.get("VERITAS_PAY_TO") or "").strip()
    network = (os.environ.get("VERITAS_NETWORK") or "").strip().lower()
    mainnetish = network in ("base", "eip155:8453", "8453")

    remaining = list(STAGE1_HUMAN)
    # Agents cannot clear these; we only note when env already points live.
    notes: list[str] = []
    if public_url.startswith("https://"):
        notes.append("VERITAS_PUBLIC_URL is https (TLS host may still need DNS)")
    if pay_to.startswith("0x") and mainnetish:
        notes.append("mainnet-ish pay-to env present — human still owns funding risk")

    return {
        "human_minutes_remaining": remaining,
        "env_hints": {
            "VERITAS_PUBLIC_URL_set": bool(public_url),
            "VERITAS_PUBLIC_URL_https": public_url.startswith("https://"),
            "VERITAS_PAY_TO_set": bool(pay_to),
            "VERITAS_NETWORK": network or None,
            "looks_mainnet_network": mainnetish,
            "VERITAS_PUBLIC_URL": public_url or None,
        },
        "notes": notes,
        # Default False offline; --probe may set True/None from measurement.
        "pypi_published": pypi_published if pypi_published is not None else False,
        "unsolicited_settlements": 0,
        "mainnet_settlements": 0,
    }


def build_existence_report(
    *,
    evidence_dir: Path | None = None,
    repo_root: Path | None = None,
    probe: bool = False,
    http_get: HttpGet | None = None,
) -> dict[str, Any]:
    root = repo_root or _repo_root()
    settlements = evidence_dir or (root / DEFAULT_SETTLEMENT_DIR)
    landmass = scan_settlement_evidence(settlements)
    surfaces = _agent_surfaces(root)

    probes: dict[str, Any] | None = None
    pypi_flag: bool | None = False
    if probe:
        public_url = (os.environ.get("VERITAS_PUBLIC_URL") or "").strip()
        pypi = probe_pypi(http_get=http_get)
        host = probe_public_host(public_url, http_get=http_get)
        probes = {"pypi": pypi, "public_host": host}
        pypi_flag = pypi.get("published")
        if pypi_flag is None:
            pypi_flag = False  # scorecard field is bool; detail lives under probes

    stage1 = _stage1_residues(pypi_published=bool(pypi_flag) if probe else False)
    if probe and probes and isinstance(probes.get("pypi"), dict):
        # Preserve measured null via probes; stage1 bool stays conservative.
        stage1["pypi_published"] = bool(probes["pypi"].get("published") is True)
        stage1["pypi_probe"] = probes["pypi"]
        stage1["public_host_probe"] = probes.get("public_host")

    prep = _stage1_agent_prep(surfaces=surfaces, stage1=stage1, probes=probes)

    publicly_existable = (
        stage1.get("pypi_published") is True
        and isinstance(probes, dict)
        and isinstance(probes.get("public_host"), dict)
        and probes["public_host"].get("ok") is True
        and probes["public_host"].get("https") is True
    )

    return {
        "schema": SCHEMA,
        "package_version": __version__,
        "landmass": {
            "testnet_settlements_confirmed": landmass[
                "testnet_settlements_confirmed"
            ],
            "mainnet_settlements": stage1["mainnet_settlements"],
            "unsolicited_settlements": stage1["unsolicited_settlements"],
            "transactions": landmass["transactions"],
            "evidence": {
                "dir": landmass["evidence_dir"],
                "files_scanned": landmass["files_scanned"],
                "incomplete_or_failed_runs": landmass["incomplete_or_failed_runs"],
                "unreadable": landmass["unreadable"],
                "by_file": landmass["by_file"],
            },
            "source": "on_disk_settlement_transcripts",
            "not_from_ledger_alone": True,
        },
        "stage1": stage1,
        "stage1_prep": prep,
        "probes": probes,
        "probe_ran": probe,
        "publicly_existable": publicly_existable,
        "agent_ready_surfaces": surfaces,
        "vision_path": {
            "stage0_rails": "done (live facilitator settle proven in evidence)",
            "stage1_public_existence": (
                "open — human residues + unsolicited=0"
                if not publicly_existable
                else "surfaces answering — still measure unsolicited demand"
            ),
            "stage2_substrate_product": "parked until stage1 falsifier window runs",
            "falsifier_stage1": (
                "90 days listed with zero unsolicited paid requests from any "
                "counterparty we did not build"
            ),
            "north_star": "VISION.md — A2A commerce substrate; Stage-1 is public existence",
        },
        "not_proven": [
            "unsolicited demand",
            "mainnet settlement",
            "PyPI publish" if not stage1.get("pypi_published") else "PyPI trusted-publisher OIDC",
            "public TLS production host"
            if not publicly_existable
            else "unsolicited traffic to public host",
            "commercial product-worth",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="veritas-existence",
        description=(
            "Stage-1 existence scorecard from on-disk settlement evidence. "
            "JSON on stdout. Never invents unsolicited or mainnet success. "
            "Pass --probe to measure PyPI + optional public /health."
        ),
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=None,
        help=f"Settlement transcript directory (default: {DEFAULT_SETTLEMENT_DIR})",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root for surface checks (default: package parent).",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help=(
            "Contact PyPI JSON API and, if VERITAS_PUBLIC_URL is set, "
            "GET {url}/health. Offline default is --probe off."
        ),
    )
    args = parser.parse_args(argv)
    report = build_existence_report(
        evidence_dir=args.evidence_dir,
        repo_root=args.repo_root,
        probe=bool(args.probe),
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
