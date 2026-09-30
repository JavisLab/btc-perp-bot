"""Accounting identities, anti-lookahead, adverse execution and crash-safe paper tests.

Fixtures here are synthetic and are never reported as historical market evidence.
"""
import copy
import json
import math
import sqlite3
import subprocess
import sys
from dataclasses import replace
from decimal import Decimal as D

import pytest

from btc_perp_bot.core import BotError
from btc_perp_bot.research.backtest import compare, simulate
from btc_perp_bot.research.config import Config, HOUR, MODEL_VERSION, canonical, digest
from btc_perp_bot.research.data import PublicData, normalize_candles, validate_dataset
from btc_perp_bot.research.engine import Account, bar_execution, book_execution, change_target, entry_size
from btc_perp_bot.research.forward import (
    advance, commit_step, connect, initial_state, paper_report, run_paper, store_lock, verify_paper,
)
from btc_perp_bot.research.report import render, write_report

BASE = 20_000 * HOUR
META = {"coin": "BTC", "asset": 0, "sz_decimals": 5}


def candles(count=300, flat=False):
    result, previous = [], D(100)
    for i in range(count):
        close = D(100) if flat else D(str(round(100 + i / 40 + 8 * math.sin(i / 13), 5)))
        result.append({"t": BASE + i * HOUR, "o": str(previous), "h": str(max(previous, close) + D("0.1")),
                       "l": str(min(previous, close) - D("0.1")), "c": str(close), "v": "123"})
        previous = close
    return result


def funding(t, rate="0.0001"):
    return {"time": t, "observed_time": t + 50, "rate": rate}


def dataset(count=300, flat=False):
    data = {"version": MODEL_VERSION, "coin": "BTC", "interval": "1h", "metadata": META,
            "start_ms": BASE, "end_ms": BASE + count * HOUR, "candles": candles(count, flat),
            "funding": [funding(BASE + i * HOUR) for i in range(1, count + 1)]}
    rehash(data)
    return data


def rehash(data):
    data["sha256"] = digest({k: v for k, v in data.items() if k != "sha256"})


def book(t, size="100", bid="99.99", ask="100.01"):
    return {"coin": "BTC", "time": t, "bids": [[bid, size]], "asks": [[ask, size]]}


