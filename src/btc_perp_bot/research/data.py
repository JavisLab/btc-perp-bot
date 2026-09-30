import json
import time
from pathlib import Path

import requests

from ..core import BotError, now_ms, number, positive
from .config import DAY, HOUR, MODEL_VERSION, digest, save_json, utc

INFO_URL = "https://api.hyperliquid.xyz/info"
ALLOWED_TYPES = frozenset({"meta", "candleSnapshot", "fundingHistory", "l2Book"})


class PublicData:
    """Only public BTC data, fixed URL; no account, private-key or exchange method."""

    def __init__(self):
        self.session = requests.Session()
        self.requests = 0

    def info(self, payload):
        kind = payload.get("type")
        if kind not in ALLOWED_TYPES or "user" in payload:
            raise BotError("Research client only permits public market data")
        # Rate-limit retries are read-only and bounded. Nothing is ever signed.
        for attempt in range(3):
            self.requests += 1
            try:
                response = self.session.post(INFO_URL, json=payload, timeout=15, allow_redirects=False)
                if response.status_code in (429, 502, 503, 504) and attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                raise BotError("Public market-data request failed; no account or exchange requests exist here") from exc

    def candles(self, start, end):
        raw = self.info({"type": "candleSnapshot", "req": {
            "coin": "BTC", "interval": "1h", "startTime": start, "endTime": end - 1}})
        return normalize_candles(raw, start, end)

    def funding(self, start, end):
        rows, cursor = {}, start
        for _ in range(30):
            raw = self.info({"type": "fundingHistory", "coin": "BTC", "startTime": cursor, "endTime": end + HOUR - 1})
            if not isinstance(raw, list):
                raise BotError("Invalid funding history")
            if not raw:
                break
            latest = cursor - 1
            for item in raw:
                observed = int(item["time"])
                t = observed // HOUR * HOUR
                latest = max(latest, observed)
                if item["coin"] != "BTC":
                    raise BotError("Unexpected funding coin")
                rate = number(item["fundingRate"])
                if abs(rate) > number("0.04"):
                    raise BotError("Funding rate outside documented hourly bounds")
                if start <= t <= end:
                    value = {"time": t, "observed_time": observed, "rate": str(rate)}
                    if t in rows and rows[t] != value:
                        raise BotError("Conflicting funding duplicates")
                    rows[t] = value
            if latest < cursor:
                raise BotError("Funding pagination made no progress")
            cursor = latest + 1
            if cursor > end:
                break
            time.sleep(0.05)
        else:
            raise BotError("Funding pagination exceeded bounded request budget")
        return [rows[t] for t in sorted(rows)]

    def metadata(self):
        for asset, item in enumerate(self.info({"type": "meta"})["universe"]):
            if item["name"] == "BTC" and not item.get("isDelisted", False):
                decimals = int(item["szDecimals"])
                if not 0 <= decimals <= 8:
                    raise BotError("Invalid BTC size precision")
                return {"coin": "BTC", "asset": asset, "sz_decimals": decimals}
        raise BotError("BTC market missing")

    def book(self):
        raw = self.info({"type": "l2Book", "coin": "BTC"})
        book = {"time": int(raw["time"]), "coin": raw["coin"],
                "bids": [[str(positive(x["px"])), str(positive(x["sz"]))] for x in raw["levels"][0]],
                "asks": [[str(positive(x["px"])), str(positive(x["sz"]))] for x in raw["levels"][1]]}
        validate_book(book, now_ms())
        return book


def validate_book(book, current):
    if book["coin"] != "BTC" or not -2000 <= current - book["time"] <= 10_000:
        raise BotError("Stale/future or wrong-coin order book")
    if not book["bids"] or not book["asks"]:
        raise BotError("Empty order book")
    for side, descending in (("bids", True), ("asks", False)):
        prices = [positive(x[0]) for x in book[side]]
        for _, qty in book[side]:
            positive(qty)
        if prices != sorted(prices, reverse=descending) or len(prices) != len(set(prices)):
            raise BotError("Unsorted or duplicate book levels")
    if number(book["bids"][0][0]) > number(book["asks"][0][0]):
        raise BotError("Crossed order book")


