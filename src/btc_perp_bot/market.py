import requests
from eth_utils import is_address, to_checksum_address

from .core import BotError, Quote, now_ms, number, positive

ENDPOINTS = {
    "mainnet": "https://api.hyperliquid.xyz",
    "testnet": "https://api.hyperliquid-testnet.xyz",
}


def address(value):
    if not is_address(value):
        raise BotError("Invalid EVM account address")
    return to_checksum_address(value)


class Market:
    def __init__(self, network="mainnet"):
        if network not in ENDPOINTS:
            raise BotError("Unknown network")
        self.network = network
        self.url = ENDPOINTS[network]
        self.session = requests.Session()
        self._meta = None

    def info(self, payload):
        try:
            response = self.session.post(self.url + "/info", json=payload, timeout=10, allow_redirects=False)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            raise BotError("Public/account API request failed; no order sent by this request") from exc

    def meta(self):
        if self._meta is None:
            self._meta = self.info({"type": "meta"})
        return self._meta

    def btc_meta(self):
        for index, item in enumerate(self.meta()["universe"]):
            if item["name"] == "BTC" and not item.get("isDelisted", False):
                return index, item
        raise BotError("BTC market is unavailable")

    def quote(self):
        result = self.info({"type": "l2Book", "coin": "BTC"})
        try:
            if result["coin"] != "BTC":
                raise ValueError("Unexpected market")
            quote = Quote(positive(result["levels"][0][0]["px"]), positive(result["levels"][1][0]["px"]), int(result["time"]))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise BotError("Missing or invalid BTC order book") from exc
        quote.validate()
        return quote

    def closes(self, count=20):
        current = now_ms()
        result = self.info({"type": "candleSnapshot", "req": {
            "coin": "BTC", "interval": "1m", "startTime": current - (count + 3) * 60000, "endTime": current,
        }})
        closed = sorted((x for x in result if x["T"] < current), key=lambda x: x["t"])
        closed = list({x["t"]: x for x in closed}.values())[-count:]
        if not closed or current - closed[-1]["T"] > 120000:
            raise BotError("Closed candles are stale or missing")
        if any(b["t"] - a["t"] != 60000 for a, b in zip(closed, closed[1:])):
            raise BotError("Gap in candle history")
        return [positive(x["c"]) for x in closed]

    def account(self, account_address):
        return self.info({"type": "clearinghouseState", "user": address(account_address)})

    def open_orders(self, account_address):
        return self.info({"type": "openOrders", "user": address(account_address)})

    def order_status(self, account_address, oid):
        return self.info({"type": "orderStatus", "user": address(account_address), "oid": oid})

    def fills_since(self, account_address, start_time):
        return self.info({"type": "userFillsByTime", "user": address(account_address),
                          "startTime": start_time, "aggregateByTime": False})


def btc_position(state):
    for item in state["assetPositions"]:
        if item["position"]["coin"] == "BTC":
            return number(item["position"]["szi"])
    return number(0)
