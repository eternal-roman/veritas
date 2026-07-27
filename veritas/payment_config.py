"""Live / free payment configuration with full CAIP-2 support."""

from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Optional, List
import re

from .networks import normalize_network, DEFAULT_NETWORK, supported_networks, is_settleable

DEFAULT_FACILITATOR = "https://pay.openfacilitator.io"
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

EVM_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


@dataclass
class PaymentConfig:
    pay_to: str
    facilitator: str
    require_payment: bool
    network: str
    price: str
    mode: str
    supported_networks: List[str]
    config_errors: List[str] = None

    @classmethod
    def from_env(cls) -> "PaymentConfig":
        pay_to = os.getenv("VERITAS_PAY_TO", ZERO_ADDRESS).strip()
        facilitator = os.getenv("VERITAS_FACILITATOR", DEFAULT_FACILITATOR).strip()
        require = os.getenv("VERITAS_REQUIRE_PAYMENT", "false").lower() in ("1", "true", "yes")
        network = normalize_network(os.getenv("VERITAS_NETWORK", DEFAULT_NETWORK))
        price = os.getenv("VERITAS_PRICE", "$0.25").strip()

        # Validate before claiming live mode. The previous check accepted any
        # string of length >= 20 as a wallet, so a typo'd address would put the
        # service in live mode and settle payments to nowhere.
        errors: List[str] = []
        if require:
            if not EVM_ADDRESS_RE.match(pay_to):
                errors.append(f"VERITAS_PAY_TO is not a valid EVM address: {pay_to!r}")
            if not is_settleable(network):
                errors.append(f"no settlement asset configured for network {network!r}")
            if not facilitator.startswith(("http://", "https://")):
                errors.append(f"VERITAS_FACILITATOR is not a valid URL: {facilitator!r}")

        is_live = bool(require and not errors)
        mode = "live" if is_live else ("misconfigured" if require else "free")

        return cls(
            pay_to=pay_to if is_live else ZERO_ADDRESS,
            facilitator=facilitator,
            require_payment=is_live,
            network=network,
            price=price,
            mode=mode,
            supported_networks=supported_networks(),
            config_errors=errors,
        )

    def is_live_ready(self) -> bool:
        return self.mode == "live"

    def as_dict(self) -> dict:
        return {
            "mode": self.mode,
            "pay_to": self.pay_to,
            "facilitator": self.facilitator,
            "require_payment": self.require_payment,
            "network": self.network,
            "price": self.price,
            "live_ready": self.is_live_ready(),
            "supported_networks": self.supported_networks,
            "config_errors": self.config_errors or [],
        }

def get_payment_config() -> PaymentConfig:
    return PaymentConfig.from_env()
