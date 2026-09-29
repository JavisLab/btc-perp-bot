import json
from decimal import Decimal as D

from btc_perp_bot import cli
from btc_perp_bot.core import Quote, now_ms


def test_paper_full_loop_never_constructs_exchange_adapter(monkeypatch, tmp_path, capsys):
    class Market:
        tick = 0

        def __init__(self, network):
            assert network == "mainnet"  # Public prices only.

        def closes(self, count):
            self.tick += 1
            return list(range(100, 120)) if self.tick == 1 else list(range(120, 100, -1))

        def quote(self):
            return Quote(D(109), D(111), now_ms())

        def btc_meta(self):
            return 0, {"szDecimals": 5}

    def forbidden(*args, **kwargs):
        raise AssertionError("Paper mode must never instantiate a signed exchange client")

    monkeypatch.setattr(cli, "Market", Market)
    monkeypatch.setattr(cli, "ExchangeBroker", forbidden)
    monkeypatch.setattr(cli.time, "sleep", lambda *_: None)
    assert cli.main(["bot", "--steps", "2", "--interval", "1", "--output-dir", str(tmp_path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "paper"
    assert report["fill_count"] == 4
    assert report["position_btc"] == "0.00000"
    assert D(report["net_pnl"]) < 0  # Flat prices with spread and fees lose money.
    assert report["funding_modelled"] is False


def test_paper_loss_stop_takes_precedence_over_entry_signal(monkeypatch, tmp_path, capsys):
    class Market:
        tick = 0

        def __init__(self, network):
            pass

        def closes(self, count):
            self.tick += 1
            return list(range(100, 120))

        def quote(self):
            price = D(100) if self.tick == 1 else D(50)
            return Quote(price, price, now_ms())

        def btc_meta(self):
            return 0, {"szDecimals": 5}

    monkeypatch.setattr(cli, "Market", Market)
    monkeypatch.setattr(cli.time, "sleep", lambda *_: None)
    assert cli.main(["bot", "--steps", "3", "--max-loss", "1", "--interval", "1", "--output-dir", str(tmp_path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ticks"] == 2
    assert report["fill_count"] == 2
    assert D(report["position_btc"]) == 0
    assert D(report["net_pnl"]) < -1  # Loss limits aren't guaranteed execution prices.
