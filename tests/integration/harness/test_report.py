"""Unit tests for IntRunReport (JUnit + JSON output).

Validates Requirements 5.4, 8.5, 10.2:
- JSON report includes run_id, account_id, region, mutations_reverted,
  baseline_restored, and test_results.
- JUnit report produces valid XML with testsuite/testcase elements.
- account_id is recorded as the allowlisted INT account.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tests.integration.harness.report import IntRunReport, TestResult


@pytest.fixture
def sample_report() -> IntRunReport:
    """A minimal IntRunReport with mixed test results."""
    return IntRunReport(
        run_id="int-abcd1234-1700000000",
        account_id="123456789012",
        region="us-east-1",
        mutations_reverted=True,
        baseline_restored=True,
        test_results=[
            TestResult(name="test_happy_path_create", status="passed", duration=12.5),
            TestResult(
                name="test_malformed_config",
                status="failed",
                duration=5.2,
                message="Expected no rule group within 240s",
            ),
            TestResult(
                name="test_delete_vpc_event",
                status="error",
                duration=1.0,
                message="boto3 ClientError: AccessDenied",
            ),
        ],
        started_at="2024-01-15T10:00:00Z",
        completed_at="2024-01-15T10:05:00Z",
    )


class TestToJson:
    """Tests for IntRunReport.to_json()."""

    def test_json_contains_all_metadata(self, sample_report: IntRunReport, tmp_path: Path) -> None:
        """JSON report includes all required metadata fields."""
        out = tmp_path / "report.json"
        sample_report.to_json(out)

        data = json.loads(out.read_text(encoding="utf-8"))

        assert data["run_id"] == "int-abcd1234-1700000000"
        assert data["account_id"] == "123456789012"
        assert data["region"] == "us-east-1"
        assert data["mutations_reverted"] is True
        assert data["baseline_restored"] is True
        assert data["started_at"] == "2024-01-15T10:00:00Z"
        assert data["completed_at"] == "2024-01-15T10:05:00Z"

    def test_json_contains_test_results(self, sample_report: IntRunReport, tmp_path: Path) -> None:
        """JSON report includes all test results with correct fields."""
        out = tmp_path / "report.json"
        sample_report.to_json(out)

        data = json.loads(out.read_text(encoding="utf-8"))
        results = data["test_results"]

        assert len(results) == 3
        assert results[0] == {
            "name": "test_happy_path_create",
            "status": "passed",
            "duration": 12.5,
            "message": "",
        }
        assert results[1]["status"] == "failed"
        assert results[1]["message"] == "Expected no rule group within 240s"

    def test_json_creates_parent_directories(self, sample_report: IntRunReport, tmp_path: Path) -> None:
        """to_json creates intermediate directories if they don't exist."""
        out = tmp_path / "nested" / "dir" / "report.json"
        sample_report.to_json(out)

        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["run_id"] == "int-abcd1234-1700000000"

    def test_json_mutations_reverted_false(self, tmp_path: Path) -> None:
        """JSON report records mutations_reverted=False when revert failed."""
        report = IntRunReport(
            run_id="int-dead0000-1700000001",
            account_id="123456789012",
            region="eu-west-1",
            mutations_reverted=False,
            baseline_restored=False,
            started_at="2024-01-15T10:00:00Z",
            completed_at="2024-01-15T10:01:00Z",
        )
        out = tmp_path / "report.json"
        report.to_json(out)

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["mutations_reverted"] is False
        assert data["baseline_restored"] is False

    def test_json_empty_test_results(self, tmp_path: Path) -> None:
        """JSON report handles zero test results correctly."""
        report = IntRunReport(
            run_id="int-00000000-1700000000",
            account_id="123456789012",
            region="us-west-2",
            mutations_reverted=True,
            baseline_restored=True,
            started_at="2024-01-15T10:00:00Z",
            completed_at="2024-01-15T10:00:01Z",
        )
        out = tmp_path / "report.json"
        report.to_json(out)

        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["test_results"] == []


