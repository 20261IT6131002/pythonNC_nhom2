"""CF-06: clean checkout reproduces D0 checks and rejects contract/link drift."""

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.verify_phase2_contract import verify_declarations, verify_documentation

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs/architecture/PHASE2_PUBLIC_CONTRACTS.md"


def test_phase2_documentation_is_consistent():
    blocks, links = verify_documentation(ROOT)
    assert blocks == 5
    assert links > 0


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("@dataclass(frozen=True)", "@dataclass(frozen=False)", "Immutable field"),
        ("limit: int = 30", "limit: int = 0", "search defaults"),
        ("confirmed: bool = False", "confirmed: bool = True", "confirmation"),
        ("-> NotePage:", "-> UnknownPage:", "unresolved"),
        ("-> NotePage:", ":", "typed port signature"),
        ("class SearchRepository(Protocol):", "class SearchRepository:", "Missing protocol"),
        ("class SortMode(str, Enum):", "class SortMode(", "Invalid"),
    ],
)
def test_declaration_drift_is_rejected(old, new, message):
    source = CONTRACT.read_text(encoding="utf-8")
    assert old in source
    with pytest.raises(ValueError, match=message):
        verify_declarations(source.replace(old, new, 1))


def test_missing_declaration_blocks_are_rejected():
    with pytest.raises(ValueError, match="five declaration blocks"):
        verify_declarations("No declaration blocks")


@pytest.fixture
def documentation_snapshot(tmp_path):
    for source in (ROOT / "docs").rglob("*.md"):
        target = tmp_path / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def test_broken_local_links_are_rejected(documentation_snapshot):
    contract = documentation_snapshot / CONTRACT.relative_to(ROOT)
    with contract.open("a", encoding="utf-8") as stream:
        stream.write("\n[Invalid local reference](missing.md)\n")
    with pytest.raises(ValueError, match="Broken local link"):
        verify_documentation(documentation_snapshot)


def test_missing_required_document_is_rejected(documentation_snapshot):
    (documentation_snapshot / "docs/testing/PHASE2_P2_02_REVIEW.md").unlink()
    with pytest.raises(ValueError, match="missing or unreadable"):
        verify_documentation(documentation_snapshot)


def test_tracked_cli_succeeds_from_another_working_directory(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_phase2_contract.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "Verified 5 declaration blocks" in result.stdout
