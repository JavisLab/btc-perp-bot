import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..core import BotError, number

HOUR = 3_600_000
DAY = 24 * HOUR
PRESETS = ("trend", "breakout", "mean_reversion")
BENCHMARKS = ("cash", "buy_hold")
ALL_STRATEGIES = PRESETS + BENCHMARKS
WARMUP = 61
MODEL_VERSION = "research-v1"


@dataclass(frozen=True)
class Config:
    cash: str = "1000"
    exposure: str = "0.5"
    fee_bps: str = "4.5"
    half_spread_bps: str = "0.5"
    slippage_bps: str = "1"
    max_drawdown: str = "0.20"
    train_fraction: str = "0.70"
    max_book_slippage_bps: str = "10"

    def __post_init__(self):
        for key, value in asdict(self).items():
            number(value)
        if number(self.cash) < 20 or not 0 < number(self.exposure) <= 1:
            raise BotError("Require virtual cash >= 20 and entry exposure in (0, 1]")
        if not 0 < number(self.max_drawdown) < 1 or not 0.5 <= number(self.train_fraction) <= 0.85:
            raise BotError("Invalid drawdown stop or training fraction")
        for key in ("fee_bps", "half_spread_bps", "slippage_bps", "max_book_slippage_bps"):
            if not 0 <= number(getattr(self, key)) <= 1000:
                raise BotError("Cost/price tolerance must be within 0..1000 bps")

    def to_dict(self):
        return asdict(self)


def utc(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def source_digest():
    root = Path(__file__).parent
    return digest({**{p.name: p.read_text() for p in sorted(root.glob("*.py"))},
                   "../core.py": (root.parent / "core.py").read_text()})


def save_json(path, value, *, replace=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.exists() and not replace:
        raise BotError(f"Refusing to overwrite {path}; choose a new output path")
    fd, temp = tempfile.mkstemp(prefix=".research-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as out:
            out.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
            out.flush()
            os.fsync(out.fileno())
        if replace:
            os.replace(temp, path)
        else:
            os.link(temp, path)  # Atomic no-overwrite, including concurrent writers.
            os.unlink(temp)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
