"""veritas-agent: the single zero-touch provisioning and serving command.

Before this CLI, `bootstrap_free_mode()` wrote a config file that only the
in-process control plane read — the HTTP server's `PaymentConfig.from_env`
never saw it, so "agent_start()" provisioned nothing the served surface
used. `veritas-agent up` closes that loop: bootstrap, wallet, env
application, serve.
"""

from __future__ import annotations

import json
import os

import pytest

from veritas.agent_cli import main
from veritas.autonomous.bootstrap import apply_to_env

PAYMENT_VARS = (
    "VERITAS_REQUIRE_PAYMENT", "VERITAS_PAY_TO", "VERITAS_NETWORK",
    "VERITAS_PRICE", "VERITAS_FACILITATOR",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    """apply_to_env writes os.environ directly (that is its job), so this
    fixture must restore the payment variables itself — monkeypatch only
    undoes its own changes."""
    for var in PAYMENT_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(tmp_path / "runtime"))
    yield tmp_path
    for var in PAYMENT_VARS:
        os.environ.pop(var, None)


def test_apply_to_env_maps_config_to_payment_env(monkeypatch):
    apply_to_env({
        "require_payment": True,
        "pay_to": "0x" + "1" * 40,
        "facilitator": "https://pay.example.org",
        "network": "eip155:84532",
        "price": "$0.10",
    })
    assert os.environ["VERITAS_REQUIRE_PAYMENT"] == "true"
    assert os.environ["VERITAS_PAY_TO"] == "0x" + "1" * 40
    assert os.environ["VERITAS_FACILITATOR"] == "https://pay.example.org"
    assert os.environ["VERITAS_NETWORK"] == "eip155:84532"
    assert os.environ["VERITAS_PRICE"] == "$0.10"


def test_apply_to_env_skips_absent_keys(monkeypatch):
    apply_to_env({"require_payment": False, "pay_to": None})
    assert os.environ["VERITAS_REQUIRE_PAYMENT"] == "false"
    assert "VERITAS_PAY_TO" not in os.environ
    assert "VERITAS_PRICE" not in os.environ


def test_init_bootstraps_config_and_wallet(tmp_path, capsys):
    pytest.importorskip("eth_account")
    assert main(["init"]) == 0
    config = json.loads((tmp_path / ".veritas_agent" / "config.json").read_text(encoding="utf-8"))
    assert config["mode"] == "free"
    assert config["pay_to"], "wallet address was not written into the config"
    assert config["pay_to"].startswith("0x")
    out = capsys.readouterr().out
    assert config["pay_to"] in out


def test_up_configures_server_from_bootstrap_config(tmp_path, monkeypatch):
    """The zero-touch command: init-if-missing, apply config to env, serve.
    The server entry point is stubbed; what matters is that the config the
    agent provisioned is what the server would boot with."""
    pytest.importorskip("eth_account")
    served = {}

    def fake_serve():
        from veritas.payment_config import get_payment_config
        served["config"] = get_payment_config()

    monkeypatch.setattr("veritas.server.main", fake_serve)
    assert main(["up"]) == 0
    assert served, "server entry point was not invoked"
    assert served["config"].mode == "free"


def test_free_default_never_requires_payment(tmp_path, monkeypatch):
    pytest.importorskip("eth_account")
    monkeypatch.setattr("veritas.server.main", lambda: None)
    assert main(["up"]) == 0
    assert os.environ.get("VERITAS_REQUIRE_PAYMENT") == "false"


def test_paid_flag_sets_pay_to_from_wallet(tmp_path, monkeypatch):
    """--paid flips require_payment and uses the provisioned wallet address;
    PaymentConfig validation then decides live vs misconfigured exactly as
    for any other deployment."""
    pytest.importorskip("eth_account")
    monkeypatch.setattr("veritas.server.main", lambda: None)
    assert main(["up", "--paid"]) == 0
    config = json.loads((tmp_path / ".veritas_agent" / "config.json").read_text(encoding="utf-8"))
    assert config["require_payment"] is True
    assert os.environ["VERITAS_PAY_TO"] == config["pay_to"]
    assert os.environ["VERITAS_REQUIRE_PAYMENT"] == "true"


def test_status_reports_config_and_wallet(tmp_path, capsys):
    pytest.importorskip("eth_account")
    main(["init"])
    assert main(["status"]) == 0
    out = capsys.readouterr().out
    assert "free" in out
    assert "0x" in out


def test_status_includes_stage1_readiness_scorecard(tmp_path, capsys):
    """PS9: seller status surfaces Stage-1 readiness in-process (measure only)."""
    pytest.importorskip("eth_account")
    main(["init"])
    capsys.readouterr()  # drop init chatter
    assert main(["status"]) == 0
    payload = json.loads(capsys.readouterr().out)
    readiness = payload["stage1_readiness"]
    assert readiness["schema"] == "veritas.existence.v1"
    assert readiness["publicly_existable"] is False
    assert readiness["probe_ran"] is False
    assert "human_minutes_remaining" in readiness
    assert "unsolicited demand" in readiness["not_proven"]
    assert readiness["testnet_settlements_confirmed"] is not None
    assert readiness["stage1_prep"]["vision_stage"] == "1_public_existence"
