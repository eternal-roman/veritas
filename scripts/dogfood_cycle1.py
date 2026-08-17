"""Dogfood cycle 1 — cold autonomous install / first-boot after the package is available.

Cycle 1 was gated on Phase N0 (evidence notary). N0–N1.3 are on main, so this
cycle can now ask: *can an autonomous agent adopt the product without a human
editing config, and does the install contract expose the surfaces that agent
needs?*

What is measured (no outbound network):

    entry_points          console scripts the install contract must expose
    free_bootstrap        veritas-agent init-style free-mode config + runtime dir
    free_server_surfaces  health, discovery, identity, schema after bootstrap
    offline_catalog       SignalStore persist + list works offline
    notary_offline        observe with injected fetch → evidence_pack present
    pack_verify           free POST /v1/packs/verify accepts the pack
    one_top_level_package installable distribution has exactly one top-level package

Honest boundary: this cycle does **not** re-run a blank-machine ``pip install``
from the public index (CI's package job already builds and installs the wheel
with hash-pinned deps). It is the *first-boot agent path* against a tree that
is already installable — the gap cycle 1 was meant to close after N0.

Run: ``python -m scripts.dogfood_cycle1`` (or ``python scripts/dogfood_cycle1.py``).
Exits non-zero if any check fails. Writes JSON when ``--out`` is set.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

REQUIRED_SCRIPTS = (
    "veritas-server",
    "veritas-agent",
    "veritas-mcp",
    "veritas-ops",
    "veritas-verify",
)

REQUIRED_MODULES = (
    "veritas.signals",
    "veritas.server",
    "veritas.notary.observe",
    "veritas.notary.pack",
    "veritas.notary.refetch",
    "veritas.notary.sign",
    "veritas.credits",
    "veritas.siwx",
)


def _check(name: str, expected: str, observed: str, ok: bool, **extra: Any) -> dict[str, Any]:
    return {
        "check": name,
        "expected": expected,
        "observed": observed,
        "pass": ok,
        **extra,
    }


def check_entry_points() -> dict[str, Any]:
    """Install contract (pyproject [project.scripts]) must expose agent CLIs.

    pyproject is the install contract a cold agent depends on. Installed
    metadata may lag a dirty local editable tree; CI installs fresh so both
    align. This check is load-bearing on the declared contract.
    """
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    # Narrow to [project.scripts] … next [
    start = text.find("[project.scripts]")
    if start < 0:
        return _check(
            "entry_points",
            f"console scripts {list(REQUIRED_SCRIPTS)} in pyproject",
            "missing [project.scripts] table",
            False,
            source="pyproject",
        )
    block = text[start:].split("\n[", 1)[0]
    found = []
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        name = line.split("=", 1)[0].strip()
        if name in REQUIRED_SCRIPTS:
            found.append(name)
    missing = [s for s in REQUIRED_SCRIPTS if s not in found]
    # Informational: installed distribution entry points (not fail-closed).
    installed_missing: list[str] | None = None
    try:
        dist = importlib.metadata.distribution("veritas-research")
        eps = {ep.name for ep in dist.entry_points if ep.group == "console_scripts"}
        installed_missing = [s for s in REQUIRED_SCRIPTS if s not in eps]
    except importlib.metadata.PackageNotFoundError:
        installed_missing = None
    return _check(
        "entry_points",
        f"console scripts {list(REQUIRED_SCRIPTS)} declared in pyproject",
        f"pyproject_present={sorted(found)}; missing={missing}; "
        f"installed_metadata_missing={installed_missing}",
        not missing,
        source="pyproject",
    )


def check_required_modules() -> dict[str, Any]:
    failed: list[str] = []
    for mod in REQUIRED_MODULES:
        try:
            importlib.import_module(mod)
        except Exception as exc:  # noqa: BLE001 — report type only
            failed.append(f"{mod}:{type(exc).__name__}")
    return _check(
        "required_modules",
        "N0–N1.3 product modules import",
        f"failed={failed}" if failed else f"imported {len(REQUIRED_MODULES)} modules",
        not failed,
    )


def check_one_top_level_package() -> dict[str, Any]:
    """Wheel must ship exactly one top-level package (CI package job invariant)."""
    pkg = REPO / "veritas"
    siblings = [
        p.name
        for p in REPO.iterdir()
        if p.is_dir()
        and (p / "__init__.py").is_file()
        and p.name not in {"tests", "scripts", "docs"}
        and not p.name.startswith(".")
        and p.name != "veritas"
    ]
    ok = pkg.is_dir() and (pkg / "__init__.py").is_file() and not siblings
    return _check(
        "one_top_level_package",
        "exactly one installable top-level package: veritas",
        f"veritas_present={pkg.is_dir()}; extra_top_level={siblings}",
        ok,
    )


def check_free_bootstrap(tmp: Path) -> dict[str, Any]:
    """Empty dir → free-mode config an agent can serve from (no human edits)."""
    agent_dir = tmp / ".veritas_agent"
    runtime = tmp / "runtime"
    runtime.mkdir(parents=True)
    os.environ["VERITAS_RUNTIME_DIR"] = str(runtime)
    os.environ.pop("VERITAS_REQUIRE_PAYMENT", None)
    os.environ.pop("VERITAS_PAY_TO", None)

    from veritas.agent_cli import main

    # init may provision wallet when signing extra is present.
    code = main(["init"])
    config_path = agent_dir / "config.json"
    if not config_path.is_file():
        # Some environments run init from cwd; agent_cli uses cwd for .veritas_agent
        config_path = Path.cwd() / ".veritas_agent" / "config.json"
    ok = code == 0 and config_path.is_file()
    mode = None
    if config_path.is_file():
        mode = json.loads(config_path.read_text(encoding="utf-8")).get("mode")
        ok = ok and mode == "free"
    return _check(
        "free_bootstrap",
        "veritas-agent init produces free-mode config without payment env",
        f"exit={code}, config={config_path.is_file()}, mode={mode}",
        ok,
    )


def check_free_server_surfaces(tmp: Path) -> dict[str, Any]:
    from fastapi.testclient import TestClient

    os.environ["VERITAS_RUNTIME_DIR"] = str(tmp / "srv")
    os.environ.pop("VERITAS_REQUIRE_PAYMENT", None)
    os.environ.pop("VERITAS_PUBLIC_URL", None)
    import veritas.server as server

    importlib.reload(server)
    client = TestClient(server.app, raise_server_exceptions=False)

    health = client.get("/health")
    wk = client.get("/.well-known/x402")
    identity = client.get("/v1/identity")
    schema = client.get("/v1/schema")
    links = wk.json().get("links", {}) if wk.status_code == 200 else {}
    required_links = (
        "identity",
        "notarize",
        "attestations_verify",
        "packs_verify",
        "schema",
    )
    missing = [k for k in required_links if k not in links]
    ok = (
        health.status_code == 200
        and health.json().get("payment_mode") == "free"
        and wk.status_code == 200
        and identity.status_code == 200
        and schema.status_code == 200
        and not missing
    )
    return _check(
        "free_server_surfaces",
        "free-mode health + discovery reaches notarize/attest/pack surfaces",
        (
            f"health={health.status_code}/{health.json().get('payment_mode')}, "
            f"wk={wk.status_code}, identity={identity.status_code}, "
            f"schema={schema.status_code}, missing_links={missing}"
        ),
        ok,
    )


def check_offline_catalog(tmp: Path) -> dict[str, Any]:
    os.environ["VERITAS_RUNTIME_DIR"] = str(tmp / "catalog")
    from veritas.signals import METHOD, SignalStore

    store = SignalStore(tmp / "catalog")
    digest = store.put({
        "venue": "polymarket",
        "market_id": "m-cycle1",
        "question": "cycle1 fixture",
        "outcomes": [{"name": "Yes", "price": 0.5}],
        "observed_at": "2026-08-17T00:00:00Z",
        "source_url": "https://gamma-api.polymarket.com/markets/m-cycle1",
        "method": METHOD,
        "note": "market-implied prices, not a verdict",
    })
    listed = store.list()
    ok = bool(digest) and any(item.get("market_id") == "m-cycle1" for item in listed)
    return _check(
        "offline_catalog",
        "SignalStore persist + list works offline",
        f"digest={digest}, n={len(listed)}",
        ok,
    )


def check_notary_and_pack(tmp: Path) -> dict[str, Any]:
    from fastapi.testclient import TestClient

    from veritas.hashing import compute_content_hash
    from veritas.notary.fetch import FetchResult
    from veritas.notary.observe import observe

    body = b"Cycle-1 cold-install notary body."
    expected_hash = compute_content_hash(body.decode("utf-8"))

    def fake_fetch(url, **kwargs):
        return FetchResult(
            request_url=url,
            final_url=url,
            status=200,
            headers={"content-type": "text/plain"},
            body=body,
            truncated=False,
        )

    observation = observe(
        "https://example.org/cycle1",
        request_id="cycle1-notary",
        robots_body="User-agent: *\nAllow: /\n",
        fetch_fn=fake_fetch,
        observed_at="2026-08-08T20:00:00Z",
    )
    pack = observation.get("evidence_pack")
    has_pack = isinstance(pack, dict) and pack.get("pack_hash", "").startswith("sha256:")
    hash_ok = (observation.get("evidence_record") or {}).get("content_hash") == expected_hash

    os.environ["VERITAS_RUNTIME_DIR"] = str(tmp / "pack")
    import veritas.server as server

    importlib.reload(server)
    client = TestClient(server.app, raise_server_exceptions=False)
    verify = client.post("/v1/packs/verify", json={"pack": pack or {}})
    verify_ok = verify.status_code == 200 and verify.json().get("valid") is True

    ok = (
        observation.get("status") == "completed"
        and has_pack
        and hash_ok
        and verify_ok
    )
    return _check(
        "notary_and_pack",
        "offline observe completes with evidence_pack; packs/verify accepts it",
        (
            f"status={observation.get('status')}, has_pack={has_pack}, "
            f"hash_ok={hash_ok}, verify={verify.status_code}/"
            f"{verify.json().get('valid') if verify.status_code == 200 else None}"
        ),
        ok,
    )


def run() -> dict[str, Any]:
    """Execute every cycle-1 check; return a JSON-serialisable report."""
    with tempfile.TemporaryDirectory(prefix="veritas-cycle1-") as tmp_name:
        tmp = Path(tmp_name)
        # agent init uses cwd for .veritas_agent
        prev = Path.cwd()
        try:
            os.chdir(tmp)
            checks = [
                check_entry_points(),
                check_required_modules(),
                check_one_top_level_package(),
                check_free_bootstrap(tmp / "boot"),
                check_free_server_surfaces(tmp / "srv"),
                check_offline_catalog(tmp / "res"),
                check_notary_and_pack(tmp / "notary"),
            ]
        finally:
            os.chdir(prev)

    passed = sum(1 for c in checks if c["pass"])
    return {
        "cycle": 1,
        "perspective": "cold autonomous install / first-boot",
        "network": "none — no outbound sockets; offline corpus and injected fetch only",
        "boundary": (
            "Does not re-run blank-machine pip install from PyPI; CI package job "
            "owns wheel install. This cycle is first-boot agent surfaces after "
            "the package is available (post N0–N1.3)."
        ),
        "on_chain_settlements": 0,
        "checks": checks,
        "passed": passed,
        "total": len(checks),
        "all_pass": passed == len(checks),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dogfood cycle 1 — cold install first-boot")
    parser.add_argument("--out", type=Path, default=None, help="Write JSON report here")
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
