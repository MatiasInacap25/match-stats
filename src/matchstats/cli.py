import argparse
import sys
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from matchstats.build import BuildError, build
from matchstats.ingest import load_matches

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

    args = parser.parse_args(argv)
    today = args.today or datetime.now(MADRID).date()
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


if __name__ == "__main__":
    sys.exit(main())
