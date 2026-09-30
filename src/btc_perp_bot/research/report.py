import csv
import html
import json
from pathlib import Path

from ..core import BotError, number
from .config import ALL_STRATEGIES, save_json, utc
from .strategies import DESCRIPTIONS

COLORS = {"trend": "#20c997", "breakout": "#59a7ff", "mean_reversion": "#c7a0ff", "cash": "#a4afbd", "buy_hold": "#ffba66"}


def esc(value):
    return html.escape(str(value), quote=True)


def fmt(value, places=2):
    return "—" if value is None else f"{number(value):,.{places}f}"


def table(accounts):
    headings = ("전략", "순손익 USDC", "수익률", "최대낙폭", "왕복거래", "승률", "수수료", "순펀딩", "상태")
    rows = []
    for name in ALL_STRATEGIES:
        m = accounts[name]["metrics"]
        color = "positive" if number(m["net_pnl"]) > 0 else "negative" if number(m["net_pnl"]) < 0 else ""
        rows.append(f'<tr><td><span style="color:{COLORS[name]}">●</span> {esc(DESCRIPTIONS[name].split(" · ")[0])}</td>'
                    f'<td class="{color}">{fmt(m["net_pnl"])}</td><td>{fmt(m["return_pct"])}%</td>'
                    f'<td>{fmt(m["max_drawdown_pct"])}%</td><td>{m["round_trips"]}</td>'
                    f'<td>{fmt(m["win_rate_pct"])}%</td><td>{fmt(m["fees"])}</td>'
                    f'<td>{fmt(m["funding_cashflow"])}</td><td>{"손실중단" if m["halted"] else "가상"}</td></tr>')
    return '<div class="table-wrap"><table><thead><tr>' + ''.join(f'<th>{x}</th>' for x in headings) + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'


