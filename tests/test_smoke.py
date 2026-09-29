import json
from decimal import Decimal as D, ROUND_DOWN
from pathlib import Path

import pytest
import requests
from hyperliquid.utils.signing import recover_agent_or_user_from_l1_action

from btc_perp_bot import cli
from btc_perp_bot.core import BotError, now_ms
from btc_perp_bot.market import Market
from btc_perp_bot.smoke import prepare
from btc_perp_bot.wallet import create_wallet


class OfflineExchangeServer:
    """Offline exchange model behind the real SDK HTTP and signing paths."""

    def __init__(self, owner):
        self.owner = owner
        self.balance = D(1000)
        self.position = D(0)
        self.orders, self.statuses, self.cloids = {}, {}, {}
        self.fills, self.actions, self.requests = [], [], []
        self.next_oid = 100
        self.cancel_lag = 2
        self.canceled_oid = None
        self.partial_entry = False
        self.partial_close = False
        self.hide_fills = False
        self.timeout_maker = False

    def request(self, method, url, **kwargs):
        assert method.upper() == "POST"
        assert url in {"https://api.hyperliquid-testnet.xyz/info", "https://api.hyperliquid-testnet.xyz/exchange"}
        payload = kwargs["json"]
        self.requests.append(url.rsplit("/", 1)[-1])
        data = self.info(payload) if url.endswith("/info") else self.exchange(payload)
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(data).encode()
        return response

    def info(self, payload):
        kind = payload["type"]
        if "user" in payload:
            assert payload["user"].lower() == self.owner.lower()
        if kind == "meta":
            return {"universe": [{"name": coin, "szDecimals": 5} for coin in ("ETH", "ATOM", "SOL", "BTC")]}
        if kind == "l2Book":
            return {"coin": "BTC", "time": now_ms(), "levels": [[{"px": "79999"}], [{"px": "80000"}]]}
        if kind == "clearinghouseState":
            return {"marginSummary": {"accountValue": str(self.balance)}, "assetPositions":
                    [{"position": {"coin": "BTC", "szi": str(self.position)}}] if self.position else []}
        if kind == "openOrders":
            return list(self.orders.values())
        if kind == "orderStatus":
            oid = self.cloids.get(payload["oid"], payload["oid"])
            if oid == self.canceled_oid and self.cancel_lag:
                self.cancel_lag -= 1
                return {"status": "order", "order": {"status": "open"}}
            return {"status": "order", "order": {"status": self.statuses[oid]}} if oid in self.statuses else {"status": "unknownOid"}
        if kind == "userFillsByTime":
            return [] if self.hide_fills else self.fills
        raise AssertionError("Unexpected read-only API operation")

    def exchange(self, payload):
        action = payload["action"]
        recovered = recover_agent_or_user_from_l1_action(
            action, payload["signature"], payload["vaultAddress"], payload["nonce"], payload["expiresAfter"], False)
        assert recovered.lower() == self.owner.lower()
        self.actions.append(action)
        if action["type"] == "cancel":
            oid = action["cancels"][0]["o"]
            assert action["cancels"][0]["a"] == 3
            del self.orders[oid]
            self.statuses[oid] = "canceled"
            self.canceled_oid = oid
            status = "success"
        else:
            assert action["type"] == "order"
            order = action["orders"][0]
            assert order["a"] == 3
            oid, self.next_oid = self.next_oid, self.next_oid + 1
            self.cloids[order["c"]] = oid
            if order["t"]["limit"]["tif"] == "Alo":
                assert D(order["p"]) < D(79999)
                self.orders[oid] = {"coin": "BTC", "oid": oid}
                self.statuses[oid] = "open"
                if self.timeout_maker:
                    raise requests.Timeout("Accepted, but response lost")
                status = {"resting": {"oid": oid}}
            else:
                assert order["t"]["limit"]["tif"] == "Ioc"
                size = D(order["s"])
                if self.partial_entry and not order["r"] or self.partial_close and order["r"]:
                    size = (size / 2).quantize(D("0.00001"), rounding=ROUND_DOWN)
                if order["r"]:
                    assert not order["b"] and 0 < size <= self.position
                self.position += size if order["b"] else -size
                self.statuses[oid] = "filled"
                self.fills.append({"coin": "BTC", "oid": oid, "side": "B" if order["b"] else "A",
                                   "sz": str(size), "px": order["p"], "fee": "0.01", "feeToken": "USDC", "time": now_ms()})
                status = {"filled": {"oid": oid, "totalSz": str(size), "avgPx": order["p"]}}
        return {"status": "ok", "response": {"type": action["type"], "data": {"statuses": [status]}}}


