import json
import os
import stat
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from pathlib import Path


class BotError(Exception):
    """An expected, secret-free user-facing error."""


def number(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise BotError("Invalid numeric input") from exc
    if not result.is_finite():
        raise BotError("Numbers must be finite")
    return result


def positive(value):
    result = number(value)
    if result <= 0:
        raise BotError("Value must be positive")
    return result


def now_ms():
    return time.time_ns() // 1_000_000


def private_dir(path):
    path = Path(path).expanduser()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    st = path.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid():
        raise BotError("Storage directory must be owned by this user and not a symlink")
    if st.st_mode & 0o077:
        raise BotError("Storage directory permissions must be 0700")
    return path


def private_open(path, flags, *, exclusive=False):
    path = Path(path).expanduser()
    flags |= os.O_NOFOLLOW
    if exclusive:
        flags |= os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
        os.close(fd)
        raise BotError("Secret/state file must be a regular owner-only file (0600)")
    return fd


def write_private_json(path, value):
    path = Path(path).expanduser()
    private_dir(path.parent)
    fd = private_open(path, os.O_WRONLY, exclusive=True)
    with os.fdopen(fd, "w") as out:
        json.dump(value, out, indent=2, default=str)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())


@dataclass(frozen=True)
class Quote:
    bid: Decimal
    ask: Decimal
    timestamp: int

    @property
    def mid(self):
        return (self.bid + self.ask) / 2

    def validate(self, current_ms=None):
        positive(self.bid)
        positive(self.ask)
        if self.bid > self.ask:
            raise BotError("Crossed order book")
        age = (now_ms() if current_ms is None else current_ms) - self.timestamp
        if not -2000 <= age <= 10000:
            raise BotError("Stale or future-dated order book; no new order")


def size_for(notional, quote, decimals):
    qty = (positive(notional) / quote.mid).quantize(Decimal(10) ** -decimals, rounding=ROUND_DOWN)
    if qty <= 0:
        raise BotError("Notional is below one lot")
    return qty


def signal(closes, fast=3, slow=8, threshold=Decimal("0.0002")):
    if not 1 <= fast < slow or len(closes) < slow:
        raise BotError("Need enough closed candles and 1 <= fast < slow")
    threshold = number(threshold)
    if not 0 <= threshold < 1:
        raise BotError("Threshold must be between 0 and 1")
    closes = [positive(x) for x in closes]
    fast_mean = sum(closes[-fast:]) / fast
    slow_mean = sum(closes[-slow:]) / slow
    if fast_mean > slow_mean * (1 + threshold):
        return 1
    if fast_mean < slow_mean * (1 - threshold):
        return -1
    return 0
