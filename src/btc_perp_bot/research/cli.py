import argparse
import json
import sqlite3
from pathlib import Path

from ..core import BotError
from .backtest import compare
from .config import Config
from .data import collect, load_dataset
from .forward import paper_report, run_paper, verify_paper
from .report import write_report


def output(value):
    print(json.dumps(value, ensure_ascii=False, indent=2), flush=True)


def parser():
    root = argparse.ArgumentParser(description="BTC research: public data + virtual ledger only; no wallet or real orders")
    sub = root.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("collect", help="Download complete 1h BTC + hourly funding data with checksums")
    fetch.add_argument("--days", type=int, default=120)
    fetch.add_argument("--out", type=Path, required=True)
    test = sub.add_parser("backtest", help="Offline fixed-strategy train/holdout comparison + stress reports")
    test.add_argument("--data", type=Path, required=True)
    test.add_argument("--out", type=Path, required=True)
    test.add_argument("--config", type=Path, help="Optional research Config JSON; no credentials")
    paper = sub.add_parser("paper", help="Persist virtual accounts using current mainnet market data")
    paper.add_argument("--state", type=Path, required=True)
    paper.add_argument("--steps", type=int, default=6, help="0 = until Ctrl-C, otherwise bounded number of observations")
    paper.add_argument("--interval", type=float, default=10)
    paper.add_argument("--config", type=Path)
    show = sub.add_parser("paper-report", help="Read a paper SQLite snapshot; no network request")
    show.add_argument("--state", type=Path, required=True)
    show.add_argument("--out", type=Path, required=True)
    verify = sub.add_parser("verify-paper", help="Replay recorded observations offline and match every ledger/tick/event")
    verify.add_argument("--state", type=Path, required=True)
    return root


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        config = Config(**json.loads(args.config.read_text())) if getattr(args, "config", None) else Config()
        if args.command == "collect":
            output(collect(args.out, args.days))
        elif args.command == "backtest":
            result = compare(load_dataset(args.data), config)
            paths = write_report(result, args.out)
            output({**paths, "selected_on_training_only": result["selected"], "flags": result["flags"],
                    "holdout": {k: v["metrics"] for k, v in result["holdout"].items()}})
        elif args.command == "paper":
            summary = run_paper(args.state, config, args.steps, args.interval, emit=output)
            output(summary)
            return 0 if summary["completed_ticks"] and not summary["skipped_ticks"] else 2
        elif args.command == "verify-paper":
            output(verify_paper(args.state))
        else:
            output(write_report(paper_report(args.state), args.out))
        return 0
    except (BotError, OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        output({"error": str(exc) if isinstance(exc, BotError) else f"{type(exc).__name__}: invalid input, dataset or local state"})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
