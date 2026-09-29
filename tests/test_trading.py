from decimal import Decimal as D

import pytest
from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.utils.signing import recover_agent_or_user_from_l1_action

from btc_perp_bot.cli import main
from btc_perp_bot.core import BotError, Quote, now_ms
from btc_perp_bot.trading import ExchangeBroker, Journal, account_lock, execution_guard, reconcile


class MarketStub:
    network = "testnet"
    url = "https://api.hyperliquid-testnet.xyz"
    quantity = D(0)
    balance = D(1000)

    def meta(self):
        return {"universe": [{"name": name, "szDecimals": 5} for name in ["ETH", "ATOM", "SOL", "BTC"]]}

    def btc_meta(self):
        return 3, self.meta()["universe"][3]

    def quote(self):
        return Quote(D(79999), D(80000), now_ms())

    def account(self, owner):
        return {"marginSummary": {"accountValue": str(self.balance)},
                "assetPositions": [] if not self.quantity else [{"position": {"coin": "BTC", "szi": str(self.quantity)}}]}

    def open_orders(self, owner):
        return []


@pytest.fixture
def rig(tmp_path):
    market, signer = MarketStub(), Account.create()
    calls = []

    class RecordingExchange(Exchange):
        def _post_action(self, action, signature, nonce):
            recovered = recover_agent_or_user_from_l1_action(action, signature, None, nonce, None, False)
            assert recovered.lower() == signer.address.lower()
            calls.append(action)
            if action["type"] == "cancel":
                status = "success"
            else:
                order = action["orders"][0]
                assert order["a"] == 3  # Actual SDK derives testnet metadata, not hardcoded mainnet id 0.
                if order["t"]["limit"]["tif"] == "Ioc":
                    size = D(order["s"]) * (1 if order["b"] else -1)
                    market.quantity += size
                    status = {"filled": {"totalSz": order["s"], "avgPx": order["p"], "oid": 42}}
                else:
                    status = {"resting": {"oid": 42}}
            return {"status": "ok", "response": {"type": action["type"], "data": {"statuses": [status]}}}

    journal = Journal(tmp_path / "orders.jsonl")
    broker = ExchangeBroker(market, signer, signer.address, journal, exchange_factory=RecordingExchange)
    return market, signer, calls, journal, broker


def test_official_sdk_signs_testnet_order_and_cancel(rig):
    _, _, calls, journal, broker = rig
    order = broker.order("buy", "0.0002", "79000")
    assert order["status"] == {"resting": {"oid": 42}}
    assert broker.cancel(42) == "success"
    assert [x["type"] for x in calls] == ["order", "cancel"]
    assert journal.unresolved() == []


def test_ioc_open_then_reduce_only_close(rig):
    market, _, calls, _, broker = rig
    broker.preflight(require_flat=True)
    broker.set_target(1, market.quote(), D(25), 5)
    assert market.quantity > 0
    broker.set_target(0, market.quote(), D(25), 5)
    assert market.quantity == 0
    assert calls[0]["orders"][0]["r"] is False
    assert calls[1]["orders"][0]["r"] is True


def test_no_collateral_never_sends_signed_request(rig):
    market, _, calls, _, broker = rig
    market.balance = D(0)
    with pytest.raises(BotError, match="collateral"):
        broker.order("buy", "0.0002", "79000")
    assert calls == []


def test_cap_reduce_only_and_precision_rejections(rig):
    _, _, calls, _, broker = rig
    for kwargs in [dict(size="1", price="80000"), dict(size="0.000001", price="80000"),
                   dict(size="0.0002", price="80000.1"), dict(size="0.0002", price="80000", reduce_only=True)]:
        with pytest.raises(BotError):
            broker.order("buy", **kwargs)
    assert calls == []


def test_timeout_is_durable_and_not_retried(rig):
    _, _, calls, journal, broker = rig
    attempts = []

    def ambiguous(*args, **kwargs):
        attempts.append(1)
        raise TimeoutError("unknown outcome")

    broker.sdk.order = ambiguous
    with pytest.raises(BotError, match="unknown"):
        broker.order("buy", "0.0002", "79000")
    assert len(journal.unresolved()) == 1
    with pytest.raises(BotError, match="Uncertain"):
        broker.order("buy", "0.0002", "79000")
    assert attempts == [1]
    assert Journal(journal.path).unresolved() == journal.unresolved()


def test_live_gate_precedes_wallet_or_network_access(capsys):
    assert main(["bot", "--mode", "live", "--keystore", "/does-not-exist"]) == 2
    assert "Mainnet orders are disabled" in capsys.readouterr().out
    with pytest.raises(BotError):
        execution_guard("mainnet")


def test_second_local_process_cannot_use_same_account(tmp_path):
    owner = Account.create().address
    with account_lock("testnet", owner, tmp_path):
        with pytest.raises(BotError, match="Another"):
            with account_lock("testnet", owner, tmp_path):
                pass


def test_outstanding_order_cannot_bypass_notional_cap(rig):
    market, _, calls, _, broker = rig
    market.open_orders = lambda _: [{"coin": "BTC", "oid": 10}]
    with pytest.raises(BotError, match="reserve exposure"):
        broker.order("buy", "0.0002", "79000")
    assert calls == []


def test_unrecognized_success_payload_is_not_assumed_filled(rig):
    _, _, _, journal, broker = rig
    broker.sdk.order = lambda *a, **k: {"status": "ok", "response": {"type": "unexpected"}}
    with pytest.raises(BotError, match="Unrecognized"):
        broker.order("buy", "0.0002", "79000")
    assert len(journal.unresolved()) == 1


def test_reconcile_requires_positive_exchange_evidence_and_never_resends(rig):
    market, signer, calls, journal, _ = rig
    identity = "0x" + "1" * 32
    journal.append({"id": identity, "state": "prepared", "action": "order", "network": "testnet", "account": signer.address})
    market.order_status = lambda *a: {"status": "unknownOid"}
    with pytest.raises(BotError, match="still unknown"):
        reconcile(market, signer.address, journal, identity)
    assert journal.unresolved() == [identity]
    market.order_status = lambda *a: {"status": "order", "order": {"status": "filled"}}
    assert reconcile(market, signer.address, journal, identity)["resubmitted"] is False
    assert journal.unresolved() == []
    assert calls == []
