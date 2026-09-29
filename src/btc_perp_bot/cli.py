import argparse
import getpass
import json
import sys
import time
import uuid
from contextlib import nullcontext
from pathlib import Path

from .core import BotError, number, positive, private_dir, signal, write_private_json
from .market import Market, address
from .paper import PaperBroker
from .trading import ExchangeBroker, Journal, account_lock, execution_guard, reconcile
from .wallet import create_wallet, load_wallet, password_from_file, verify_wallet


def output(value):
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def password(args, create=False):
    if args.password_file:
        return password_from_file(args.password_file)
    if not sys.stdin.isatty():
        raise BotError("Use a terminal password prompt or a 0600 --password-file; never a password argument")
    value = getpass.getpass("Keystore password (not shown): ")
    if create and value != getpass.getpass("Repeat password: "):
        raise BotError("Passwords do not match")
    return value


def signer_args(parser):
    parser.add_argument("--keystore", required=True, type=Path)
    parser.add_argument("--password-file", type=Path)


def execution_args(parser):
    signer_args(parser)
    parser.add_argument("--account", help="Master account address when using an authorized API wallet")
    parser.add_argument("--enable-live-orders", action="store_true", help="Operator-only opt-in for mainnet orders")
    parser.add_argument("--max-notional", type=positive, default=number("25"))


def make_parser():
    parser = argparse.ArgumentParser(description="BTC bot: defaults to paper/testnet; never auto-withdraws")
    commands = parser.add_subparsers(dest="command", required=True)
    wallet = commands.add_parser("wallet")
    wallets = wallet.add_subparsers(dest="wallet_command", required=True)
    create = wallets.add_parser("create")
    signer_args(create)
    create.add_argument("--purpose", choices=["testnet", "mainnet"], default="testnet")
    signer_args(wallets.add_parser("check"))
    for name in ("quote", "account", "order-status", "reconcile"):
        sub = commands.add_parser(name)
        sub.add_argument("--network", choices=["mainnet", "testnet"], default="testnet")
        if name != "quote":
            sub.add_argument("--account", required=True, type=address)
        if name in {"order-status", "reconcile"}:
            sub.add_argument("--id", required=True, help="Numeric order id or 0x client id")
    for name in ("order", "cancel"):
        sub = commands.add_parser(name)
        execution_args(sub)
        sub.add_argument("--network", choices=["testnet", "mainnet"], default="testnet")
        if name == "order":
            sub.add_argument("--side", choices=["buy", "sell"], required=True)
            sub.add_argument("--size", type=positive, required=True)
            sub.add_argument("--price", type=positive, required=True)
            sub.add_argument("--tif", choices=["Alo", "Gtc", "Ioc"], default="Alo")
            sub.add_argument("--reduce-only", action="store_true")
        else:
            sub.add_argument("--id", type=int, required=True)
    bot = commands.add_parser("bot")
    bot.add_argument("--mode", choices=["paper", "testnet", "live"], default="paper")
    bot.add_argument("--keystore", type=Path)
    bot.add_argument("--password-file", type=Path)
    bot.add_argument("--account")
    bot.add_argument("--enable-live-orders", action="store_true")
    bot.add_argument("--notional", type=positive, default=number("25"))
    bot.add_argument("--cash", type=positive, default=number("1000"), help="Paper starting balance only")
    bot.add_argument("--max-loss", type=positive, default=number("20"))
    bot.add_argument("--max-orders", type=int, default=8)
    bot.add_argument("--steps", type=int, default=6)
    bot.add_argument("--interval", type=positive, default=number("10"))
    bot.add_argument("--fast", type=int, default=3)
    bot.add_argument("--slow", type=int, default=8)
    bot.add_argument("--threshold", type=number, default=number("0.0002"))
    bot.add_argument("--flatten-on-exit", action="store_true", help="Paper always flattens; opt in for exchange mode")
    bot.add_argument("--output-dir", type=Path, default=Path("runs"))
    return parser


def unlock(args, network):
    execution_guard(network, args.enable_live_orders)
    if not args.keystore:
        raise BotError("Exchange execution requires --keystore")
    signer = load_wallet(args.keystore, password(args), network)
    owner = address(args.account or signer.address)
    return signer, owner


def journal_for(network, owner):
    root = private_dir(Path.home() / ".local/share/btc-perp-bot/journals")
    return Journal(root / f"{network}-{owner.lower()}.jsonl")


