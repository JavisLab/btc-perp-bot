"""Bounded testnet acceptance check, never a mainnet strategy or faucet bypass."""

import time
from decimal import Decimal, ROUND_DOWN

from .core import BotError, now_ms, number, positive
from .market import ENDPOINTS, btc_position


def testnet_only(market):
    if market.network != "testnet" or market.url != ENDPOINTS["testnet"]:
        raise BotError("This acceptance check only supports the official testnet endpoint")


def prepare(market, owner, notional="25"):
    testnet_only(market)
    notional = positive(notional)
    if not Decimal(12) <= notional <= Decimal(100):
        raise BotError("Testnet smoke notional must be between 12 and 100 mock USDC")
    state = market.account(owner)
    orders = market.open_orders(owner)
    asset_id, spec = market.btc_meta()
    quote = market.quote()
    quote.validate()
    # Reserve 1% of the cap for rounding/quote changes. Each send rechecks the cap.
    size = (notional * Decimal("0.99") / quote.ask).quantize(
        Decimal(10) ** -spec["szDecimals"], rounding=ROUND_DOWN)
    # Integer perp prices are valid irrespective of the five-significant-figure rule.
    maker_price = (quote.bid * Decimal("0.99")).to_integral_value(rounding=ROUND_DOWN)
    equity = number(state["marginSummary"]["accountValue"])
    blockers = []
    if equity < notional:
        blockers.append("insufficient_testnet_collateral")
    if any(number(x["position"]["szi"]) for x in state["assetPositions"]):
        blockers.append("account_not_flat")
    if orders:
        blockers.append("existing_open_orders")
    if maker_price <= 0 or size <= 0 or size * maker_price < 10:
        blockers.append("rounded_order_below_exchange_minimum")
    return {"network": "testnet", "ready": not blockers, "blockers": blockers,
            "account_value": str(equity), "open_order_count": len(orders),
            "btc_position": str(btc_position(state)), "btc_asset_id": asset_id,
            "bid": str(quote.bid), "ask": str(quote.ask), "quote_time": quote.timestamp,
            "notional_cap": str(notional), "size": str(size), "maker_price": str(maker_price)}


def wait_read(label, query, matches, *, attempts=12, pause=0.25):
    """Retry observations only, never mutations. Fail closed if evidence is missing."""
    for attempt in range(attempts):
        value = query()
        if matches(value):
            return value
        if attempt + 1 < attempts:
            time.sleep(pause)
    raise BotError(f"Could not confirm {label}; stop and inspect orders/positions, do not replay")


def order_is(value, expected):
    return value.get("status") == "order" and value.get("order", {}).get("status") == expected


def fill_details(result, maximum):
    detail = result.get("status", {}).get("filled")
    if not isinstance(detail, dict):
        raise BotError("IOC fill was not acknowledged; stop and inspect the journal")
    size = positive(detail["totalSz"])
    if size > maximum or not isinstance(detail["oid"], int):
        raise BotError("Unexpected fill size or order id")
    return size, detail["oid"]


def execute(broker, record, *, attempts=12, pause=0.25):
    market, owner = broker.market, broker.account_address
    testnet_only(market)
    started = now_ms() - 60000  # History window accommodates small host clock skew.
    wait_options = {"attempts": attempts, "pause": pause}
    broker.preflight(require_flat=True)
    plan = prepare(market, owner, broker.max_notional)
    if not plan["ready"]:
        raise BotError("Testnet account is not ready: " + ", ".join(plan["blockers"]))

    record({"step": "maker_order", "phase": "before_request"})
    placed = broker.order("buy", plan["size"], plan["maker_price"], "Alo")
    resting = placed.get("status", {}).get("resting")
    if not isinstance(resting, dict) or not isinstance(resting.get("oid"), int):
        raise BotError("Maker order did not rest; inspect account before continuing")
    maker_oid = resting["oid"]
    wait_read("resting order", lambda: market.order_status(owner, placed["cloid"]),
              lambda result: order_is(result, "open"), **wait_options)
    record({"step": "maker_order", "phase": "confirmed", "oid": maker_oid, "cloid": placed["cloid"]})

    record({"step": "cancel", "phase": "before_request", "oid": maker_oid})
    broker.cancel(maker_oid)
    wait_read("cancellation", lambda: market.order_status(owner, maker_oid),
              lambda result: order_is(result, "canceled"), **wait_options)
    wait_read("empty open-order list", lambda: market.open_orders(owner), lambda value: not value, **wait_options)
    if btc_position(broker.state()):
        raise BotError("Maker order filled before cancellation; no additional entry sent")
    record({"step": "cancel", "phase": "confirmed", "oid": maker_oid})

    plan = prepare(market, owner, broker.max_notional)
    if not plan["ready"]:
        raise BotError("Account changed before IOC entry; stop and inspect")
    size = positive(plan["size"])
    record({"step": "entry", "phase": "before_request"})
    entry = broker.ioc(size, market.quote())
    filled, entry_oid = fill_details(entry, size)
    wait_read("entry position", broker.state, lambda state: btc_position(state) == filled, **wait_options)
    record({"step": "entry", "phase": "confirmed", "oid": entry_oid,
            "cloid": entry["cloid"], "size": str(filled)})

    # Close only the confirmed fill; partial entry fills are not treated as the requested size.
    record({"step": "close", "phase": "before_request", "reduce_only": True})
    closed = broker.ioc(-filled, market.quote(), reduce_only=True)
    close_size, close_oid = fill_details(closed, filled)
    if close_size != filled:
        raise BotError("Close was partial; position may remain, do not replay the test")
    wait_read("flat position", broker.state, lambda state: btc_position(state) == 0, **wait_options)
    wait_read("final empty open-order list", lambda: market.open_orders(owner), lambda value: not value, **wait_options)
    record({"step": "close", "phase": "confirmed", "oid": close_oid,
            "cloid": closed["cloid"], "size": str(close_size), "reduce_only": True})

    def fills_match(fills):
        for oid, side, quantity in ((entry_oid, "B", filled), (close_oid, "A", close_size)):
            matches = [f for f in fills if f["coin"] == "BTC" and f["oid"] == oid and f["side"] == side]
            if sum((positive(f["sz"]) for f in matches), Decimal(0)) != quantity:
                return False
        return True

    fills = wait_read("exchange fill history", lambda: market.fills_since(owner, started), fills_match, **wait_options)
    selected = [{k: f[k] for k in ("oid", "side", "sz", "px", "fee", "feeToken", "time")}
                for f in fills if f["coin"] == "BTC" and f["oid"] in {entry_oid, close_oid}]
    record({"step": "fill_history", "phase": "confirmed", "fills": selected})
    return {"status": "completed", "network": "testnet", "maker_oid": maker_oid,
            "entry_oid": entry_oid, "close_oid": close_oid, "filled_size": str(filled),
            "position_btc": "0", "open_order_count": 0, "fills": selected}
