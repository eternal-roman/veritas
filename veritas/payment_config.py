"""Live / free payment configuration for Veritas.

Environment variables (live mode):
  VERITAS_PAY_TO          = 0xYourReceivingWallet
  VERITAS_FACILITATOR     = https://pay.openfacilitator.io   (or CDP / self-hosted)
  VERITAS_REQUIRE_PAYMENT = true
  VERITAS_NETWORK         = eip155:8453          (Base mainnet)
  VERITAS_PRICE           = $0.25

If VERITAS_REQUIRE_PAYMENT is not true or PAY_TO is missing/zero,
the service stays in free/simulated mode.
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Optional

DEFAULT_FACILITATOR = "https://pay.openfacilitator.io"
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

@dataclass
class PaymentConfig:
    pay_to: str
    facilitator: str
    require_payment: bool
    network: str
    price: str
    mode: str  # "free" | "live"

    @classmethod
    def from_env(cls) -> "PaymentConfig":
        pay_to = os.getenv("VERITAS_PAY_TO", ZERO_ADDRESS).strip()
        facilitator = os.getenv("VERITAS_FACILITATOR", DEFAULT_FACILITATOR).strip()
        require = os.getenv("VERITAS_REQUIRE_PAYMENT", "false").lower() in ("1", "true", "yes")
        network = os.getenv("VERITAS_NETWORK", "eip155:8453").strip()
        price = os.getenv("VERITAS_PRICE", "$0.25").strip()

        is_live = require and pay_to and pay_to != ZERO_ADDRESS and len(pay_to) == 42
        mode = "live" if is_live else "free"

        return cls(
            pay_to=pay_to if is_live else ZERO_ADDRESS,
            facilitator=facilitator,
            require_payment=is_live,
            network=network,
            price=price,
            mode=mode,
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
        }

def get_payment_config() -> PaymentConfig:
    return PaymentConfig.from_env()
