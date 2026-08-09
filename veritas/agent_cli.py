"""veritas-agent: zero-touch provisioning and serving for an agent operator.

One command takes a fresh install to a running, self-described service:

    veritas-agent up            # bootstrap config + wallet, then serve
    veritas-agent up --paid     # same, requiring payment to the agent's wallet

`init` provisions without serving; `serve` serves an existing config;
`status` prints what is provisioned. Free mode stays the default: paid mode
additionally needs a funded counterparty and a reachable facilitator, and
`PaymentConfig.from_env` validation decides live vs misconfigured exactly as
for any other deployment. What still requires a human is unchanged and
stated: funding the wallet and public (TLS) deployment.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from veritas.autonomous.bootstrap import apply_to_env, bootstrap_free_mode, load_config
from veritas.networks import DEFAULT_NETWORK, is_testnet, normalize_network

CONFIG_NAME = "config.json"


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
    _write_config(base_dir, config)
    print(f"config: {Path(base_dir) / CONFIG_NAME}")
    print(wallet_note)
    print(f"mode requested: {'paid' if paid else 'free'}")
    return config


def _serve(base_dir: str) -> None:
    config = load_config(base_dir)
    apply_to_env(config)

    import veritas.server

    veritas.server.main()


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

    init_p = sub.add_parser("init", help="provision config and wallet, do not serve")
    _payment_flags(init_p)
    sub.add_parser("serve", help="apply provisioned config to env and run the server")
    up_p = sub.add_parser("up", help="init if missing, then serve (the zero-touch path)")
    _payment_flags(up_p)
    sub.add_parser("status", help="print provisioned config and wallet state")

    args = parser.parse_args(argv)

    if args.command == "init":
        _provision(args.base_dir, paid=args.paid, network=args.network,
                   acknowledged_real_money=args.acknowledged_real_money)
        return 0

    if args.command == "up":
        _provision(args.base_dir, paid=args.paid, network=args.network,
                   acknowledged_real_money=args.acknowledged_real_money)
        _serve(args.base_dir)
        return 0

    if args.command == "serve":
        _serve(args.base_dir)
        return 0

    if args.command == "status":
        config = load_config(args.base_dir)
        from veritas.autonomous.wallet import wallet_address
        from veritas.existence import build_existence_report

        try:
            address = wallet_address(args.base_dir)
        except ValueError:
            address = None

        # Stage-1 readiness in-process (PS9): never invent public existence.
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
            "vision_path": existence.get("vision_path"),
            "not_proven": existence.get("not_proven"),
            "publicly_existable": False,  # honest until human residues clear
            "note": (
                "Stage-1 public existence remains human-gated "
                "(PyPI / TLS / mainnet / registry). Measure only — "
                "require_payment on localhost is not live to agents."
            ),
        }
        print(json.dumps({
            "mode": config.get("mode"),
            "require_payment": config.get("require_payment"),
            "pay_to": config.get("pay_to"),
            "wallet": address or "not provisioned",
            "config_path": str(Path(args.base_dir) / CONFIG_NAME),
            "stage1_readiness": stage1_readiness,
        }, indent=2))
        return 0

    return 2  # pragma: no cover - argparse enforces the command set


if __name__ == "__main__":
    raise SystemExit(main())
