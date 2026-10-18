"""B03: seed CLI help and validation finish without Mongo configuration."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run_seed_cli(*args: str) -> subprocess.CompletedProcess[str]:
    # Do not inherit a developer's database configuration in CLI smoke tests.
    env = {key: value for key, value in os.environ.items() if not key.startswith("NOTEAPP_")}
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "seed_notes.py"), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )


def test_seed_cli_help():
    result = run_seed_cli("--help")

    assert result.returncode == 0
    assert "--count" in result.stdout
    assert result.stderr == ""


def test_seed_cli_rejects_negative_count():
    result = run_seed_cli("--count", "-1")

    assert result.returncode == 2
    assert "--count must be between 0 and 1000" in result.stderr


def test_seed_cli_rejects_count_above_limit():
    result = run_seed_cli("--count", "1001")

    assert result.returncode == 2
    assert "--count must be between 0 and 1000" in result.stderr


def test_seed_cli_rejects_non_integer_count():
    result = run_seed_cli("--count", "abc")

    assert result.returncode == 2
    assert "--count" in result.stderr
    assert "invalid int value" in result.stderr
