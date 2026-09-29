import fcntl
import json
import os
import uuid
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

from hyperliquid.exchange import Exchange
from hyperliquid.utils.types import Cloid

from .core import BotError, now_ms, number, positive, private_dir, private_open, size_for
from .market import ENDPOINTS, address, btc_position


def execution_guard(network, enable_live=False):
    if network not in ENDPOINTS:
        raise BotError("Unknown execution network")
    if network == "mainnet" and not enable_live:
        raise BotError("Mainnet orders are disabled; only an operator may explicitly enable them")


@contextmanager
def account_lock(network, account_address, root=None):
    root = private_dir(root or Path.home() / ".local/share/btc-perp-bot/locks")
    path = root / f"{network}-{address(account_address).lower()}.lock"
    fd = private_open(path, os.O_RDWR | os.O_CREAT)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BotError("Another local process owns this trading account") from exc
        yield
    finally:
        os.close(fd)


class Journal:
    def __init__(self, path):
        self.path = Path(path).expanduser()
        private_dir(self.path.parent)
        fd = private_open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT)
        os.close(fd)

    def append(self, event):
        event = {"recorded_at": now_ms(), **event}
        with os.fdopen(private_open(self.path, os.O_WRONLY | os.O_APPEND), "a") as out:
            out.write(json.dumps(event, default=str) + "\n")
            out.flush()
            os.fsync(out.fileno())

    def unresolved(self):
        states = {}
        with os.fdopen(private_open(self.path, os.O_RDONLY), "r") as src:
            for line in src:
                try:
                    event = json.loads(line)
                    states[event["id"]] = event["state"]
                except (ValueError, KeyError) as exc:
                    raise BotError("Damaged order journal; stop and reconcile before trading") from exc
        return [key for key, value in states.items() if value == "prepared"]

    def pending_intent(self, identity):
        if identity not in self.unresolved():
            raise BotError("No unresolved intent with this id")
        with os.fdopen(private_open(self.path, os.O_RDONLY), "r") as src:
            for line in src:
                event = json.loads(line)
                if event["id"] == identity and event["state"] == "prepared":
                    return event
        raise BotError("Prepared intent not found")


def reconcile(market, owner, journal, identity):
    """Read exchange status and resolve a known outcome; never resubmit."""
    intent = journal.pending_intent(identity)
    if intent["network"] != market.network or address(intent["account"]) != address(owner):
        raise BotError("Journal account/network mismatch")
    oid = identity if intent["action"] == "order" else intent["oid"]
    result = market.order_status(owner, oid)
    status = result.get("order", {}).get("status") if result.get("status") == "order" else None
    terminal = status in {"filled", "canceled", "rejected"} or isinstance(status, str) and status.endswith("Canceled")
    known = terminal or intent["action"] == "order" and status == "open"
    if not known:
        raise BotError("Exchange outcome still unknown; journal remains blocked, no resend")
    journal.append({"id": identity, "state": "reconciled", "exchange_status": status})
    return {"id": identity, "exchange_status": status, "resubmitted": False,
            "next_step": "Check current positions and open orders before continuing"}


