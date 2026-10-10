"""QA-owned CI gate: require all real desktop scenarios to pass without skips."""

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

EXPECTED_SCENARIOS = {
    "test_desktop_create_restart_edit_conflict",
    "test_desktop_db_unavailable_preserves_text_and_closes_pending",
    "test_real_launcher_mainloop_and_shutdown",
    "test_phase2_search_trash_restart_restore_and_confirmed_purge",
}


def verify_report(report: Path) -> None:
    try:
        cases = ET.parse(report).getroot().findall(".//testcase")
    except (OSError, ET.ParseError):
        raise ValueError("Desktop E2E report is missing or invalid.") from None
    names = {case.get("name") for case in cases}
    if len(cases) != len(EXPECTED_SCENARIOS) or names != EXPECTED_SCENARIOS:
        raise ValueError("Desktop E2E must execute exactly the four required scenarios.")
    if any(
        case.find(status) is not None
        for case in cases
        for status in ("skipped", "failure", "error")
    ):
        raise ValueError("Desktop E2E contains a skipped, failed or errored scenario.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    try:
        verify_report(args.report)
    except ValueError as error:
        parser.exit(1, str(error) + "\n")
    print("Verified all 4 desktop Mongo E2E scenarios passed; skipped=0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
