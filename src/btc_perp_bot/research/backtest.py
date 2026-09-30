from dataclasses import replace

from ..core import BotError, number
from .config import ALL_STRATEGIES, HOUR, MODEL_VERSION, PRESETS, WARMUP, digest, source_digest, utc
from .engine import Account, bar_execution, change_target
from .strategies import DESCRIPTIONS, target

LIMITATIONS = [
    "과거 자료에 대한 가상 결과이며 실거래 수익·체결 보장이 아닙니다.",
    "펀딩률은 실제 기록, 펀딩 명목금액은 직전 시간봉 거래 종가 추정값입니다. 당시 oracle 가격이 아닙니다.",
    "과거 펀딩은 시간 경계에서 이전 포지션에 정산한 후 새 봉 주문을 체결하는 시간봉 모형입니다. 실제 밀리초 순서를 복원하지 않습니다.",
    "과거 스프레드·슬리피지는 가정값입니다. 주문장 깊이/대기열/봉내 체결 경로/정확한 강제청산은 복원하지 않습니다.",
    "진입 시 명목 노출을 제한합니다. 보유 중 가격 변동으로 실제 명목노출/평가자산 비율이 변합니다.",
    "낙폭·손실중단은 관측 시점 기준이며 봉 사이 급변에서 설정 한도를 초과할 수 있습니다.",
    "평가 결과를 보고 전략을 수정하면 이 평가 구간은 더 이상 미사용 데이터가 아닙니다.",
    "현재 거래 단위와 고정 기본 수수료를 과거에도 적용했습니다. 과거 제도 변화/세금/운영비/환율은 미반영입니다.",
    "BTC 보유 비교는 현물이 아닌 동일 노출의 선물 보유이며 수수료와 펀딩을 포함합니다.",
]


def period_returns(curve, initial):
    days, months = {}, {}
    previous = number(initial)
    for point in curve:
        stamp = utc(point["time"] - 1)
        for groups, key in ((days, stamp[:10]), (months, stamp[:7])):
            groups.setdefault(key, [previous, previous])[1] = number(point["equity"])
        previous = number(point["equity"])
    return {"daily": {k: str((end / start - 1) * 100) if start > 0 else None for k, (start, end) in days.items()},
            "monthly": {k: str((end / start - 1) * 100) if start > 0 else None for k, (start, end) in months.items()}}


def simulate(data, name, start_index, end_index, config, extra_delay=0):
    candles = data["candles"]
    if start_index < WARMUP + extra_delay or end_index <= start_index:
        raise BotError("Insufficient warm-up or evaluation range")
    rates = {x["time"]: x for x in data["funding"]}
    account = Account(config.cash)
    curve, decisions = [], []
    padding = number(config.half_spread_bps) + number(config.slippage_bps)
    active_bars = 0
    for i in range(start_index, end_index):
        bar = candles[i]
        opening, close = number(bar["o"]), number(bar["c"])
        # Previous bar's funding has already been settled. Account is flat on a new split.
        stop = config.max_drawdown if name in PRESETS else None
        account.observe(opening, stop)
        visible_end = i - extra_delay
        history = candles[max(0, visible_end - WARMUP):visible_end]
        wanted = target(name, history, account.direction)
        change_target(account, wanted, opening, bar["t"], config, data["metadata"]["sz_decimals"],
                      bar_execution(opening, config), padding)
        decisions.append({"time": bar["t"], "last_signal_bar": history[-1]["t"], "target": wanted})
        active_bars += int(bool(account.position))
        boundary = bar["t"] + HOUR
        # settle for the position held through this hour, before next-hour fills
        account.apply_funding(boundary, rates[boundary]["rate"], close)
        equity = account.observe(close, stop)
        curve.append({"time": boundary, "equity": str(equity), "position": str(account.position),
                      "drawdown_pct": str((account.peak - equity) / account.peak * 100)})
    last = candles[end_index - 1]
    # Every backtest split ends flat; cost of this artificial exit is included.
    change_target(account, 0, number(last["c"]), last["t"] + HOUR, config,
                  data["metadata"]["sz_decimals"], bar_execution(last["c"], config), padding)
    equity = account.observe(number(last["c"]))
    curve[-1].update(equity=str(equity), position="0", drawdown_pct=str((account.peak - equity) / account.peak * 100))
    metrics = account.metrics(last["c"])
    periods = period_returns(curve, config.cash)
    day_values = [number(x) for x in periods["daily"].values() if x is not None]
    month_values = [number(x) for x in periods["monthly"].values() if x is not None]
    metrics.update(worst_day_pct=str(min(day_values)), worst_month_pct=str(min(month_values)),
                   exposure_time_pct=str(number(active_bars) / (end_index - start_index) * 100))
    return {"strategy": name, "description": DESCRIPTIONS[name], "metrics": metrics,
            "start": utc(candles[start_index]["t"]), "end": utc(last["t"] + HOUR),
            "bars": end_index - start_index, "curve": curve, "events": account.events,
            "decisions": decisions, "period_returns": periods}


