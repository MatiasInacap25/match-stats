"""orchestra validate | run-wave | cleanup"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from orchestra.herdr import Herdr, worktree_path
from orchestra.manifest import ManifestError, load_wave
from orchestra.runner import CommandError, SubprocessRunner
from orchestra.wave import run_wave


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="orchestra")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate").add_argument("manifest", type=Path)
    run = sub.add_parser("run-wave")
    run.add_argument("manifest", type=Path)
    run.add_argument("--timeout-min", type=int, default=45)
    run.add_argument("--max-parallel", type=int, default=4)
    sub.add_parser("cleanup").add_argument("manifest", type=Path)
    for p in sub.choices.values():
        p.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    try:
        wave = load_wave(args.manifest)
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.command == "validate":
        print(f"ok: wave {wave.name} with {len(wave.tasks)} tasks: {', '.join(t.id for t in wave.tasks)}")
        return 0

    repo = args.repo.resolve()
    herdr = Herdr(SubprocessRunner())

    if args.command == "run-wave":
        if not 1 <= args.max_parallel <= 4:
            print("error: --max-parallel must be between 1 and 4", file=sys.stderr)
            return 1
        results = run_wave(wave, repo, herdr, timeout_ms=args.timeout_min * 60_000, max_parallel=args.max_parallel)
        print(json.dumps([asdict(r) for r in results], indent=2, default=str))
        return 0 if all(r.status in {"idle", "done"} for r in results) else 3

    code = 0
    for task in wave.tasks:
        path = worktree_path(repo, task.id)
        if not path.exists():
            continue
        try:
            herdr.remove_worktree(repo, path)
            print(f"removed {path}")
        except CommandError as exc:
            print(f"error: {exc}", file=sys.stderr)
            code = 1
    return code


if __name__ == "__main__":
    sys.exit(main())
