import argparse
import sys
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from matchstats.build import BuildError, build, uefa_report
from matchstats.ingest import IngestError, load_matches

MADRID = ZoneInfo("Europe/Madrid")


def main(
    argv: list[str] | None = None,
    *,
    loader: Callable | None = None,
    fixtures_text: Callable[[], str] | None = None,
    feed_text: Callable[[str, str], str | None] | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="matchstats")
    commands = parser.add_subparsers(dest="command", required=True)

    build_cmd = commands.add_parser("build", help="write and validate the site data files")
    build_cmd.add_argument("--out", type=Path, required=True, help="directory to replace, e.g. site/public/data")
    build_cmd.add_argument("--cache", type=Path, required=True, help="raw CSV cache, e.g. data/raw")
    build_cmd.add_argument("--today", type=date.fromisoformat, default=None, help="YYYY-MM-DD (default: today in Europe/Madrid)")

    uefa_cmd = commands.add_parser("uefa-backtest", help="fit the UEFA league offsets and print the backtest")
    uefa_cmd.add_argument("--cache", type=Path, required=True, help="raw CSV cache, e.g. data/raw")
    uefa_cmd.add_argument("--today", type=date.fromisoformat, default=None, help="YYYY-MM-DD (default: today in Europe/Madrid)")

    args = parser.parse_args(argv)
    today = args.today or datetime.now(MADRID).date()
    if args.command == "uefa-backtest":
        return _uefa_backtest(args.cache, today, loader or load_matches, feed_text)
    try:
        build(
            out_dir=args.out,
            cache_dir=args.cache,
            today=today,
            loader=loader or load_matches,
            fixtures_text=fixtures_text,
            feed_text=feed_text,
        )
    except BuildError as error:
        print(f"build failed: {error}", file=sys.stderr)
        return 1
    return 0


def _uefa_backtest(cache: Path, today: date, loader: Callable, feed_text: Callable | None) -> int:
    try:
        document = uefa_report(cache, today, loader=loader, feed_text=feed_text)
    except IngestError as error:
        print(f"uefa-backtest failed: {error}", file=sys.stderr)
        return 1
    if document is None:
        print("uefa-backtest failed: no usable past UEFA results", file=sys.stderr)
        return 1

    backtest = document["backtest"]
    for key in ("held_out", "matches", "log_loss", "log_loss_unadjusted", "log_loss_baseline"):
        print(f"{key}: {backtest[key]}")
    print(f"calibrated: {str(document['calibrated']).lower()}")
    print(f"home_advantage: {document['home_advantage']}")
    print(f"{'league':<6}  {'attack':>8}  {'defense':>8}")
    for code, offset in document["offsets"].items():
        print(f"{code:<6}  {offset['attack']:>8.4f}  {offset['defense']:>8.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