def chart(accounts, initial, title, field="equity"):
    curves = {name: value["curve"] for name, value in accounts.items()}
    points = [p for curve in curves.values() for p in curve]
    if not points:
        return ""
    values = [float(p[field]) for p in points] + ([float(initial)] if field == "equity" else [0])
    low, high = min(values), max(values)
    pad = max((high - low) * .12, .1)
    low, high = low - pad, high + pad
    start, end = min(x["time"] for x in points), max(x["time"] for x in points)
    lines = []
    for j in range(5):
        y = 25 + j * 50
        value = high - j * (high - low) / 4
        lines.append(f'<path d="M75,{y}H945" stroke="#293542"/><text x="65" y="{y+4}" text-anchor="end">{value:,.2f}</text>')
    for name, curve in curves.items():
        stride = max(1, len(curve) // 700)
        displayed = curve[::stride]
        if displayed[-1] != curve[-1]:
            displayed.append(curve[-1])
        coords = ' '.join(f'{75 + (p["time"] - start) / max(1, end-start) * 870:.2f},{25 + (high-float(p[field])) / (high-low)*200:.2f}' for p in displayed)
        lines.append(f'<polyline data-series="{name}" points="{coords}" fill="none" stroke="{COLORS[name]}" stroke-width="2"/>')
    lines.append(f'<text x="75" y="252">{esc(utc(start)[:16])} UTC</text><text x="945" y="252" text-anchor="end">{esc(utc(end)[:16])} UTC</text>')
    return f'<section class="chart"><h3>{esc(title)}</h3><svg viewBox="0 0 980 270" role="img" aria-label="{esc(title)}">' + ''.join(lines) + '</svg></section>'


def render(result):
    historical = result["kind"] == "historical_backtest"
    accounts = result["holdout"] if historical else result["accounts"]
    config = result["config"]
    label = "과거 자료 · 시간순 분리 평가" if historical else "현재 메인넷 호가 · 실시간 모의계좌"
    date_range = f'{result["split"]["holdout_start"]} → {result["split"]["end"]}' if historical else f'{result["start"]} → {result["last_observation"]}'
    if historical:
        selected = result["selected"]
        title = f'개발 구간에서 선택한 후보: {DESCRIPTIONS[selected].split(" · ")[0]}'
        explanation = "개발 구간 순손익 1위로 선택했으며, 아래 수치는 선택에 사용하지 않은 후속 기간의 가상 성과입니다."
        m = accounts[selected]["metrics"]
        verdict = "평가 구간 순손실 — 실거래 전환 근거 없음" if number(m["net_pnl"]) <= 0 else "평가 구간 순이익 관측 — 실거래 수익 입증 아님"
    else:
        title = f'누적 {result["observed_ticks"]}회 관측 · 가상 계좌 5개'
        explanation = f'관측 공백 {result["gap_count"]}회, 오류/건너뛴 조회 {len(result["errors"])}회. 종료 시 가상 포지션은 보존됩니다.'
        verdict = "실제 거래소 주문 0 · 실제 자금 사용 0"
    legends = ''.join(f'<label><input type="checkbox" checked data-toggle="{n}"><span style="color:{COLORS[n]}">●</span> {esc(DESCRIPTIONS[n].split(" · ")[0])}</label>' for n in ALL_STRATEGIES)
    main = f'<section class="callout"><p class="eyebrow">{esc(verdict)}</p><h2>{esc(title)}</h2><p>{esc(explanation)}</p></section>'
    main += '<h2>평가 기간 성과</h2>' if historical else '<h2>가상 계좌 현재 상태</h2>'
    main += table(accounts) + f'<div class="legend">{legends}</div>'
    main += chart(accounts, config["cash"], "평가자산 곡선 · USDC")
    main += chart(accounts, config["cash"], "낙폭 · % (관측 시점 기준)", "drawdown_pct")
    if historical:
        main += '<h2>비용·지연 스트레스 · 같은 평가 기간</h2><div class="table-wrap"><table><thead><tr><th>전략</th><th>기본 순손익</th><th>거래비용 2배</th><th>체결 1시간 추가 지연</th></tr></thead><tbody>'
        for name in ALL_STRATEGIES:
            s = result["stress"][name]
            main += f'<tr><td>{esc(DESCRIPTIONS[name].split(" · ")[0])}</td><td>{fmt(accounts[name]["metrics"]["net_pnl"])}</td><td>{fmt(s["double_execution_cost"]["net_pnl"])}</td><td>{fmt(s["extra_one_hour_delay"]["net_pnl"])}</td></tr>'
        main += '</tbody></table></div><p class="muted">USDC 기준. 비용 2배는 수수료·가정 스프레드·슬리피지만 변경하고 펀딩률은 유지합니다.</p>'
        main += '<details><summary>개발 기간 성과 · 후보 선택에 사용한 자료</summary>' + table(result["training"]) + '</details>'
        main += '<details><summary>월별 평가 성과 · 처음/마지막 달은 부분 기간일 수 있음</summary><div class="table-wrap"><table><tr><th>전략</th><th>월</th><th>수익률</th></tr>'
        for name in ALL_STRATEGIES:
            for month, value in accounts[name]["period_returns"]["monthly"].items():
                main += f'<tr><td>{esc(name)}</td><td>{esc(month)}</td><td>{fmt(value)}%</td></tr>'
        main += '</table></div></details>'
    else:
        main += '<details><summary>가상 포지션과 미실현손익</summary><div class="table-wrap"><table><tr><th>전략</th><th>BTC 포지션</th><th>미실현손익 USDC</th></tr>'
        for name in ALL_STRATEGIES:
            m = accounts[name]["metrics"]
            main += f'<tr><td>{esc(name)}</td><td>{fmt(m["position_btc"], 5)}</td><td>{fmt(m["unrealized"])}</td></tr>'
        main += '</table></div></details>'
    main += '<section><h2>고정 조건과 해석</h2><ul>' + ''.join(f'<li>{esc(v)}</li>' for v in DESCRIPTIONS.values()) + '</ul>'
    main += f'<p>가상 시작 자산 {fmt(config["cash"])} USDC · 진입 목표 {fmt(number(config["exposure"])*100)}% · 편도 수수료 {esc(config["fee_bps"])}bp · 추가 슬리피지 {esc(config["slippage_bps"])}bp</p>'
    main += '<p class="muted">1bp = 0.01%. 순펀딩 양수는 수취, 음수는 지급입니다. 승률은 비용·펀딩 포함 완료 왕복거래 기준이며, Profit Factor에 손실 표본이 없으면 값을 만들지 않습니다. 차트는 표시용으로 줄여 그릴 수 있으나 지표는 전체 관측값으로 계산합니다.</p></section>'
    main += '<section class="limits"><h2>검증 범위와 한계</h2><ul>' + ''.join(f'<li>{esc(x)}</li>' for x in result["limitations"]) + '</ul></section>'
    main += '<details><summary>재현 정보 · 데이터/코드 지문</summary><pre>' + esc(json.dumps({k: result[k] for k in ("version", "source_sha256", "dataset_sha256", "experiment_sha256", "flags", "config") if k in result}, ensure_ascii=False, indent=2)) + '</pre></details>'
    return '''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BTC Strategy Lab · 모의검증 보고서</title><style>
:root{color-scheme:dark;font-family:system-ui,-apple-system,"Noto Sans CJK KR",sans-serif;background:#0c131c;color:#e2eaf3}*{box-sizing:border-box}body{margin:0}main{max-width:1160px;margin:auto;padding:40px 24px 70px}header{border-bottom:1px solid #2a3847;padding-bottom:26px;margin-bottom:28px}.brand{letter-spacing:3px;color:#20c997;font-size:12px;font-weight:750}h1{font-size:clamp(25px,4vw,40px);margin:14px 0}h2{font-size:20px;margin:28px 0 16px}h3{font-size:15px}.muted,header p,section p{color:#9dabbc;line-height:1.65}.tag{display:inline-block;padding:6px 10px;background:#19352f;color:#85e2c2;border-radius:6px;font-size:12px}.callout{background:#162432;border:1px solid #32475e;border-left:3px solid #59a7ff;border-radius:10px;padding:18px 22px}.callout h2{margin:8px 0}.eyebrow{font-size:13px;color:#ffce8e!important}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;font-size:13px}th,td{padding:13px 11px;border-bottom:1px solid #293542;white-space:nowrap;text-align:right}th:first-child,td:first-child{text-align:left}th{font-weight:600;color:#a7b8ca}tr:hover td{background:#152130}.positive{color:#5adcab}.negative{color:#ff9694}.chart{margin:20px 0;padding:14px 16px 0;background:#121e2a;border:1px solid #243342;border-radius:10px}.chart svg{width:100%;height:auto}.chart text{fill:#a4b3c4;font-size:12px}.legend{display:flex;gap:16px;flex-wrap:wrap;padding:20px 0 0;font-size:13px}.legend label{cursor:pointer}input{accent-color:#20c997}details{margin:20px 0;border:1px solid #293b4e;border-radius:8px;padding:15px}summary{cursor:pointer}pre{white-space:pre-wrap;word-break:break-word;font-size:12px;color:#9cbbd6}.limits{border-top:1px solid #293542;margin-top:30px}li{line-height:1.8;color:#b3c1d0;margin:5px 0}footer{font-size:12px;color:#8595a8;margin-top:30px}@media(max-width:600px){main{padding:25px 14px}.callout{padding:14px}.chart{padding:10px 2px}table{font-size:12px}h2{font-size:18px}}
</style></head><body><main><header><div class="brand">BTC STRATEGY LAB / RESEARCH V1</div><h1>수익성 검증 보고서</h1><span class="tag">PAPER ONLY · 실제 거래 없음</span><p>''' + esc(label) + '<br>' + esc(date_range) + '</p></header>' + main + '''<footer>BTC Perp Bot · 재현 가능한 모의 연구 환경. 수익 보장이나 투자 권유 자료가 아닙니다.</footer></main><script>
document.querySelectorAll('[data-toggle]').forEach(input=>input.addEventListener('change',()=>{document.querySelectorAll('[data-series="'+input.dataset.toggle+'"]').forEach(line=>line.style.display=input.checked?'':'none')}));
</script></body></html>'''


def write_report(result, directory, replace=False):
    directory = Path(directory)
    if directory.exists() and not replace:
        raise BotError("Report directory already exists; use a fresh experiment directory")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    save_json(directory / "results.json", result, replace=replace)
    # Report contains public market data + virtual balances only, never a wallet address/key.
    (directory / "report.html").write_text(render(result))
    groups = {"training": result["training"], "holdout": result["holdout"]} if result["kind"] == "historical_backtest" else {"paper": result["accounts"]}
    sample = next(iter(next(iter(groups.values())).values()))["metrics"]
    fields = list(sample)
    with (directory / "metrics.csv").open("w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=["period", "strategy"] + fields)
        writer.writeheader()
        for period, accounts in groups.items():
            for name, value in accounts.items():
                writer.writerow({"period": period, "strategy": name, **value["metrics"]})
    with (directory / "events.csv").open("w", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["period", "strategy", "time_utc", "kind", "details_json"])
        for period, accounts in groups.items():
            for name, value in accounts.items():
                for event in value["events"]:
                    writer.writerow([period, name, utc(event["time"]), event["kind"], json.dumps(event, ensure_ascii=False)])
    with (directory / "equity.csv").open("w", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["period", "strategy", "time_utc", "equity", "drawdown_pct"])
        for period, accounts in groups.items():
            for name, value in accounts.items():
                for point in value["curve"]:
                    writer.writerow([period, name, utc(point["time"]), point["equity"], point["drawdown_pct"]])
    return {"report": str(directory / "report.html"), "results": str(directory / "results.json")}