def first_step(config=None):
    config = config or Config()
    bars = candles(80, flat=True)
    t = BASE + 80 * HOUR + 2000
    before = initial_state(config, META)
    obs = {"book": book(t), "closed_candles": bars, "funding": [funding(t // HOUR * HOUR)]}
    state, events, points = advance(before, bars, obs["book"], obs["funding"], config, t)
    return before, state, events, points, obs


@pytest.mark.parametrize("sign,exit_price,expected", [(1, "110", "1017.38"), (-1, "90", "1021.82")])
def test_independent_long_short_fee_funding_identity(sign, exit_price, expected):
    a = Account("1000")
    a.fill(1, D(2 * sign), "100", "10", "entry")
    a.apply_funding(2, "0.01", "110")
    a.fill(3, D(-2 * sign), exit_price, "10", "exit")
    assert a.cash == D(expected)
    assert a.cash == a.initial + a.gross_pnl + a.funding - a.fees
    assert a.trade_count == a.wins == 1 and a.position == 0
    assert D(a.events[-1]["net_pnl"]) == a.cash - a.initial
    restored = Account("1000", a.state())
    assert restored.metrics(100) == a.metrics(100)


def test_partial_exit_does_not_flip_and_counts_one_completed_trade():
    a, config = Account(1000), Config()
    a.fill(1, D(1), 100, 0, "entry")
    change_target(a, -1, 110, 2, config, 5, lambda qty: (D("0.4"), D(110)), 0)
    assert a.position == D("0.6") and a.trade_count == 0
    assert a.events[-1]["reason"] == "partial_or_unfilled_exit"
    a.fill(3, D("-0.6"), 110, config.fee_bps, "exit")
    assert a.trade_count == 1 and a.position == 0


def test_book_depth_price_limit_and_reuse_cannot_invent_liquidity():
    b = {"asks": [["100", "0.1"], ["100.05", "0.2"], ["110", "999"]], "bids": [["99.9", "1"]]}
    execute = book_execution(b, Config(slippage_bps="0", max_book_slippage_bps="10"))
    qty, price = execute(D(1))
    assert qty == D("0.3") and price == D("30.010") / D("0.3")
    assert execute(D(1))[0] == 0
    assert b["asks"][0][1] == "0.1"  # input snapshot unchanged
    assert book_execution(b, Config(slippage_bps="11", max_book_slippage_bps="10"))(D(1))[0] == 0


@pytest.mark.parametrize("direction", [1, -1])
def test_entry_exposure_includes_fee_and_adverse_mark_to_market(direction):
    a, config = Account(1000), Config(exposure="1", half_spread_bps="10", slippage_bps="10")
    size = entry_size(a, D(100), config, 5, D(20))
    _, price = bar_execution(100, config)(direction * size)
    a.fill(1, direction * size, price, config.fee_bps, "entry")
    assert abs(a.position) * price <= a.equity(100)
    assert size.as_tuple().exponent == -5


@pytest.mark.parametrize("damage", ["checksum", "gap", "funding", "nan", "duplicate"])
def test_corrupt_or_incomplete_dataset_rejected_even_if_rehashed(damage):
    data = dataset()
    if damage in ("checksum", "gap"):
        data["candles"].pop(12)
    elif damage == "funding":
        data["funding"].pop(13)
    elif damage == "nan":
        data["candles"][12]["c"] = "NaN"
    else:
        data["candles"].insert(12, copy.deepcopy(data["candles"][12]))
    if damage != "checksum":
        rehash(data)
    with pytest.raises(BotError):
        validate_dataset(data)


def test_public_client_refuses_accounts_and_exchange_before_http():
    class NeverNetwork:
        def post(self, *args, **kwargs):
            pytest.fail("Private query reached the network")
    client = PublicData()
    client.session = NeverNetwork()
    for payload in ({"type": "order"}, {"type": "clearinghouseState", "user": "x"}, {"type": "meta", "user": "x"}):
        with pytest.raises(BotError):
            client.info(payload)


def test_raw_funding_millisecond_offsets_and_pagination():
    client, calls = PublicData(), []
    def response(payload):
        calls.append(payload)
        times = [BASE + HOUR + 41, BASE + 2 * HOUR + 89] if len(calls) == 1 else [BASE + 3 * HOUR + 22]
        return [{"time": t, "coin": "BTC", "fundingRate": "0.0001"} for t in times]
    client.info = response
    values = client.funding(BASE + HOUR, BASE + 3 * HOUR)
    assert [x["time"] for x in values] == [BASE + i * HOUR for i in (1, 2, 3)]
    assert values[0]["observed_time"] == BASE + HOUR + 41
    assert calls[1]["startTime"] == BASE + 2 * HOUR + 90


def test_missing_api_candles_are_not_forward_filled():
    with pytest.raises(BotError, match="Missing"):
        normalize_candles([], BASE, BASE + HOUR)


def test_future_price_changes_cannot_change_earlier_signals_or_fills():
    original, altered = dataset(), dataset()
    cutoff = 160
    for bar in altered["candles"][cutoff:]:
        for key in ("o", "h", "l", "c"):
            bar[key] = str(D(bar[key]) * 3)
    for name in ("trend", "breakout", "mean_reversion"):
        a = simulate(original, name, 62, 250, Config())
        b = simulate(altered, name, 62, 250, Config())
        before = lambda result, key: [x for x in result[key] if x["time"] < BASE + cutoff * HOUR]
        assert before(a, "decisions") == before(b, "decisions")
        assert before(a, "events") == before(b, "events")
        assert all(x["last_signal_bar"] + HOUR <= x["time"] for x in a["decisions"])


def test_candidate_selection_does_not_use_holdout():
    a = compare(dataset(), Config())
    data = dataset()
    split = 62 + int((len(data["candles"]) - 62) * D("0.70"))
    for bar in data["candles"][split:]:
        for key in ("o", "h", "l", "c"):
            bar[key] = str(D(bar[key]) * D("1.5"))
    rehash(data)
    b = compare(data, Config())
    assert a["selected"] == b["selected"]
    assert a["training"] == b["training"]
    assert a["holdout"]["buy_hold"]["metrics"] != b["holdout"]["buy_hold"]["metrics"]


def test_costs_reduce_flat_market_returns_and_accounting_balances():
    data = dataset(flat=True)
    for item in data["funding"]:
        item["rate"] = "0"
    a = simulate(data, "buy_hold", 62, 200, Config())
    b = simulate(data, "buy_hold", 62, 200, Config(fee_bps="9", half_spread_bps="1", slippage_bps="2"))
    assert D(b["metrics"]["net_pnl"]) < D(a["metrics"]["net_pnl"]) < 0
    for result in (a, b):
        m = result["metrics"]
        assert D(m["equity"]) == 1000 + D(m["gross_realized"]) + D(m["funding_cashflow"]) - D(m["fees"])
        assert m["position_btc"] == "0.00000"


def test_historical_funding_before_exit_and_not_before_entry():
    data = dataset(flat=True)
    result = simulate(data, "buy_hold", 62, 65, Config(fee_bps="0", half_spread_bps="0", slippage_bps="0"))
    events = result["events"]
    payments = [x for x in events if x["kind"] == "funding"]
    assert [x["time"] for x in payments] == [BASE + i * HOUR for i in (63, 64, 65)]
    assert sum(D(x["cashflow"]) for x in payments) == D("-0.15")
    assert events[-2]["kind"] == "fill" and events[-2]["reason"] == "target_exit"


def test_drawdown_stop_exits_and_cannot_reopen():
    a, config = Account(1000), Config()
    a.fill(1, D(5), 100, 0, "entry")
    a.observe(50, config.max_drawdown)
    assert a.halted and a.halt_reason == "drawdown_stop"
    change_target(a, 1, 50, 2, config, 5, bar_execution(50, config), 2)
    assert a.position == 0
    change_target(a, 1, 100, 3, config, 5, bar_execution(100, config), 2)
    assert a.position == 0 and a.fill_count == 2


@pytest.mark.parametrize("damage", ["stale", "duplicate", "funding_missing", "candle_gap"])
def test_bad_forward_observation_never_mutates_account(damage):
    _, state, _, _, obs = first_step()
    previous = canonical(state)
    b = book(obs["book"]["time"] + HOUR)
    bars = candles(81, flat=True)
    rates = [funding(BASE + 81 * HOUR)]
    current = b["time"]
    if damage == "stale":
        current += 20_000
    elif damage == "duplicate":
        b = obs["book"]
        current = b["time"]
    elif damage == "funding_missing":
        rates = []
    else:
        bars.pop(70)
    with pytest.raises(BotError):
        advance(state, bars, b, rates, Config(), current)
    assert canonical(state) == previous


def test_funding_once_on_resume_gaps_not_replayed_and_no_repeat_entry():
    _, state, _, _, obs = first_step()
    before_position = D(state["accounts"]["buy_hold"]["position"])
    t = obs["book"]["time"] + 2 * HOUR
    rates = [funding(BASE + i * HOUR, "0.001") for i in (81, 82)]
    resumed, events, _ = advance(state, candles(82, flat=True), book(t), rates, Config(), t)
    a = resumed["accounts"]["buy_hold"]
    assert D(a["funding"]) == -before_position * 100 * D("0.002")
    assert resumed["gap_count"] == 1 and resumed["unobserved_ms"] == 2 * HOUR
    assert a["fill_count"] == 1
    again, events2, _ = advance(resumed, candles(82, flat=True), book(t + 1000), [], Config(), t + 1000)
    assert again["accounts"]["buy_hold"] == resumed["accounts"]["buy_hold"]
    assert not any(e["kind"] == "funding" for e in events2)
    assert any(e["kind"] == "observation_gap" and not e["missed_orders_replayed"] for e in events)


def test_initial_paper_tick_waits_for_current_funding_publication():
    before, _, _, _, obs = first_step()
    with pytest.raises(BotError, match="publication"):
        advance(before, obs["closed_candles"], obs["book"], [], Config(), obs["book"]["time"])
    future = copy.deepcopy(obs["funding"])
    future[0]["observed_time"] = obs["book"]["time"] + 1
    with pytest.raises(BotError, match="future"):
        advance(before, obs["closed_candles"], obs["book"], future, Config(), obs["book"]["time"])


def test_sqlite_atomic_commit_and_process_lock(tmp_path):
    _, state, events, points, obs = first_step()
    path = tmp_path / "paper.sqlite"
    with store_lock(path):
        with pytest.raises(BotError, match="Another"):
            with store_lock(path):
                pass
        db = connect(path)
        commit_step(db, state, events, points, obs)
        db.execute("CREATE TRIGGER fail_event BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT, 'failure'); END")
        later = copy.deepcopy(state)
        later["observed_ticks"] += 1
        with pytest.raises(sqlite3.IntegrityError):
            commit_step(db, later, events, points, obs)
        assert json.loads(db.execute("SELECT payload FROM state").fetchone()[0]) == state
        assert db.execute("SELECT count(*) FROM ticks").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM observations").fetchone()[0] == 1
        db.close()
    assert paper_report(path)["observed_ticks"] == 1


def test_restart_preserves_account_and_rejects_config_change(tmp_path, monkeypatch):
    from btc_perp_bot.research import forward
    t = [BASE + 80 * HOUR + 2000]
    monkeypatch.setattr(forward, "now_ms", lambda: t[0])
    class Client:
        metadata = lambda self: META
        candles = lambda self, start, end: [x for x in candles(80, flat=True) if start <= x["t"] < end]
        funding = lambda self, start, end: [funding(start)]
        book = lambda self: book(t[0])
    path = tmp_path / "paper.sqlite"
    assert run_paper(path, Config(), 1, 1, Client())["completed_ticks"] == 1
    before = paper_report(path)
    t[0] += 1000
    assert run_paper(path, Config(), 1, 1, Client())["completed_ticks"] == 1
    after = paper_report(path)
    assert after["observed_ticks"] == 2
    assert after["accounts"]["buy_hold"]["metrics"] == before["accounts"]["buy_hold"]["metrics"]
    assert verify_paper(path)["ticks_replayed"] == 2
    with pytest.raises(BotError, match="model/config"):
        run_paper(path, replace(Config(), cash="2000"), 1, 1, Client())
    db = sqlite3.connect(path)
    db.execute("DELETE FROM ticks WHERE id=2")
    db.commit()
    db.close()
    with pytest.raises(BotError, match="count mismatch"):
        verify_paper(path)


def test_offline_cli_report_imports_no_signer_or_trading_and_uses_no_network(tmp_path):
    source = tmp_path / "data.json"
    source.write_text(json.dumps(dataset()))
    code = """
import socket, sys
def blocked(*a, **kw):
    raise AssertionError('Network not permitted during offline research')
socket.socket = blocked
from btc_perp_bot.research.cli import main
assert 'btc_perp_bot.wallet' not in sys.modules
assert 'btc_perp_bot.trading' not in sys.modules
assert 'hyperliquid.exchange' not in sys.modules
assert main(sys.argv[1:]) == 0
"""
    # Install socket blocker after requests import: SSL needs socket's class at import time.
    code = "import requests\n" + code
    out = tmp_path / "report"
    completed = subprocess.run([sys.executable, "-c", code, "backtest", "--data", str(source), "--out", str(out)],
                               capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert (out / "report.html").is_file()
    assert (out / "events.csv").is_file()
    result = json.loads((out / "results.json").read_text())
    result["limitations"].append('<script src="https://evil.example">bad</script>')
    html = render(result)
    assert '<script src=' not in html and '&lt;script src=' in html
    assert "https://cdn" not in html
    with pytest.raises(BotError, match="already exists"):
        write_report(result, out)