def run_bot(args):
    if not 1 <= args.steps <= 360 or args.max_orders < 1 or not 1 <= args.fast < args.slow <= 60:
        raise BotError("Require 1..360 steps, positive order budget, and 1 <= fast < slow <= 60")
    if not 0 <= args.threshold < 1 or args.interval < 1:
        raise BotError("Require interval >= 1 second and threshold in [0, 1)")
    network = "testnet" if args.mode == "testnet" else "mainnet"
    signer = owner = None
    if args.mode != "paper":
        signer, owner = unlock(args, network)
    market = Market(network)
    run_dir = private_dir(private_dir(args.output_dir) / (time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]))
    records, failure, last_quote = [], None, None
    guard = account_lock(network, owner) if owner else nullcontext()
    with guard:
        if args.mode == "paper":
            broker = PaperBroker(cash=args.cash, max_orders=args.max_orders)
            initial = args.cash
        else:
            broker = ExchangeBroker(market, signer, owner, journal_for(network, owner),
                                    max_notional=args.notional, max_orders=args.max_orders,
                                    enable_live=args.enable_live_orders)
            initial = number(broker.preflight(require_flat=True)["marginSummary"]["accountValue"])
        decimals = market.btc_meta()[1]["szDecimals"]
        try:
            for tick in range(args.steps):
                closes = market.closes(max(args.slow + 2, 20))
                quote = market.quote()
                last_quote = quote
                target = signal(closes, args.fast, args.slow, args.threshold)
                equity = broker.equity(quote) if args.mode == "paper" else number(broker.state()["marginSummary"]["accountValue"])
                stop = initial - equity >= args.max_loss
                broker.set_target(0 if stop else target, quote, args.notional, decimals)
                record = {"tick": tick, "mode": args.mode, "time": quote.timestamp,
                          "bid": str(quote.bid), "ask": str(quote.ask), "closed_candles": [str(x) for x in closes],
                          "signal": target, "loss_stop": stop}
                records.append(record)
                write_private_json(run_dir / f"tick-{tick:04}.json", record)
                if stop:
                    break
                if tick + 1 < args.steps:
                    time.sleep(float(args.interval))
            if args.mode == "paper" or args.flatten_on_exit:
                last_quote = market.quote()
                broker.set_target(0, last_quote, args.notional, decimals)
        except (BotError, KeyboardInterrupt) as exc:
            # Never issue cleanup orders when the last order or market state is uncertain.
            failure = "Interrupted" if isinstance(exc, KeyboardInterrupt) else str(exc)
        if args.mode == "paper" and last_quote:
            report = broker.summary(last_quote)
            write_private_json(run_dir / "fills.json", broker.fills)
        else:
            report = {"mode": args.mode, "account": owner, "order_count": broker.order_count if owner else 0,
                      "position": "Query account before restarting; not assumed flat"}
        report.update({"error": failure, "ticks": len(records), "run_dir": str(run_dir),
                       "strategy": {"fast": args.fast, "slow": args.slow, "threshold": str(args.threshold)},
                       "notional": str(args.notional), "max_loss": str(args.max_loss)})
        write_private_json(run_dir / "summary.json", report)
        output(report)
        return 1 if failure else 0


def main(argv=None):
    try:
        args = make_parser().parse_args(argv)
        if args.command == "wallet":
            if args.wallet_command == "create":
                output(create_wallet(args.keystore, password(args, True), args.purpose))
            else:
                output(verify_wallet(load_wallet(args.keystore, password(args))))
        elif args.command in {"quote", "account", "order-status", "reconcile"}:
            market = Market(args.network)
            if args.command == "quote":
                q = market.quote()
                output({"network": args.network, "coin": "BTC", "bid": q.bid, "ask": q.ask, "time": q.timestamp})
            elif args.command == "account":
                output(market.account(args.account))
            elif args.command == "reconcile":
                with account_lock(args.network, args.account):
                    output(reconcile(market, args.account, journal_for(args.network, args.account), args.id))
            else:
                oid = int(args.id) if args.id.isdecimal() else args.id
                output(market.order_status(args.account, oid))
        elif args.command in {"order", "cancel"}:
            signer, owner = unlock(args, args.network)
            with account_lock(args.network, owner):
                broker = ExchangeBroker(Market(args.network), signer, owner, journal_for(args.network, owner),
                                        max_notional=args.max_notional, enable_live=args.enable_live_orders)
                if args.command == "order":
                    output(broker.order(args.side, args.size, args.price, args.tif, args.reduce_only))
                else:
                    output(broker.cancel(args.id))
        else:
            return run_bot(args)
        return 0
    except BotError as exc:
        output({"error": str(exc)})
        return 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # Do not dump exception objects from libraries that may carry sensitive inputs.
        output({"error": f"{type(exc).__name__}: input, API data, or local file operation failed"})
        return 2