def compare(data, config):
    if any(number(getattr(config, key)) > 500 for key in ("fee_bps", "half_spread_bps", "slippage_bps")):
        raise BotError("Base execution costs must be <=500 bps to allow the 2x stress case")
    candles = data["candles"]
    first = WARMUP + 1  # Equal starts for base and additional-one-bar delay stress.
    split = first + int((len(candles) - first) * number(config.train_fraction))
    if split - first < 48 or len(candles) - split < 48:
        raise BotError("Need at least 48 hourly bars in each split after warm-up")
    training = {name: simulate(data, name, first, split, config) for name in ALL_STRATEGIES}
    # This selection never reads any holdout results.
    selected = max(PRESETS, key=lambda name: number(training[name]["metrics"]["net_pnl"]))
    evaluation = {name: simulate(data, name, split, len(candles), config) for name in ALL_STRATEGIES}
    expensive = replace(config, **{key: str(number(getattr(config, key)) * 2)
                                  for key in ("fee_bps", "half_spread_bps", "slippage_bps")})
    stress = {}
    for name in ALL_STRATEGIES:
        stress[name] = {
            "double_execution_cost": simulate(data, name, split, len(candles), expensive)["metrics"],
            "extra_one_hour_delay": simulate(data, name, split, len(candles), config, extra_delay=1)["metrics"],
        }
    chosen = evaluation[selected]["metrics"]
    flags = []
    if number(chosen["net_pnl"]) <= 0:
        flags.append("selected_strategy_loses_on_holdout")
    if chosen["round_trips"] < 30:
        flags.append("fewer_than_30_closed_trades_in_holdout_not_a_statistical_threshold")
    if number(chosen["net_pnl"]) <= number(evaluation["buy_hold"]["metrics"]["net_pnl"]):
        flags.append("selected_strategy_does_not_beat_same_exposure_btc_perp_hold")
    if number(stress[selected]["double_execution_cost"]["net_pnl"]) <= 0:
        flags.append("selected_strategy_loses_with_double_execution_cost")
    if number(stress[selected]["extra_one_hour_delay"]["net_pnl"]) <= 0:
        flags.append("selected_strategy_loses_with_extra_delay")
    result = {"version": MODEL_VERSION, "kind": "historical_backtest", "config": config.to_dict(),
              "source_sha256": source_digest(), "dataset_sha256": data["sha256"],
              "dataset": {k: v for k, v in data.items() if k not in ("candles", "funding")},
              "split": {"warmup_bars": first, "training_start": training[selected]["start"],
                        "holdout_start": evaluation[selected]["start"], "end": evaluation[selected]["end"]},
              "selection_rule": "Highest training net PnL among the three fixed presets; no holdout tuning",
              "selected": selected, "flags": flags, "limitations": LIMITATIONS,
              "training": training, "holdout": evaluation, "stress": stress}
    result["experiment_sha256"] = digest({k: result[k] for k in ("config", "dataset_sha256", "source_sha256", "split")})
    return result
