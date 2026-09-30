from decimal import Decimal, ROUND_DOWN

from ..core import BotError, number, positive

ZERO = Decimal(0)
ONE = Decimal(1)


class Account:
    """USDC linear-perp ledger shared by historical and forward simulations."""

    decimal_fields = ("initial", "cash", "position", "entry", "fees", "funding", "gross_pnl",
                      "peak", "drawdown", "trade_net", "winning_pnl", "losing_pnl", "turnover")

    def __init__(self, cash, state=None):
        for field in self.decimal_fields:
            setattr(self, field, ZERO)
        self.initial = self.cash = self.peak = positive(cash)
        self.halted = False
        self.halt_reason = None
        self.fill_count = self.trade_count = self.wins = self.entry_time = 0
        self.events = []
        if state is not None:
            for key in self.decimal_fields:
                setattr(self, key, number(state[key]))
            for key in ("halted", "halt_reason", "fill_count", "trade_count", "wins", "entry_time"):
                setattr(self, key, state[key])
            if self.initial != positive(cash):
                raise BotError("Virtual account starting cash mismatch")

    @property
    def direction(self):
        return (self.position > 0) - (self.position < 0)

    def equity(self, mark):
        return self.cash + self.position * (positive(mark) - self.entry)

    def observe(self, mark, max_drawdown=None):
        equity = self.equity(mark)
        self.peak = max(self.peak, equity)
        dd = (self.peak - equity) / self.peak
        self.drawdown = max(self.drawdown, dd)
        if equity <= 0 or (max_drawdown is not None and dd >= number(max_drawdown)):
            self.halted = True
            self.halt_reason = "nonpositive_equity" if equity <= 0 else "drawdown_stop"
        return equity

    def apply_funding(self, timestamp, rate, reference):
        if not self.position:
            return
        payment = -self.position * positive(reference) * number(rate)
        self.cash += payment
        self.funding += payment
        self.trade_net += payment
        self.events.append({"kind": "funding", "time": timestamp, "cashflow": str(payment),
                            "rate": str(rate), "reference_price": str(reference), "reference_is_proxy": True})

    def fill(self, timestamp, signed_qty, price, fee_bps, reason):
        qty, price = number(signed_qty), positive(price)
        if qty == 0:
            return
        # One open position, no pyramiding. Partial exits are allowed, flips use two fills.
        if self.position and (self.position * qty > 0 or abs(qty) > abs(self.position)):
            raise BotError("Invalid simulated fill: pyramid or over-close")
        fee = abs(qty) * price * number(fee_bps) / 10000
        realized = ZERO
        opening = self.position == 0
        if opening:
            self.entry = price
            self.entry_time = timestamp
            self.trade_net = -fee
        else:
            realized = -qty * (price - self.entry)
            self.trade_net += realized - fee
        self.cash += realized - fee
        self.fees += fee
        self.gross_pnl += realized
        self.turnover += abs(qty) * price
        self.position += qty
        self.fill_count += 1
        self.events.append({"kind": "fill", "time": timestamp, "side": "buy" if qty > 0 else "sell",
                            "size": str(abs(qty)), "price": str(price), "fee": str(fee),
                            "gross_realized": str(realized), "position_after": str(self.position),
                            "reason": reason, "opening": opening})
        if not self.position:
            self.trade_count += 1
            self.wins += int(self.trade_net > 0)
            self.winning_pnl += max(ZERO, self.trade_net)
            self.losing_pnl += min(ZERO, self.trade_net)
            self.events.append({"kind": "round_trip", "time": timestamp, "entry_time": self.entry_time,
                                "net_pnl": str(self.trade_net)})
            self.entry = ZERO
            self.entry_time = 0
            self.trade_net = ZERO

    def state(self):
        return {**{key: str(getattr(self, key)) for key in self.decimal_fields},
                **{key: getattr(self, key) for key in ("halted", "halt_reason", "fill_count", "trade_count", "wins", "entry_time")}}

    def metrics(self, mark):
        equity = self.equity(mark)
        return {"initial_equity": str(self.initial), "equity": str(equity),
                "net_pnl": str(equity - self.initial), "return_pct": str((equity / self.initial - 1) * 100),
                "max_drawdown_pct": str(self.drawdown * 100), "fees": str(self.fees),
                "current_drawdown_pct": str((self.peak - equity) / self.peak * 100),
                "funding_cashflow": str(self.funding), "gross_realized": str(self.gross_pnl),
                "unrealized": str(equity - self.cash), "position_btc": str(self.position),
                "fill_count": self.fill_count, "round_trips": self.trade_count,
                "win_rate_pct": str(number(self.wins) / self.trade_count * 100) if self.trade_count else None,
                "profit_factor": str(self.winning_pnl / -self.losing_pnl) if self.losing_pnl else None,
                "turnover_usdc": str(self.turnover), "halted": self.halted, "halt_reason": self.halt_reason}


