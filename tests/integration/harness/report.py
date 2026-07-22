"""IntRunReport — produce JUnit XML and JSON run reports.

Emits both report forms at the end of an integration run. The JSON report
captures all run metadata including run_id, account_id (the allowlisted INT
account), region, mutations_reverted, baseline_restored, and test results.
The JUnit XML report produces valid ``<testsuite>``/``<testcase>`` elements
compatible with CI tools.

Requirements: 5.4, 8.5, 10.2
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TestResult:
    """Result of a single integration test case.

    Attributes
    ----------
    name : str
        Fully qualified test name (e.g. ``test_happy_path_create``).
    status : str
        One of ``passed``, ``failed``, or ``error``.
    duration : float
        Wall-clock execution time in seconds.
    message : str
        Optional failure/error message (empty string on pass).
    """

    name: str
    status: str
    duration: float
    message: str = ""


@dataclass
class IntRunReport:
    """Integration run report with JUnit XML and JSON serialization.

    Records the run metadata required by the DVP spec:
    - ``account_id``: the allowlisted INT account identifier (Requirement 5.4)
    - ``mutations_reverted`` / ``baseline_restored``: revert outcome (Requirement 10.2)
    - Test results in both JUnit and JSON forms (Requirement 8.5)

    Attributes
    ----------
    run_id : str
        The unique run identifier (``int-<shortsha>-<epoch>``).
    account_id : str
        The allowlisted INT account id.
    region : str
        The AWS region the run executed in.
    mutations_reverted : bool
        Whether all run-id-scoped mutations were successfully reverted.
    baseline_restored : bool
        Whether the firewall policy was restored to its baseline state.
    test_results : list[TestResult]
        Results for each test case in the run.
    started_at : str
        ISO-8601 UTC timestamp when the run started.
    completed_at : str
        ISO-8601 UTC timestamp when the run completed.
    """

    run_id: str
    account_id: str
    region: str
    mutations_reverted: bool
    baseline_restored: bool
    test_results: list[TestResult] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""

    def to_json(self, path: Path) -> None:
        """Write the report as a JSON file.

        The JSON structure includes all metadata fields and the full list of
        test results serialized as dictionaries.

        Parameters
        ----------
        path : Path
            Destination file path for the JSON report.
        """
        data = {
            "run_id": self.run_id,
            "account_id": self.account_id,
            "region": self.region,
            "mutations_reverted": self.mutations_reverted,
            "baseline_restored": self.baseline_restored,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "test_results": [asdict(r) for r in self.test_results],
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

        logger.info("IntRunReport.to_json: wrote %s (%d test results)", path, len(self.test_results))

    def to_junit(self, path: Path) -> None:
        """Write the report as a JUnit XML file.

        Produces valid XML compatible with CI tools (Jenkins, GitHub Actions,
        etc.) using ``<testsuite>`` and ``<testcase>`` elements.

        Parameters
        ----------
        path : Path
            Destination file path for the JUnit XML report.
        """
        tests_count = len(self.test_results)
        failures_count = sum(1 for r in self.test_results if r.status == "failed")
        errors_count = sum(1 for r in self.test_results if r.status == "error")

        testsuite = Element("testsuite")
        testsuite.set("name", f"int-run-{self.run_id}")
        testsuite.set("tests", str(tests_count))
        testsuite.set("failures", str(failures_count))
        testsuite.set("errors", str(errors_count))
        testsuite.set("time", f"{sum(r.duration for r in self.test_results):.3f}")

        # Record DVP-specific properties as JUnit properties
        properties = SubElement(testsuite, "properties")
        for prop_name, prop_value in [
            ("run_id", self.run_id),
            ("account_id", self.account_id),
            ("region", self.region),
            ("mutations_reverted", str(self.mutations_reverted).lower()),
            ("baseline_restored", str(self.baseline_restored).lower()),
            ("started_at", self.started_at),
            ("completed_at", self.completed_at),
        ]:
            prop = SubElement(properties, "property")
            prop.set("name", prop_name)
            prop.set("value", prop_value)

        for result in self.test_results:
            testcase = SubElement(testsuite, "testcase")
            testcase.set("name", result.name)
            testcase.set("classname", f"integration.{self.run_id}")
            testcase.set("time", f"{result.duration:.3f}")

            if result.status == "failed":
                failure = SubElement(testcase, "failure")
                failure.set("message", result.message)
                failure.text = result.message
            elif result.status == "error":
                error = SubElement(testcase, "error")
                error.set("message", result.message)
                error.text = result.message

        path.parent.mkdir(parents=True, exist_ok=True)

        tree = ElementTree(testsuite)
        with open(path, "wb") as f:
            tree.write(f, encoding="utf-8", xml_declaration=True)

        logger.info(
            "IntRunReport.to_junit: wrote %s (%d tests, %d failures, %d errors)",
            path,
            tests_count,
            failures_count,
            errors_count,
        )
