from decimal import Decimal

from .core import BotError, number, positive, size_for


class PaperBroker:
    """Fresh, bounded simulation per run; never sends a signed request."""

    def __init__(self, cash="1000", fee_bps="4.5", slippage_bps="1", max_orders=8):
        self.cash = positive(cash)
        self.initial = self.cash
        self.position = Decimal(0)
        self.entry = Decimal(0)
        self.realized = Decimal(0)
        self.fees = Decimal(0)
        self.fee_rate = number(fee_bps) / 10000
        self.slippage = number(slippage_bps) / 10000
        if not 0 <= self.fee_rate < 1 or not 0 <= self.slippage < 1 or max_orders < 1:
            raise BotError("Invalid simulation costs or order limit")
        self.fills = []
        self.max_orders = max_orders

    def equity(self, quote):
        return self.cash + self.position * (quote.mid - self.entry)

    def _fill(self, quantity, quote):
        quote.validate()
        price = quote.ask * (1 + self.slippage) if quantity > 0 else quote.bid * (1 - self.slippage)
        realized = Decimal(0)
        if self.position:
            if quantity != -self.position:
                raise BotError("Paper close must close the whole position")
            realized = self.position * (price - self.entry)
        else:
            self.entry = price
        fee = abs(quantity) * price * self.fee_rate
        self.cash += realized - fee
        self.realized += realized
        self.fees += fee
        self.position += quantity
        if not self.position:
            self.entry = Decimal(0)
        self.fills.append({"mode": "paper", "time": quote.timestamp, "side": "buy" if quantity > 0 else "sell",
                           "size": str(abs(quantity)), "price": str(price), "fee": str(fee),
                           "realized_pnl_before_fee": str(realized), "position_after": str(self.position)})

    def set_target(self, direction, quote, notional, decimals):
        if direction not in (-1, 0, 1):
            raise BotError("Invalid target direction")
        current_direction = (self.position > 0) - (self.position < 0)
        if current_direction == direction:
            return
        if self.position:
            self._fill(-self.position, quote)
        if direction and len(self.fills) < self.max_orders:
            if positive(notional) > self.equity(quote):
                raise BotError("Paper entry would exceed 1x account exposure")
            self._fill(direction * size_for(notional, quote, decimals), quote)

    def summary(self, quote):
        return {"mode": "paper", "initial_equity": str(self.initial), "equity": str(self.equity(quote)),
                "net_pnl": str(self.equity(quote) - self.initial), "fees": str(self.fees),
                "position_btc": str(self.position), "fill_count": len(self.fills),
                "funding_modelled": False, "liquidation_modelled": False,
                "disclaimer": "Execution smoke test, not a profitability backtest; no real fills"}
