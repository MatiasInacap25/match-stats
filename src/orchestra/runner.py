"""Single seam for every external command (git, herdr), so orchestration logic is testable."""

import subprocess
from pathlib import Path
from typing import Protocol


class CommandError(RuntimeError):
    def __init__(self, argv: list[str], returncode: int, stdout: str, stderr: str):
        super().__init__(f"{' '.join(argv)} exited {returncode}: {stderr.strip() or stdout.strip()}")
        self.argv = argv
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class Runner(Protocol):
    def run(self, argv: list[str], cwd: Path | None = None) -> str: ...


class SubprocessRunner:
    def run(self, argv: list[str], cwd: Path | None = None) -> str:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise CommandError(argv, proc.returncode, proc.stdout, proc.stderr)
        return proc.stdout