def entry_size(account, mark, config, decimals, price_padding_bps):
    # Fee and allowed execution-price padding included, so opening notional / post-fee
    # equity cannot exceed the requested entry exposure (<= 1) even with full exposure.
    equity = account.equity(mark)
    if equity <= 0:
        return ZERO
    fraction = number(config.exposure)
    price_bound = positive(mark) * (1 + number(price_padding_bps) / 10000)
    immediate_cost = price_bound * number(config.fee_bps) / 10000 + price_bound - positive(mark)
    size = (equity * fraction / (price_bound + fraction * immediate_cost)).quantize(
        Decimal(10) ** -decimals, rounding=ROUND_DOWN)
    return size if size * positive(mark) >= 10 else ZERO


def change_target(account, direction, mark, timestamp, config, decimals, execution, price_padding_bps):
    """execution(signed_quantity) -> (positive filled quantity, VWAP)."""
    if direction not in (-1, 0, 1):
        raise BotError("Invalid target")
    direction = 0 if account.halted else direction
    if direction == account.direction:
        return
    if account.position:
        sign = -account.direction
        wanted = abs(account.position)
        got, price = execution(sign * wanted)
        if got:
            account.fill(timestamp, sign * got, price, config.fee_bps, "risk_stop" if account.halted else "target_exit")
        if got < wanted:
            account.events.append({"kind": "unfilled", "time": timestamp, "reason": "partial_or_unfilled_exit",
                                   "requested": str(wanted), "filled": str(got)})
        if account.position:
            return  # Never open the opposite side while a close is incomplete.
    if direction:
        size = entry_size(account, mark, config, decimals, price_padding_bps)
        if not size:
            account.events.append({"kind": "unfilled", "time": timestamp, "reason": "below_minimum_notional"})
            return
        got, price = execution(direction * size)
        if got:
            account.fill(timestamp, direction * got, price, config.fee_bps, "signal_entry")
        if got < size:
            account.events.append({"kind": "unfilled", "time": timestamp, "reason": "partial_or_unfilled_entry",
                                   "requested": str(size), "filled": str(got)})


def bar_execution(price, config):
    impact = (number(config.half_spread_bps) + number(config.slippage_bps)) / 10000

    def fill(qty):
        return abs(qty), positive(price) * (1 + impact if qty > 0 else 1 - impact)

    return fill


def book_execution(book, config):
    # Each strategy gets its own hypothetical book; shared-market impact is not modelled.
    # Within one strategy tick, consume a level only once.
    available = {side: [[number(p), number(q)] for p, q in book[side]] for side in ("bids", "asks")}
    limit_bps = number(config.max_book_slippage_bps) / 10000
    extra = number(config.slippage_bps) / 10000

    def fill(qty):
        levels = available["asks" if qty > 0 else "bids"]
        top = levels[0][0]
        limit = top * (1 + limit_bps if qty > 0 else 1 - limit_bps)
        remaining, total, value = abs(qty), ZERO, ZERO
        for level in levels:
            price = level[0] * (1 + extra if qty > 0 else 1 - extra)
            if (qty > 0 and price > limit) or (qty < 0 and price < limit):
                break
            take = min(remaining, level[1])
            total += take
            value += take * price
            remaining -= take
            level[1] -= take
            if remaining == 0:
                break
        return total, value / total if total else top

    return fill
