"""Self-calibrator that improves from evaluation and call outcomes.

Maintains a simple frequency table of raw posterior -> observed correctness.
Can be updated automatically from harness runs or from online feedback.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Any
from collections import defaultdict

RUNTIME = Path(os.getenv("VERITAS_RUNTIME_DIR", ".veritas_runtime"))
STATE_PATH = RUNTIME / "calibrator_state.json"


class SelfCalibrator:
    # Observations required in a bin before its empirical rate replaces the
    # raw posterior. Below this, one or two samples would swing confidence wildly.
    MIN_OBSERVATIONS = 3

    def __init__(self, n_bins: int = 10):
        self.n_bins = n_bins
        self.bins: Dict[int, Dict[str, float]] = defaultdict(lambda: {"sum": 0.0, "count": 0.0})
        self._load()

    def _bin(self, p: float) -> int:
        p = max(0.0, min(1.0, p))
        return min(self.n_bins - 1, int(p * self.n_bins))

    def update(self, raw_posterior: float, observed: float) -> None:
        """observed is 1.0 for correct / useful, 0.0 for incorrect / refused correctly, etc."""
        b = self._bin(raw_posterior)
        self.bins[b]["sum"] += observed
        self.bins[b]["count"] += 1

    @property
    def is_trained(self) -> bool:
        """False while no bin has enough observations to adjust anything.

        Exposed so callers can report calibration as unavailable rather than
        presenting a pass-through value as though it were calibrated.
        """
        return any(stats["count"] >= self.MIN_OBSERVATIONS for stats in self.bins.values())

    def calibrate(self, raw_posterior: float) -> float:
        b = self._bin(raw_posterior)
        stats = self.bins.get(b)
        if not stats or stats["count"] < self.MIN_OBSERVATIONS:
            return raw_posterior  # not enough data; pass through unchanged
        return stats["sum"] / stats["count"]

    def save(self) -> None:
        RUNTIME.mkdir(parents=True, exist_ok=True)
        serializable = {str(k): v for k, v in self.bins.items()}
        STATE_PATH.write_text(json.dumps({"n_bins": self.n_bins, "bins": serializable}, indent=2))

    def _load(self) -> None:
        if not STATE_PATH.exists():
            return
        try:
            data = json.loads(STATE_PATH.read_text())
            self.n_bins = data.get("n_bins", 10)
            for k, v in data.get("bins", {}).items():
                self.bins[int(k)] = v
        except Exception:
            pass

    def summary(self) -> Dict[str, Any]:
        return {
            "n_bins": self.n_bins,
            "populated_bins": len([b for b in self.bins.values() if b["count"] > 0]),
            "total_updates": sum(b["count"] for b in self.bins.values()),
            "is_trained": self.is_trained,
            "status": "calibrated" if self.is_trained else "passthrough_untrained",
        }