class ExchangeBroker:
    """Signed SDK order/cancel adapter. Nothing invokes it in paper mode."""

    def __init__(self, market, signer, account_address, journal, max_notional="25", max_orders=8,
                 slippage_bps="10", enable_live=False, exchange_factory=Exchange):
        execution_guard(market.network, enable_live)
        self.market = market
        self.account_address = address(account_address)
        self.journal = journal
        self.max_notional = positive(max_notional)
        self.slippage = positive(slippage_bps) / 10000
        if self.slippage > Decimal("0.01") or max_orders < 1:
            raise BotError("Slippage must be at most 1%; order count must be positive")
        self.max_orders = max_orders
        self.order_count = 0
        self.expected_position = None
        self.sdk = exchange_factory(signer, base_url=market.url, meta=market.meta(),
                                    account_address=self.account_address,
                                    spot_meta={"tokens": [], "universe": []}, timeout=10)

    def state(self):
        return self.market.account(self.account_address)

    def preflight(self, require_flat=False):
        if self.journal.unresolved():
            raise BotError("Uncertain previous request in journal; query order status before any resend")
        state = self.state()
        if number(state["marginSummary"]["accountValue"]) <= 0:
            raise BotError("Account has no perpetual collateral; no signed order sent")
        if require_flat:
            if any(number(x["position"]["szi"]) for x in state["assetPositions"]):
                raise BotError("Bot startup requires a flat, dedicated account")
            if self.market.open_orders(self.account_address):
                raise BotError("Bot startup requires no open orders")
            self.expected_position = Decimal(0)
        return state

    def _submit(self, intent, call):
        if self.journal.unresolved():
            raise BotError("Uncertain previous request; automatic retry is forbidden")
        self.journal.append({**intent, "state": "prepared", "network": self.market.network,
                             "account": self.account_address})
        try:
            result = call()
        except Exception as exc:
            # Leave PREPARED durable. A timeout does not prove rejection.
            raise BotError(f"Request outcome unknown. Do not resend. Check journal id {intent['id']}") from exc
        if not isinstance(result, dict) or result.get("status") not in {"ok", "err"}:
            raise BotError(f"Unrecognized exchange reply; reconcile journal id {intent['id']}")
        if result["status"] == "err":
            self.journal.append({"id": intent["id"], "state": "rejected", "response": result})
            raise BotError("Exchange rejected request; see journal")
        statuses = result.get("response", {}).get("data", {}).get("statuses")
        if not isinstance(statuses, list) or len(statuses) != 1:
            raise BotError(f"Unrecognized action status; reconcile journal id {intent['id']}")
        status = statuses[0]
        if isinstance(status, dict) and "error" in status:
            self.journal.append({"id": intent["id"], "state": "rejected", "response": result})
            raise BotError("Exchange rejected action; see journal")
        if not (status == "success" or isinstance(status, dict) and ("filled" in status or "resting" in status)):
            raise BotError(f"Ambiguous action status; reconcile journal id {intent['id']}")
        self.journal.append({"id": intent["id"], "state": "acknowledged", "response": result})
        return status

    def order(self, side, size, price, tif="Alo", reduce_only=False):
        if side not in {"buy", "sell"} or tif not in {"Alo", "Gtc", "Ioc"}:
            raise BotError("Invalid order side or time-in-force")
        size, price = positive(size), positive(price)
        _, spec = self.market.btc_meta()
        decimals = spec["szDecimals"]
        if size != size.quantize(Decimal(10) ** -decimals):
            raise BotError("Size violates BTC lot precision")
        if price != price.to_integral_value():
            if len(price.normalize().as_tuple().digits) > 5 or price != price.quantize(Decimal(10) ** -(6 - decimals)):
                raise BotError("Price violates perp tick precision")
        quote = self.market.quote()
        quote.validate()
        state = self.preflight()
        position = btc_position(state)
        if reduce_only:
            if not position or (side == "buy") != (position < 0) or size > abs(position):
                raise BotError("Reduce-only order must reduce an existing BTC position")
        else:
            if self.market.open_orders(self.account_address):
                raise BotError("Open orders already reserve exposure; reconcile or cancel before another entry")
            if any(x["position"]["coin"] != "BTC" and number(x["position"]["szi"]) for x in state["assetPositions"]):
                raise BotError("This prototype requires a dedicated BTC-only account")
            worst_exposure = abs(position + (size if side == "buy" else -size)) * max(price, quote.ask)
            if size * price > self.max_notional or worst_exposure > self.max_notional:
                raise BotError("Order would exceed the configured notional cap")
            if worst_exposure > number(state["marginSummary"]["accountValue"]):
                raise BotError("Order would exceed 1x account exposure")
            if self.order_count >= self.max_orders:
                raise BotError("Entry order budget exhausted")
        client_id = "0x" + uuid.uuid4().hex
        intent = {"id": client_id, "action": "order", "side": side, "size": str(size),
                  "price": str(price), "tif": tif, "reduce_only": reduce_only}
        status = self._submit(intent, lambda: self.sdk.order("BTC", side == "buy", float(size), float(price),
                              {"limit": {"tif": tif}}, reduce_only=reduce_only, cloid=Cloid.from_str(client_id)))
        self.order_count += 1
        return {"cloid": client_id, "status": status}

    def cancel(self, oid):
        if not isinstance(oid, int) or isinstance(oid, bool) or oid <= 0:
            raise BotError("Order id must be a positive integer")
        intent = {"id": "cancel-" + uuid.uuid4().hex, "action": "cancel", "oid": oid}
        return self._submit(intent, lambda: self.sdk.cancel("BTC", oid))

    def set_target(self, direction, quote, notional, decimals):
        state = self.state()
        position = btc_position(state)
        if self.expected_position is not None and position != self.expected_position:
            raise BotError("Position changed outside this bot; stop and reconcile")
        if self.market.open_orders(self.account_address):
            raise BotError("Unexpected open orders; stop and reconcile")
        if (position > 0) - (position < 0) == direction:
            return
        if position:
            self._ioc(-position, quote, reduce_only=True)
            remaining = btc_position(self.state())
            if remaining:
                raise BotError("Close incomplete; position remains, no reversal entry sent")
            self.expected_position = Decimal(0)
        if direction and self.order_count < self.max_orders:
            qty = direction * size_for(number(notional) / (1 + self.slippage), quote, decimals)
            result = self._ioc(qty, quote)
            status = result["status"]
            if "filled" not in status:
                raise BotError("Entry was not filled; inspect the order before restarting")
            actual = number(status["filled"]["totalSz"]) * direction
            if not 0 < abs(actual) <= abs(qty) or btc_position(self.state()) != actual:
                raise BotError("Fill/position mismatch; stop and reconcile")
            self.expected_position = actual

    def _ioc(self, signed_size, quote, reduce_only=False):
        quote.validate()
        buy = signed_size > 0
        raw_price = (quote.ask * (1 + self.slippage)) if buy else (quote.bid * (1 - self.slippage))
        decimals = self.market.btc_meta()[1]["szDecimals"]
        price = round(number(format(raw_price, ".5g")), 6 - decimals)
        return self.order("buy" if buy else "sell", abs(signed_size), price, "Ioc", reduce_only)
