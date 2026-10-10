"""BLK-02: a green pytest exit from skipped or incomplete E2E is insufficient."""

import xml.etree.ElementTree as ET

import pytest

from scripts.verify_desktop_e2e import EXPECTED_SCENARIOS, verify_report


def make_report(path, names=EXPECTED_SCENARIOS, status=None):
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite")
    for name in names:
        case = ET.SubElement(suite, "testcase", name=name)
        if status:
            ET.SubElement(case, status)
    ET.ElementTree(root).write(path)
    return path


def test_complete_passed_report_accepted(tmp_path):
    verify_report(make_report(tmp_path / "report.xml"))


@pytest.mark.parametrize("status", ["skipped", "failure", "error"])
def test_non_passed_desktop_scenarios_rejected(tmp_path, status):
    with pytest.raises(ValueError, match="skipped, failed or errored"):
        verify_report(make_report(tmp_path / "report.xml", status=status))


@pytest.mark.parametrize(
    "names",
    [[], ["unrelated"], sorted(EXPECTED_SCENARIOS)[:-1], [*sorted(EXPECTED_SCENARIOS), "extra"]],
)
def test_missing_or_wrong_scenarios_rejected(tmp_path, names):
    with pytest.raises(ValueError, match="four required"):
        verify_report(make_report(tmp_path / "report.xml", names=names))


def test_duplicate_scenarios_rejected(tmp_path):
    with pytest.raises(ValueError, match="four required"):
        verify_report(make_report(tmp_path / "report.xml", names=["same"] * 4))


def test_missing_or_invalid_report_rejected(tmp_path):
    path = tmp_path / "report.xml"
    with pytest.raises(ValueError, match="missing or invalid"):
        verify_report(path)
    path.write_text("invalid", encoding="utf-8")
    with pytest.raises(ValueError, match="missing or invalid"):
        verify_report(path)