def normalize_candles(raw, start, end):
    if not isinstance(raw, list):
        raise BotError("Invalid candle response")
    rows = {}
    for item in raw:
        t = int(item["t"])
        if item["s"] != "BTC" or item["i"] != "1h" or t % HOUR or int(item["T"]) != t + HOUR - 1:
            raise BotError("Unexpected candle coin, interval or time")
        if not start <= t < end:
            continue
        row = {"t": t, **{key: str(positive(item[key])) for key in ("o", "h", "l", "c")},
               "v": str(number(item["v"]))}
        if not number(row["l"]) <= min(number(row["o"]), number(row["c"])) <= max(number(row["o"]), number(row["c"])) <= number(row["h"]) or number(row["v"]) < 0:
            raise BotError("Invalid OHLC/volume")
        if t in rows and rows[t] != row:
            raise BotError("Conflicting candle duplicates")
        rows[t] = row
    candles = [rows[t] for t in sorted(rows)]
    expected = list(range(start, end, HOUR))
    if [x["t"] for x in candles] != expected:
        raise BotError("Missing candle history; no forward filling or synthetic replacement permitted")
    return candles


def validate_dataset(data):
    if data.get("version") != MODEL_VERSION or data.get("coin") != "BTC" or data.get("interval") != "1h":
        raise BotError("Unsupported research dataset")
    content = {k: v for k, v in data.items() if k != "sha256"}
    if data.get("sha256") != digest(content):
        raise BotError("Dataset checksum mismatch")
    candles = data["candles"]
    if not candles or data["start_ms"] % HOUR or data["end_ms"] % HOUR:
        raise BotError("Empty or unaligned dataset")
    # The disk format goes through the same strict validator as the API format.
    raw = [{**x, "s": "BTC", "i": "1h", "T": x["t"] + HOUR - 1} for x in candles]
    checked = normalize_candles(raw, data["start_ms"], data["end_ms"])
    if checked != candles:
        raise BotError("Dataset candles must be unique and ordered")
    expected = list(range(data["start_ms"] + HOUR, data["end_ms"] + 1, HOUR))
    if [x["time"] for x in data["funding"]] != expected:
        raise BotError("Incomplete/duplicate/out-of-order hourly funding history")
    for event in data["funding"]:
        if abs(number(event["rate"])) > number("0.04"):
            raise BotError("Invalid funding rate")
        if not event["time"] <= event["observed_time"] < event["time"] + HOUR:
            raise BotError("Invalid observed funding timestamp")
    if not 0 <= int(data["metadata"]["sz_decimals"]) <= 8:
        raise BotError("Invalid size precision")
    return data


def collect(path, days=120, client=None, current=None):
    if not 14 <= days <= 200:
        raise BotError("Choose 14..200 days; the API only retains the latest 5000 candles")
    current = now_ms() if current is None else current
    # Leave one completed hour for publication lag in funding data.
    end = (current // HOUR - 1) * HOUR
    start = end - days * DAY
    client = client or PublicData()
    data = {"version": MODEL_VERSION, "coin": "BTC", "interval": "1h", "source": INFO_URL,
            "retrieved_at": utc(current), "start_ms": start, "end_ms": end,
            "metadata": client.metadata(), "candles": client.candles(start, end),
            "funding": client.funding(start + HOUR, end),
            "funding_notional": "previous_hour_trade_close_proxy_not_historical_oracle",
            "historical_spread": "assumed_not_observed", "metadata_time": "retrieval_time_not_historical"}
    data["sha256"] = digest(data)
    validate_dataset(data)
    save_json(path, data)
    return {"path": str(path), "sha256": data["sha256"], "candles": len(data["candles"]),
            "funding_events": len(data["funding"]), "start": utc(start), "end": utc(end)}


def load_dataset(path):
    return validate_dataset(json.loads(Path(path).read_text()))
