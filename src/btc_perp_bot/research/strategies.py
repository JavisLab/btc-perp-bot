from ..core import BotError, number
from .config import ALL_STRATEGIES, WARMUP

DESCRIPTIONS = {
    "trend": "추세 · 20/60시간 이동평균, 0.1% 중립 구간",
    "breakout": "돌파 · 직전 24시간 고가/저가 돌파, 반대 돌파까지 유지",
    "mean_reversion": "평균회귀 · 직전 48시간 평균 대비 2σ 진입, 0.3σ 복귀 청산",
    "cash": "현금 유지 · 매매 없음",
    "buy_hold": "BTC 선물 매수 후 보유 · 동일 노출/수수료/펀딩, 전략 손실중단 제외",
}


def target(name, closed_candles, current_direction=0):
    if name not in ALL_STRATEGIES:
        raise BotError("Unknown research strategy")
    if name == "cash":
        return 0
    if len(closed_candles) < WARMUP:
        return 0
    if name == "buy_hold":
        return 1
    closes = [number(x["c"]) for x in closed_candles[-WARMUP:]]
    if name == "trend":
        fast, slow = sum(closes[-20:]) / 20, sum(closes[-60:]) / 60
        return 1 if fast > slow * number("1.001") else -1 if fast < slow * number("0.999") else 0
    last = closes[-1]
    if name == "breakout":
        preceding = closed_candles[-25:-1]
        upper = max(number(x["h"]) for x in preceding)
        lower = min(number(x["l"]) for x in preceding)
        return 1 if last > upper else -1 if last < lower else current_direction
    preceding = closes[-49:-1]
    mean = sum(preceding) / 48
    deviation = (sum((x - mean) ** 2 for x in preceding) / 48).sqrt()
    if deviation == 0:
        return 0
    z = (last - mean) / deviation
    if current_direction == 1 and z >= number("-0.3"):
        return 0
    if current_direction == -1 and z <= number("0.3"):
        return 0
    if current_direction:
        return current_direction
    return -1 if z >= 2 else 1 if z <= -2 else 0
