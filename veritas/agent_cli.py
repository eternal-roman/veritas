"""veritas-agent: plugin-and-play account, wallet, skills, and serving.

    veritas-agent enroll --id <name> --interests research,buy,verify
    veritas-agent whoami
    veritas-agent up            # sell path (enrolls a default account if needed)
    veritas-buy <seller-url>    # buy path
    veritas-mcp                 # local free-mode tools

`init`/`up` enroll automatically. Funding the wallet and public TLS remain
external. Paid mode still needs --paid and, on mainnet, an explicit ack.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from veritas.agent_account import (
    catalog_document,
    enroll_account,
    load_account,
    record_funding,
    whoami_document,
)
from veritas.autonomous.bootstrap import apply_to_env, bootstrap_free_mode, load_config
from veritas.networks import DEFAULT_NETWORK, is_testnet, normalize_network

CONFIG_NAME = "config.json"
TLS_CERT_NAME = "cert.pem"
TLS_KEY_NAME = "key.pem"


def _tls_paths(base_dir: str) -> tuple[Path, Path]:
    tls_dir = Path(base_dir) / "tls"
    return tls_dir / TLS_CERT_NAME, tls_dir / TLS_KEY_NAME


def _env_tls_files() -> tuple[str, str] | None:
    cert = (os.environ.get("VERITAS_TLS_CERT") or "").strip()
    key = (os.environ.get("VERITAS_TLS_KEY") or "").strip()
    if cert and key:
        return cert, key
    return None


def _issue_tls_material(base_dir: str, cert: Path, key: Path) -> bool:
    """Ask ``veritas.peer_tls`` to write material if that module is present."""
    try:
        from veritas.peer_tls import issue_tls_material
    except ImportError:
        return False
    tls_dir = cert.parent
    try:
        issued = issue_tls_material(tls_dir)
    except TypeError:
        issued = issue_tls_material(base_dir)
    if isinstance(issued, (tuple, list)) and len(issued) >= 2:
        return Path(issued[0]).is_file() and Path(issued[1]).is_file()
    return cert.is_file() and key.is_file()


def _apply_tls(base_dir: str, *, want_tls: bool) -> None:
    """Resolve TLS files into ``VERITAS_TLS_CERT`` / ``VERITAS_TLS_KEY``.

    Env wins. ``--tls`` looks under ``{base-dir}/tls/{cert,key}.pem`` when
    env is unset. Missing files: call ``issue_tls_material`` if
    ``veritas.peer_tls`` is importable; otherwise exit 1.
    """
    if _env_tls_files() is not None:
        return
    if not want_tls:
        return
    cert, key = _tls_paths(base_dir)
    if not (cert.is_file() and key.is_file()):
        if not _issue_tls_material(base_dir, cert, key):
            raise SystemExit(
                "TLS requested (--tls) but no certificate files found. "
                "Set VERITAS_TLS_CERT and VERITAS_TLS_KEY to PEM paths, or "
                f"place {TLS_CERT_NAME} and {TLS_KEY_NAME} under "
                f"{Path(base_dir) / 'tls'}/. This build does not generate "
                "certificates (veritas.peer_tls is unavailable)."
            )
    if not (cert.is_file() and key.is_file()):
        raise SystemExit(
            "TLS requested (--tls) but issue_tls_material did not write "
            f"{cert} and {key}"
        )
    os.environ["VERITAS_TLS_CERT"] = str(cert.resolve())
    os.environ["VERITAS_TLS_KEY"] = str(key.resolve())


def _write_config(base_dir: str, config: dict[str, Any]) -> None:
    (Path(base_dir) / CONFIG_NAME).write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )


def _provision(
    base_dir: str,
    paid: bool,
    network: str | None = None,
    acknowledged_real_money: bool = False,
) -> dict[str, Any]:
    """Bootstrap config and, when signing support is installed, a wallet."""
    config_path = Path(base_dir) / CONFIG_NAME
    config = load_config(base_dir) if config_path.exists() else bootstrap_free_mode(base_dir=base_dir)

    wallet_note = "wallet: not provisioned (install the 'signing' extra to enable)"
    try:
        from veritas.autonomous.wallet import ensure_wallet

        info = ensure_wallet(base_dir=base_dir)
        config["pay_to"] = info.address
        wallet_note = f"wallet: {info.address} ({'created' if info.created else 'existing'})"
    except ValueError as exc:  # WalletError, or eth_account absent
        if paid:
            raise
        wallet_note = f"wallet: not provisioned ({exc})"

    if network:
        config["network"] = normalize_network(network)

    if paid:
        target = config.get("network") or DEFAULT_NETWORK
        # Reaching mainnet moves real money. It used to be the default, so a
        # single `--paid` put a freshly generated, unfunded keystore into live
        # operation. Now it has to be said out loud.
        if not is_testnet(target) and not acknowledged_real_money:
            raise SystemExit(
                f"refusing to enable payment on {target}, which settles real "
                "funds. Re-run with --i-understand-this-is-real-money, or pass "
                "--network eip155:84532 for Base Sepolia."
            )
        config["require_payment"] = True
    config["notes_cli"] = (
        "Provisioned by veritas-agent. Funding the wallet and public TLS "
        "deployment remain external steps."
    )
    account = enroll_account(
        base_dir,
        agent_id=config.get("agent_id"),
        commerce_address=config.get("pay_to"),
    )
    config["agent_id"] = account["agent_id"]
    config["did"] = account["did"]
    _write_config(base_dir, config)
    # JSON on stdout, like every sibling CLI: the first consumer is an agent.
    print(json.dumps({
        "config_path": str(Path(base_dir) / CONFIG_NAME),
        "wallet": wallet_note,
        "mode_requested": "paid" if paid else "free",
        "account": {
            "agent_id": account["agent_id"],
            "did": account["did"],
            "skills": [s["id"] for s in account["skills"]],
            "binding_hash": account["binding_hash"],
        },
        "note": "funding the wallet and public TLS deployment remain external",
    }, indent=2))
    return config


def _serve(base_dir: str, want_tls: bool = False) -> None:
    config = load_config(base_dir)
    apply_to_env(config, base_dir=base_dir)
    _apply_tls(base_dir, want_tls=want_tls)

    import veritas.server

    # Empty argv: the server must not re-parse veritas-agent's own arguments.
    veritas.server.main([])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="veritas-agent", description=__doc__)
    parser.add_argument("--base-dir", default=".veritas_agent")
    sub = parser.add_subparsers(dest="command", required=True)
    def _payment_flags(sub_parser):
        sub_parser.add_argument("--paid", action="store_true")
        sub_parser.add_argument(
            "--network", default=None,
            help="CAIP-2 network id (default: Base Sepolia testnet)",
        )
        sub_parser.add_argument(
            "--i-understand-this-is-real-money", action="store_true",
            dest="acknowledged_real_money",
            help="required to enable payment on a mainnet network",
        )

    init_p = sub.add_parser("init", help="provision config, wallet, and account; do not serve")
    _payment_flags(init_p)
    serve_p = sub.add_parser("serve", help="apply provisioned config to env and run the server")
    serve_p.add_argument(
        "--tls",
        action="store_true",
        help=(
            "Terminate TLS from VERITAS_TLS_CERT / VERITAS_TLS_KEY, or "
            "{base-dir}/tls/cert.pem and key.pem if env is unset"
        ),
    )
    up_p = sub.add_parser("up", help="init if missing, then serve (the zero-touch path)")
    _payment_flags(up_p)
    up_p.add_argument(
        "--tls",
        action="store_true",
        help=(
            "Terminate TLS from VERITAS_TLS_CERT / VERITAS_TLS_KEY, or "
            "{base-dir}/tls/cert.pem and key.pem if env is unset"
        ),
    )
    sub.add_parser("status", help="print provisioned config, wallet, and account")

    enroll_p = sub.add_parser(
        "enroll",
        help="create identity + wallets + interest-bound skills (no server)",
    )
    enroll_p.add_argument("--id", dest="agent_id", default=None, help="agent id (default: self)")
    enroll_p.add_argument("--role", default=None, help="plane role (default: agent)")
    enroll_p.add_argument(
        "--interests",
        default=None,
        help="comma-separated interests mapped onto catalog skills "
        "(default: research,verify)",
    )
    sub.add_parser("whoami", help="print the enrolled account, or how to enroll")
    sub.add_parser("skills", help="print bound skills, or the catalog if not enrolled")
    adopt_p = sub.add_parser(
        "adopt",
        help="enroll + sign did:pkh card (does not faucet; --tx optional)",
    )
    adopt_p.add_argument("--id", dest="agent_id", default=None)
    adopt_p.add_argument("--role", default=None)
    adopt_p.add_argument("--interests", default=None)
    adopt_p.add_argument(
        "--tx",
        dest="tx_hash",
        default=None,
        help="optional USDC funding tx to check",
    )
    fund_p = sub.add_parser(
        "fund-proof",
        help="observe USDC Transfer custody for the commerce wallet (not a faucet)",
    )
    fund_p.add_argument("--tx", dest="tx_hash", default=None)

    connect_p = sub.add_parser(
        "connect",
        help="fetch another agent's peer card into the local book (no central network)",
    )
    connect_p.add_argument("url", help="base URL of the other self-hosted agent")
    connect_p.add_argument(
        "--allow-local",
        action="store_true",
        help="permit loopback and RFC1918; never permits cloud metadata IPs",
    )
    sub.add_parser(
        "peers",
        help="list the local peer book as JSON (never published over HTTP)",
    )
    pull_p = sub.add_parser(
        "pull-signals",
        help="GET another agent's /v1/signals and store snapshots locally",
    )
    pull_p.add_argument("peer", help="peer_id from the local book, or a base URL")
    pull_p.add_argument(
        "--query",
        default=None,
        help="optional query string forwarded to GET /v1/signals",
    )
    pull_p.add_argument(
        "--allow-local",
        action="store_true",
        help="permit loopback and RFC1918; never permits cloud metadata IPs",
    )
    sub.add_parser(
        "browse",
        help="mDNS browse for LAN peer card URLs (no-op without zeroconf extra)",
    )
    sub.add_parser(
        "introductions",
        help="print signed public-URL introductions from the local book (empty without a signer)",
    )

    args = parser.parse_args(argv)
    args.base_dir = str(Path(args.base_dir).expanduser().resolve())

    if args.command == "enroll":
        account = enroll_account(
            args.base_dir,
            agent_id=args.agent_id,
            role=args.role,
            interests=args.interests,
        )
        print(json.dumps(account, indent=2))
        return 0

    if args.command == "adopt":
        enroll_account(
            args.base_dir,
            agent_id=args.agent_id,
            role=args.role,
            interests=args.interests,
        )
        if args.tx_hash:
            acc = load_account(args.base_dir)
            addr = (acc or {}).get("wallets", {}).get("commerce", {}).get("address")
            if addr:
                from veritas.funding_proof import prove_funding

                record_funding(
                    args.base_dir, prove_funding(addr, tx_hash=args.tx_hash)
                )
        print(json.dumps(whoami_document(args.base_dir), indent=2))
        return 0

    if args.command == "fund-proof":
        acc = load_account(args.base_dir)
        if acc is None:
            print(json.dumps(whoami_document(args.base_dir), indent=2))
            return 1
        addr = (acc.get("wallets") or {}).get("commerce", {}).get("address")
        if not addr:
            print(json.dumps({"error": "no commerce address", **whoami_document(args.base_dir)}, indent=2))
            return 1
        from veritas.funding_proof import prove_funding

        proof = prove_funding(addr, tx_hash=args.tx_hash)
        record_funding(args.base_dir, proof)
        print(json.dumps({**whoami_document(args.base_dir), "funding_proof": proof}, indent=2))
        return 0

    if args.command == "whoami":
        print(json.dumps(whoami_document(args.base_dir), indent=2))
        return 0

    if args.command == "skills":
        acc = load_account(args.base_dir)
        if acc is None:
            print(json.dumps({"enrolled": False, **catalog_document()}, indent=2))
        else:
            print(json.dumps({
                "enrolled": True,
                "agent_id": acc["agent_id"],
                "did": acc["did"],
                "commerce_address": acc.get("wallets", {}).get("commerce", {}).get("address"),
                "skills": acc["skills"],
                "binding_hash": acc["binding_hash"],
            }, indent=2))
        return 0

    if args.command == "connect":
        from veritas.peer import connect as connect_peer

        result = connect_peer(
            args.url, allow_local=args.allow_local, base_dir=args.base_dir
        )
        print(json.dumps(result, indent=2))
        if result.get("ok"):
            return 0
        return 2 if result.get("code") == "unreachable" else 1

    if args.command == "peers":
        from veritas.peer import list_peers

        print(json.dumps(list_peers(args.base_dir), indent=2))
        return 0

    if args.command == "pull-signals":
        from veritas.peer import pull_signals as pull_peer_signals

        result = pull_peer_signals(
            args.peer,
            query=args.query,
            allow_local=args.allow_local,
            base_dir=args.base_dir,
        )
        print(json.dumps(result, indent=2))
        if result.get("ok"):
            return 0
        return 2 if result.get("code") == "unreachable" else 1

    if args.command == "browse":
        from veritas.peer_mdns import browse

        result = browse()
        print(json.dumps(result, indent=2))
        if isinstance(result, list):
            return 0
        return 0 if result.get("unavailable") else 1

    if args.command == "introductions":
        from veritas.peer import load_peers
        from veritas.peer_intro import DEFAULT_LIMIT, public_introductions

        items = public_introductions(load_peers(args.base_dir), limit=DEFAULT_LIMIT)
        print(json.dumps({
            "schema": "veritas.peer.introductions.v1",
            "items": items,
            "count": len(items),
            "cap": DEFAULT_LIMIT,
            "central_network": False,
            "note": "public-URL only; empty without a commerce signer",
        }, indent=2))
        return 0

    if args.command == "init":
        _provision(args.base_dir, paid=args.paid, network=args.network,
                   acknowledged_real_money=args.acknowledged_real_money)
        return 0

    if args.command == "up":
        _provision(args.base_dir, paid=args.paid, network=args.network,
                   acknowledged_real_money=args.acknowledged_real_money)
        _serve(args.base_dir, want_tls=args.tls)
        return 0

    if args.command == "serve":
        _serve(args.base_dir, want_tls=args.tls)
        return 0

    if args.command == "status":
        config = load_config(args.base_dir)
        from veritas.autonomous.wallet import wallet_address
        from veritas.existence import build_existence_report

        try:
            address = wallet_address(args.base_dir)
        except ValueError:
            address = None

        # Stage-1 readiness in-process (PS9 + vision Stage-1): never invent
        # public existence. Offline by default; operators run
        # `veritas-ops existence --probe` for PyPI / public /health.
        existence = build_existence_report()
        stage1 = existence.get("stage1") or {}
        landmass = existence.get("landmass") or {}
        stage1_readiness = {
            "schema": existence.get("schema"),
            "package_version": existence.get("package_version"),
            "testnet_settlements_confirmed": landmass.get(
                "testnet_settlements_confirmed"
            ),
            "mainnet_settlements": landmass.get("mainnet_settlements"),
            "unsolicited_settlements": landmass.get("unsolicited_settlements"),
            "human_minutes_remaining": stage1.get("human_minutes_remaining"),
            "env_hints": stage1.get("env_hints"),
            "stage1_prep": existence.get("stage1_prep"),
            "vision_path": existence.get("vision_path"),
            "not_proven": existence.get("not_proven"),
            "publicly_existable": bool(existence.get("publicly_existable")),
            "probe_ran": bool(existence.get("probe_ran")),
            "note": (
                "Stage-1 public existence remains human-gated "
                "(PyPI / TLS / mainnet / registry). Offline status does not "
                "probe the network — use `veritas-ops existence --probe`."
            ),
        }
        print(json.dumps({
            "mode": config.get("mode"),
            "require_payment": config.get("require_payment"),
            "pay_to": config.get("pay_to"),
            "wallet": address or "not provisioned",
            "config_path": str(Path(args.base_dir) / CONFIG_NAME),
            "account": whoami_document(args.base_dir),
            "stage1_readiness": stage1_readiness,
        }, indent=2))
        return 0

    return 2  # pragma: no cover - argparse enforces the command set


if __name__ == "__main__":
    raise SystemExit(main())