@pytest.fixture
def setup(monkeypatch, tmp_path):
    key_path, pass_path = tmp_path / "test.keystore.json", tmp_path / "unlock.pass"
    pass_path.write_text("offline-test-password-only")
    pass_path.chmod(0o600)
    wallet = create_wallet(key_path, pass_path.read_text())
    server = OfflineExchangeServer(wallet["address"])
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    monkeypatch.setattr(requests.Session, "request", lambda self, method, url, **kw: server.request(method, url, **kw))
    monkeypatch.setattr("btc_perp_bot.smoke.time.sleep", lambda _: None)
    args = ["testnet-smoke", "--account", wallet["address"], "--keystore", str(key_path),
            "--password-file", str(pass_path), "--output-dir", str(tmp_path / "runs")]
    return server, args


def no_unlock(*args, **kwargs):
    raise AssertionError("Readiness checking must not open a private key")


def test_default_only_reads_even_with_wallet_present(setup, monkeypatch, capsys):
    server, args = setup
    monkeypatch.setattr(cli, "load_wallet", no_unlock)
    assert cli.main(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "ready_check_only"
    assert report["signed_requests"] == 0 and not server.actions


def test_unfunded_execute_stops_before_unlock_or_exchange(setup, monkeypatch, capsys):
    server, args = setup
    server.balance = D(0)
    monkeypatch.setattr(cli, "load_wallet", no_unlock)
    assert cli.main(args + ["--execute-testnet-orders"]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "blocked"
    assert report["precheck"]["blockers"] == ["insufficient_testnet_collateral"]
    assert server.requests and set(server.requests) == {"info"}


def test_real_sdk_http_serialization_full_smoke_with_delayed_cancel_visibility(setup, capsys):
    server, args = setup
    assert cli.main(args + ["--execute-testnet-orders"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "completed"
    assert [x["type"] for x in server.actions] == ["order", "cancel", "order", "order"]
    assert len(server.fills) == 2 and server.position == 0 and not server.orders
    assert server.actions[-1]["orders"][0]["r"] is True
    assert server.cancel_lag == 0  # Delayed observation doesn't resend the cancellation.
    assert report["fills"] == [{k: f[k] for k in ("oid", "side", "sz", "px", "fee", "feeToken", "time")} for f in server.fills]


def test_partial_entry_closes_only_confirmed_quantity(setup, capsys):
    server, args = setup
    server.partial_entry = True
    assert cli.main(args + ["--execute-testnet-orders"]) == 0
    report = json.loads(capsys.readouterr().out)
    entry = server.actions[2]["orders"][0]
    close = server.actions[3]["orders"][0]
    assert D(close["s"]) == D(report["filled_size"]) < D(entry["s"])
    assert server.position == 0


def test_partial_close_does_not_claim_success_or_send_another_order(setup, capsys):
    server, args = setup
    server.partial_close = True
    assert cli.main(args + ["--execute-testnet-orders"]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "failed" and "partial" in report["error"]
    assert server.position > 0 and len(server.actions) == 4


def test_missing_exchange_fill_history_is_not_claimed_as_proof(setup, capsys):
    server, args = setup
    server.hide_fills = True
    assert cli.main(args + ["--execute-testnet-orders"]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "failed" and "fill history" in report["error"]
    assert server.position == 0 and len(server.actions) == 4


def test_accepted_maker_with_lost_response_blocks_rerun(setup, capsys):
    server, args = setup
    server.timeout_maker = True
    assert cli.main(args + ["--execute-testnet-orders"]) == 2
    first = json.loads(capsys.readouterr().out)
    assert first["status"] == "failed" and "unknown" in first["error"]
    assert len(server.orders) == len(server.actions) == 1
    assert cli.main(args + ["--execute-testnet-orders"]) == 2
    second = json.loads(capsys.readouterr().out)
    assert "unresolved_order_journal" in second["precheck"]["blockers"]
    assert len(server.actions) == 1  # No cleanup cancel or duplicate order after an ambiguous result.


def test_existing_order_blocks_before_wallet_unlock(setup, monkeypatch, capsys):
    server, args = setup
    server.orders[99] = {"coin": "BTC", "oid": 99}
    monkeypatch.setattr(cli, "load_wallet", no_unlock)
    assert cli.main(args + ["--execute-testnet-orders"]) == 2
    assert "existing_open_orders" in json.loads(capsys.readouterr().out)["precheck"]["blockers"]
    assert not server.actions


@pytest.mark.parametrize("network,url", [("mainnet", "https://api.hyperliquid.xyz"), ("testnet", "https://example.invalid")])
def test_smoke_cannot_be_retargeted_to_mainnet_or_other_endpoint(network, url):
    market = Market(network)
    market.url = url
    with pytest.raises(BotError, match="only supports"):
        prepare(market, "0x" + "1" * 40)
