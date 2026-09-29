from decimal import Decimal as D

import pytest

from btc_perp_bot.core import BotError, Quote, now_ms, number, signal
from btc_perp_bot.paper import PaperBroker


def q(bid, ask):
    return Quote(D(bid), D(ask), now_ms())


def test_long_roundtrip_accounts_for_spread_and_both_fees():
    bot = PaperBroker(slippage_bps=0)
    bot.set_target(1, q("99.9", "100.1"), D(100), 4)
    bot.set_target(0, q("109.9", "110.1"), D(100), 4)
    assert bot.position == 0
    assert bot.fees == D("0.094500")
    assert bot.cash == D("1009.705500")


def test_short_roundtrip():
    bot = PaperBroker(slippage_bps=0)
    bot.set_target(-1, q("99.9", "100.1"), D(100), 4)
    bot.set_target(0, q("89.9", "90.1"), D(100), 4)
    assert bot.cash == D("1009.714500")
    assert bot.position == 0


def test_same_signal_does_not_rebuy_on_every_tick():
    bot = PaperBroker()
    for _ in range(5):
        bot.set_target(1, q("99", "101"), D(25), 4)
    assert len(bot.fills) == 1
    assert bot.equity(q("90", "92")) < bot.cash


def test_budget_blocks_new_entries_but_not_exit():
    bot = PaperBroker(max_orders=1)
    bot.set_target(1, q("99", "101"), D(25), 4)
    bot.set_target(-1, q("99", "101"), D(25), 4)
    assert bot.position == 0
    assert len(bot.fills) == 2  # Risk-reducing exit remains possible.


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_values_rejected(value):
    with pytest.raises(BotError):
        number(value)


def test_stale_book_cannot_simulate_a_trade():
    bot = PaperBroker()
    with pytest.raises(BotError, match="Stale"):
        bot.set_target(1, Quote(D(99), D(101), now_ms() - 20000), D(25), 4)
    assert bot.fills == []


def test_strategy_both_directions_and_neutral():
    assert signal([100, 101, 102, 103, 104], 2, 4) == 1
    assert signal([104, 103, 102, 101, 100], 2, 4) == -1
    assert signal([100] * 5, 2, 4) == 0
