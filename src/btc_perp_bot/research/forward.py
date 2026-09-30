import copy
import fcntl
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from ..core import BotError, now_ms, number
from .config import ALL_STRATEGIES, HOUR, MODEL_VERSION, PRESETS, WARMUP, Config, canonical, source_digest, utc
from .data import PublicData, validate_book
from .engine import Account, book_execution, change_target
from .strategies import DESCRIPTIONS, target


@contextmanager
def store_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(str(path) + ".lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BotError("Another paper process is using this virtual account") from exc
        yield
    finally:
        os.close(fd)


def initial_state(config, metadata):
    return {"version": MODEL_VERSION, "source_sha256": source_digest(), "config": config.to_dict(),
            "metadata": metadata, "created_at": utc(now_ms()), "last_quote_time": None,
            "last_candle": None, "last_funding": None, "last_mid": None, "observed_ticks": 0,
            "gap_count": 0, "unobserved_ms": 0,
            "accounts": {name: Account(config.cash).state() for name in ALL_STRATEGIES}}


def advance(previous, candles, book, funding, config, current):
    """Pure step: commit only after all input validation and accounting succeeds."""
    validate_book(book, current)
    if previous["last_quote_time"] is not None and book["time"] <= previous["last_quote_time"]:
        raise BotError("Book timestamp did not advance; virtual fills not repeated")
    boundary = book["time"] // HOUR * HOUR
    if len(candles) < WARMUP or candles[-1]["t"] + HOUR != boundary:
        raise BotError("Need complete, current closed-hour history before any simulated fill")
    if any(b["t"] - a["t"] != HOUR for a, b in zip(candles, candles[1:])):
        raise BotError("Gap in forward candle history")
    by_time = {x["t"]: x for x in candles}
    expected = [boundary] if previous["last_funding"] is None else list(range(previous["last_funding"] + HOUR, boundary + 1, HOUR))
    if [x["time"] for x in funding] != expected:
        raise BotError("Funding publication missing or duplicated; wait for complete history")
    for item in funding:
        if item["time"] - HOUR not in by_time or not item["time"] <= item["observed_time"] <= book["time"]:
            raise BotError("Funding reference missing or future-dated")
        if abs(number(item["rate"])) > number("0.04"):
            raise BotError("Invalid hourly funding rate")
    state = copy.deepcopy(previous)
    all_events, points = [], {}
    mid = (number(book["bids"][0][0]) + number(book["asks"][0][0])) / 2
    new_signal = candles[-1]["t"] != previous["last_candle"]
    if previous["last_quote_time"] is not None:
        gap = book["time"] - previous["last_quote_time"]
        if gap > 120_000:
            state["gap_count"] += 1
            state["unobserved_ms"] += gap
            all_events.append({"strategy": "system", "kind": "observation_gap", "time": book["time"],
                               "gap_ms": gap, "missed_orders_replayed": False})
    for name in ALL_STRATEGIES:
        account = Account(config.cash, state["accounts"][name])
        for item in funding:
            # A position opened after the funding event does not pay that old event.
            if account.position and account.entry_time < item["observed_time"]:
                account.apply_funding(item["observed_time"], item["rate"], by_time[item["time"] - HOUR]["c"])
        account.observe(mid, config.max_drawdown if name in PRESETS else None)
        wanted = target(name, candles[-WARMUP:], account.direction) if new_signal else account.direction
        if new_signal or (account.halted and account.position):
            # Include observed half-spread and IOC limit in sizing's adverse price bound.
            half = (number(book["asks"][0][0]) / mid - 1) * 10000
            padding = half + number(config.max_book_slippage_bps) + half * number(config.max_book_slippage_bps) / 10000
            change_target(account, wanted, mid, book["time"], config, state["metadata"]["sz_decimals"],
                          book_execution(book, config), padding)
        account.observe(mid, config.max_drawdown if name in PRESETS else None)
        points[name] = account.metrics(mid)
        state["accounts"][name] = account.state()
        all_events.extend({"strategy": name, **event} for event in account.events)
    state.update(last_quote_time=book["time"], last_candle=candles[-1]["t"], last_funding=boundary,
                 last_mid=str(mid), observed_ticks=state["observed_ticks"] + 1)
    return state, all_events, points


def connect(path):
    db = sqlite3.connect(path, timeout=5)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS ticks (id INTEGER PRIMARY KEY, time INTEGER NOT NULL, payload TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, time INTEGER NOT NULL, payload TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS observations (id INTEGER PRIMARY KEY, time INTEGER NOT NULL, payload TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS errors (id INTEGER PRIMARY KEY, time INTEGER NOT NULL, message TEXT NOT NULL)")
    db.commit()
    return db


def commit_step(db, state, events, points, observation):
    # State, evidence, fills and valuation either all commit or none do.
    with db:
        db.execute("INSERT OR REPLACE INTO state VALUES (1, ?)", (canonical(state),))
        db.execute("INSERT INTO ticks(time,payload) VALUES (?,?)", (state["last_quote_time"], canonical(points)))
        db.execute("INSERT INTO observations(time,payload) VALUES (?,?)", (state["last_quote_time"], canonical(observation)))
        for event in events:
            db.execute("INSERT INTO events(time,payload) VALUES (?,?)", (event["time"], canonical(event)))


def run_paper(path, config, steps=6, interval=10, client=None, emit=None):
    if steps < 0 or steps > 1_000_000 or not 1 <= interval <= 3600:
        raise BotError("Steps 0=until interrupted, otherwise 1..1000000; interval 1..3600 seconds")
    path = Path(path)
    client = client or PublicData()
    completed = failures = 0
    with store_lock(path):
        db = connect(path)
        try:
            row = db.execute("SELECT payload FROM state WHERE id=1").fetchone()
            state = json.loads(row[0]) if row else initial_state(config, client.metadata())
            if state["version"] != MODEL_VERSION or state["config"] != config.to_dict() or state["source_sha256"] != source_digest():
                raise BotError("Paper model/config changed; create a separate virtual account, do not silently reset")
            count = 0
            while steps == 0 or count < steps:
                count += 1
                try:
                    boundary = now_ms() // HOUR * HOUR
                    start = boundary - (WARMUP + 2) * HOUR
                    if state["last_funding"] is not None:
                        start = min(start, state["last_funding"])
                    if boundary - start > 4990 * HOUR:
                        raise BotError("Paper outage exceeds available candle history; cannot reconstruct funding")
                    candles = client.candles(start, boundary)
                    funding = (client.funding(boundary, boundary) if state["last_funding"] is None else
                               [] if state["last_funding"] == boundary else client.funding(state["last_funding"] + HOUR, boundary))
                    book = client.book()  # Last request, to avoid ageing the execution quote.
                    updated, events, points = advance(state, candles, book, funding, config, now_ms())
                    observation = {"book": book, "closed_candles": candles, "funding": funding}
                    commit_step(db, updated, events, points, observation)
                    state = updated
                    completed += 1
                    if emit:
                        emit({"tick": state["observed_ticks"], "time": utc(book["time"]),
                              "virtual_equity": {name: x["equity"] for name, x in points.items()}})
                except (BotError, KeyError, ValueError, TypeError) as exc:
                    failures += 1
                    text = str(exc) if isinstance(exc, BotError) else "Malformed public market data; no virtual fill applied"
                    with db:
                        db.execute("INSERT INTO errors(time,message) VALUES (?,?)", (now_ms(), text))
                    if emit:
                        emit({"skipped_tick": count, "reason": text})
                if steps == 0 or count < steps:
                    time.sleep(interval)
        except KeyboardInterrupt:
            # Deliberately preserve open virtual positions; no automatic flatten on stop.
            pass
        finally:
            db.close()
    return {"database": str(path), "completed_ticks": completed, "skipped_ticks": failures,
            "real_orders": 0, "open_virtual_positions_preserved": True}


def paper_report(path):
    path = Path(path).resolve()
    if not path.is_file():
        raise BotError("Paper database does not exist")
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        db.execute("BEGIN")  # Consistent read snapshot while a paper process may continue.
        row = db.execute("SELECT payload FROM state WHERE id=1").fetchone()
        if not row:
            raise BotError("No successful paper observation yet")
        state = json.loads(row[0])
        ticks = [(t, json.loads(payload)) for t, payload in db.execute("SELECT time,payload FROM ticks ORDER BY id")]
        events = [json.loads(x[0]) for x in db.execute("SELECT payload FROM events ORDER BY id")]
        errors = [{"time": t, "message": msg} for t, msg in db.execute("SELECT time,message FROM errors ORDER BY id")]
    finally:
        db.close()
    accounts = {}
    for name in ALL_STRATEGIES:
        account = Account(state["config"]["cash"], state["accounts"][name])
        accounts[name] = {"strategy": name, "description": DESCRIPTIONS[name], "metrics": account.metrics(state["last_mid"]),
                          "curve": [{"time": t, "equity": value[name]["equity"],
                                     "drawdown_pct": value[name]["current_drawdown_pct"]} for t, value in ticks],
                          "events": [x for x in events if x.get("strategy") == name]}
    return {"version": MODEL_VERSION, "kind": "forward_paper", "config": state["config"],
            "source_sha256": state["source_sha256"], "start": state["created_at"],
            "last_observation": utc(state["last_quote_time"]), "observed_ticks": state["observed_ticks"],
            "gap_count": state["gap_count"], "unobserved_ms": state["unobserved_ms"],
            "accounts": accounts, "errors": errors,
            "limitations": ["가상 체결만 존재합니다. 실제 거래소 주문/지갑/서명은 없습니다.",
                            "실시간 스냅샷 깊이와 가격제한으로 체결을 추정하며 대기열/네트워크 전달 후 호가 변동은 재현하지 못합니다.",
                            "펀딩은 실제 과거율과 직전 시간봉 거래 종가 추정 명목금액으로 처리합니다.",
                            "중단 중 주문은 소급 재생하지 않습니다. 관측 공백이 있으면 연속 운영 성과가 아닙니다.",
                            "프로세스 종료 시 가상 포지션을 보존합니다. 현금과 미실현손익을 합친 평가자산을 표시합니다.",
                            "관측 시점 손실중단은 최대손실 보장이 아니며 정확한 강제청산은 모형에 없습니다."]}


def verify_paper(path):
    """Offline replay of every stored public observation, not historical missed orders."""
    path = Path(path).resolve()
    if not path.is_file():
        raise BotError("Paper database does not exist")
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        db.execute("BEGIN")
        row = db.execute("SELECT payload FROM state WHERE id=1").fetchone()
        if not row:
            raise BotError("No successful paper observation yet")
        final = json.loads(row[0])
        observations = [json.loads(x[0]) for x in db.execute("SELECT payload FROM observations ORDER BY id")]
        ticks = [(t, json.loads(x)) for t, x in db.execute("SELECT time,payload FROM ticks ORDER BY id")]
        recorded_events = [json.loads(x[0]) for x in db.execute("SELECT payload FROM events ORDER BY id")]
    finally:
        db.close()
    if final["source_sha256"] != source_digest() or final["version"] != MODEL_VERSION:
        raise BotError("Replay requires the exact original research source version")
    if len(observations) != len(ticks) or len(ticks) != final["observed_ticks"]:
        raise BotError("Observation/tick count mismatch")
    config = Config(**final["config"])
    state = initial_state(config, final["metadata"])
    state["created_at"] = final["created_at"]
    replayed_events = []
    for obs, (timestamp, expected_points) in zip(observations, ticks):
        state, events, points = advance(state, obs["closed_candles"], obs["book"], obs["funding"], config, timestamp)
        if points != expected_points or obs["book"]["time"] != timestamp:
            raise BotError("Paper replay valuation mismatch")
        replayed_events.extend(events)
    if state != final or replayed_events != recorded_events:
        raise BotError("Paper replay final ledger/event mismatch")
    return {"verified": True, "ticks_replayed": len(ticks), "events_matched": len(recorded_events),
            "all_five_accounts_matched": True, "network_requests": 0, "real_orders": 0,
            "source_sha256": final["source_sha256"]}