class TestToJunit:
    """Tests for IntRunReport.to_junit()."""

    def test_junit_valid_xml_structure(self, sample_report: IntRunReport, tmp_path: Path) -> None:
        """JUnit report produces well-formed XML with testsuite root."""
        out = tmp_path / "report.xml"
        sample_report.to_junit(out)

        tree = ET.parse(out)
        root = tree.getroot()

        assert root.tag == "testsuite"
        assert root.get("name") == "int-run-int-abcd1234-1700000000"
        assert root.get("tests") == "3"
        assert root.get("failures") == "1"
        assert root.get("errors") == "1"

    def test_junit_testcase_elements(self, sample_report: IntRunReport, tmp_path: Path) -> None:
        """JUnit report contains one testcase element per test result."""
        out = tmp_path / "report.xml"
        sample_report.to_junit(out)

        tree = ET.parse(out)
        root = tree.getroot()
        testcases = root.findall("testcase")

        assert len(testcases) == 3
        assert testcases[0].get("name") == "test_happy_path_create"
        assert testcases[0].get("time") == "12.500"
        # Passed test has no failure/error child
        assert testcases[0].find("failure") is None
        assert testcases[0].find("error") is None

    def test_junit_failure_element(self, sample_report: IntRunReport, tmp_path: Path) -> None:
        """Failed test cases include a <failure> element with message."""
        out = tmp_path / "report.xml"
        sample_report.to_junit(out)

        tree = ET.parse(out)
        root = tree.getroot()
        testcases = root.findall("testcase")
        failed_tc = testcases[1]

        failure = failed_tc.find("failure")
        assert failure is not None
        assert failure.get("message") == "Expected no rule group within 240s"
        assert failure.text == "Expected no rule group within 240s"

    def test_junit_error_element(self, sample_report: IntRunReport, tmp_path: Path) -> None:
        """Error test cases include an <error> element with message."""
        out = tmp_path / "report.xml"
        sample_report.to_junit(out)

        tree = ET.parse(out)
        root = tree.getroot()
        testcases = root.findall("testcase")
        error_tc = testcases[2]

        error = error_tc.find("error")
        assert error is not None
        assert error.get("message") == "boto3 ClientError: AccessDenied"

    def test_junit_properties_include_dvp_metadata(
        self, sample_report: IntRunReport, tmp_path: Path
    ) -> None:
        """JUnit properties capture account_id, mutations_reverted, baseline_restored."""
        out = tmp_path / "report.xml"
        sample_report.to_junit(out)

        tree = ET.parse(out)
        root = tree.getroot()
        props = root.find("properties")
        assert props is not None

        prop_map = {p.get("name"): p.get("value") for p in props.findall("property")}

        assert prop_map["account_id"] == "123456789012"
        assert prop_map["mutations_reverted"] == "true"
        assert prop_map["baseline_restored"] == "true"
        assert prop_map["run_id"] == "int-abcd1234-1700000000"
        assert prop_map["region"] == "us-east-1"

    def test_junit_creates_parent_directories(self, sample_report: IntRunReport, tmp_path: Path) -> None:
        """to_junit creates intermediate directories if they don't exist."""
        out = tmp_path / "nested" / "dir" / "report.xml"
        sample_report.to_junit(out)

        assert out.exists()
        tree = ET.parse(out)
        assert tree.getroot().tag == "testsuite"

    def test_junit_total_time(self, sample_report: IntRunReport, tmp_path: Path) -> None:
        """JUnit testsuite time is the sum of all testcase durations."""
        out = tmp_path / "report.xml"
        sample_report.to_junit(out)

        tree = ET.parse(out)
        root = tree.getroot()

        # 12.5 + 5.2 + 1.0 = 18.7
        assert root.get("time") == "18.700"

    def test_junit_xml_declaration(self, sample_report: IntRunReport, tmp_path: Path) -> None:
        """JUnit report starts with an XML declaration."""
        out = tmp_path / "report.xml"
        sample_report.to_junit(out)

        content = out.read_bytes()
        assert content.startswith(b"<?xml")
