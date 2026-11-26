"""Unit tests for pyado.raw.test.test_results."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
import requests
from pydantic import ValidationError

from pyado.raw import (
    ApiCall,
    CodeCoverageStats,
    FileCoverage,
    TestAttachmentType,
    TestIdentity,
    TestOutcome,
    TestResultCreate,
    TestResultUpdate,
    TestRunCreate,
    TestRunUpdate,
    delete_test_run,
    get_code_coverage,
    get_test_attachment_bytes,
    get_test_result,
    get_test_results_api_call,
    get_test_run,
    iter_build_test_runs,
    iter_test_result_attachments,
    iter_test_results,
    iter_test_run_attachments,
    list_build_test_runs,
    list_test_results,
    make_attachment_request,
    patch_test_results,
    patch_test_run,
    post_code_coverage,
    post_file_coverage,
    post_test_result_attachment,
    post_test_results,
    post_test_run,
    post_test_run_attachment,
    publish_code_coverage,
)
from pyado.raw import (
    TestRunState as RunState,
)
from tests.conftest import _make_mock_response

RUN = {"id": 7, "name": "r", "state": "InProgress", "totalTests": 3, "passedTests": 2}


class TestRunCalls:
    """Tests for the run functions."""

    @staticmethod
    def test_post_run_serialises_the_request(api_call: ApiCall) -> None:
        """The body is camelCase, omits unset fields and nests the build id."""
        request = TestRunCreate(
            name="r",
            build={"id": 5},
            owner=TestIdentity(id="u1"),
            started_date=datetime(2026, 11, 23, tzinfo=UTC),
        )
        with patch.object(
            requests.Session, "request", return_value=_make_mock_response(RUN)
        ) as mock_req:
            run = post_test_run(api_call, request)
        call = mock_req.call_args
        assert call.args[0] == "POST"
        assert call.kwargs["url"].endswith("/test/runs")
        body = call.kwargs["json"]
        assert body["build"] == {"id": 5}
        assert body["isAutomated"] is True
        assert body["state"] == "InProgress"
        assert body["owner"] == {"id": "u1"}
        assert "comment" not in body
        assert body["startedDate"].startswith("2026-11-23")
        assert run.id == 7

    @staticmethod
    def test_patch_run_completes_it(api_call: ApiCall) -> None:
        """patch_test_run sends only the fields that are set."""
        with patch.object(
            requests.Session, "request", return_value=_make_mock_response(RUN)
        ) as mock_req:
            patch_test_run(api_call, 7, TestRunUpdate(state=RunState.COMPLETED))
        call = mock_req.call_args
        assert call.args[0] == "PATCH"
        assert call.kwargs["url"].endswith("/test/runs/7")
        assert call.kwargs["json"] == {"state": "Completed"}

    @staticmethod
    def test_get_run(api_call: ApiCall) -> None:
        """get_test_run reads one run with its counters."""
        with patch.object(
            requests.Session, "request", return_value=_make_mock_response(RUN)
        ) as mock_req:
            run = get_test_run(api_call, 7)
        assert mock_req.call_args.kwargs["url"].endswith("/test/runs/7")
        assert run.total_tests == 3

    @staticmethod
    def test_build_runs_are_found_by_build_uri(api_call: ApiCall) -> None:
        """The runs of a build are listed with buildUri=vstfs:///Build/Build/{id}."""
        with patch.object(
            requests.Session,
            "request",
            return_value=_make_mock_response({"value": [RUN]}),
        ) as mock_req:
            runs = list_build_test_runs(api_call, 42)
        params = mock_req.call_args.kwargs["params"]
        assert params["buildUri"] == "vstfs:///Build/Build/42"
        assert [r.id for r in runs] == [7]

    @staticmethod
    def test_iter_build_runs_is_lazy_and_empty_ok(api_call: ApiCall) -> None:
        """An empty answer yields nothing."""
        with patch.object(
            requests.Session,
            "request",
            return_value=_make_mock_response({"value": []}),
        ):
            assert list(iter_build_test_runs(api_call, 1)) == []


class TestUnknownRunState:
    """A deleted run is listed with the state ``"255"``."""

    @staticmethod
    def test_unknown_state_reads_as_other() -> None:
        """An unknown state must not fail the whole listing."""
        assert RunState("255") is RunState.OTHER


class TestRunState:
    """The state a run may be created with."""

    @staticmethod
    def test_a_run_cannot_be_created_completed() -> None:
        """The server answers HTTP 400 for it, so the model refuses it."""
        with pytest.raises(ValidationError):
            TestRunCreate(name="r", build={"id": 1}, state=RunState.COMPLETED)

    @staticmethod
    def test_a_run_can_be_created_not_started() -> None:
        """NotStarted is accepted at creation."""
        run = TestRunCreate(name="r", build={"id": 1}, state=RunState.NOT_STARTED)
        assert run.state == RunState.NOT_STARTED


class TestResultCalls:
    """Tests for the result and attachment functions."""

    @staticmethod
    def test_post_results_sends_every_set_field(api_call: ApiCall) -> None:
        """Owner, error text and the outcome reach the body."""
        row = TestResultCreate(
            test_case_title="t",
            automated_test_name="a.t",
            test_case={"name": "t"},
            outcome=TestOutcome.FAILED,
            error_message="boom",
            stack_trace="at x",
            owner=TestIdentity(id="u1", display_name="U"),
            computer_name="HOST",
        )
        response = _make_mock_response({"value": [{"id": 100000}]})
        with patch.object(
            requests.Session, "request", return_value=response
        ) as mock_req:
            refs = post_test_results(api_call, 7, [row])
        call = mock_req.call_args
        assert call.args[0] == "POST"
        assert call.kwargs["url"].endswith("/test/runs/7/results")
        sent = call.kwargs["json"][0]
        assert sent["outcome"] == "Failed"
        assert sent["errorMessage"] == "boom"
        assert sent["owner"] == {"id": "u1", "displayName": "U"}
        assert sent["computerName"] == "HOST"
        assert refs[0].id == 100000

    @staticmethod
    def test_patch_results_links_a_bug(api_call: ApiCall) -> None:
        """associated_bugs is sent as associatedBugs: [{id}]."""
        response = _make_mock_response({"value": [{"id": 100000}]})
        with patch.object(
            requests.Session, "request", return_value=response
        ) as mock_req:
            patch_test_results(
                api_call,
                7,
                [TestResultUpdate(id=100000, associated_bugs=[{"id": 2098}])],
            )
        call = mock_req.call_args
        assert call.args[0] == "PATCH"
        assert call.kwargs["json"] == [{"id": 100000, "associatedBugs": [{"id": 2098}]}]

    @staticmethod
    def test_attachment_request_base64_encodes() -> None:
        """The stream is the base64 text of the bytes."""
        request = make_attachment_request(
            "n.txt", b"hi", attachment_type=TestAttachmentType.CONSOLE_LOG
        )
        assert request.stream == "aGk="
        assert request.attachment_type == TestAttachmentType.CONSOLE_LOG

    @staticmethod
    def test_result_attachment_path_and_id(api_call: ApiCall) -> None:
        """A result attachment is posted below the result and returns its id."""
        with patch.object(
            requests.Session,
            "request",
            return_value=_make_mock_response({"id": 2}),
        ) as mock_req:
            att_id = post_test_result_attachment(
                api_call, 7, 100000, make_attachment_request("n.txt", b"hi")
            )
        url = mock_req.call_args.kwargs["url"]
        assert url.endswith("/test/runs/7/results/100000/attachments")
        assert mock_req.call_args.kwargs["json"]["fileName"] == "n.txt"
        assert att_id == 2

    @staticmethod
    def test_run_attachment_path_and_id(api_call: ApiCall) -> None:
        """A run attachment is posted below the run."""
        with patch.object(
            requests.Session,
            "request",
            return_value=_make_mock_response({"id": 10}),
        ) as mock_req:
            att_id = post_test_run_attachment(
                api_call, 7, make_attachment_request("r.txt", b"x")
            )
        assert mock_req.call_args.kwargs["url"].endswith("/test/runs/7/attachments")
        assert att_id == 10


class TestCoverageCalls:
    """Tests for the coverage functions."""

    @staticmethod
    def test_get_coverage_reads_the_stored_summary(api_call: ApiCall) -> None:
        """The stored stats and the status come back as a model."""
        response = _make_mock_response(
            {
                "status": "finalized",
                "coverageData": [
                    {
                        "buildFlavor": "",
                        "buildPlatform": "",
                        "coverageStats": [
                            {
                                "label": "Lines",
                                "position": 2,
                                "total": 36,
                                "covered": 30,
                                "isDeltaAvailable": False,
                            }
                        ],
                    }
                ],
            }
        )
        with patch.object(
            requests.Session, "request", return_value=response
        ) as mock_req:
            summary = get_code_coverage(api_call, 42)
        assert mock_req.call_args.kwargs["params"]["deltaBuildId"] == 0
        assert summary.status == "finalized"
        assert summary.coverage_data[0].coverage_stats[0].covered == 30

    @staticmethod
    def test_get_coverage_without_data(api_call: ApiCall) -> None:
        """No stored summary reads as an empty list."""
        response = _make_mock_response({"status": "completed", "coverageData": []})
        with patch.object(requests.Session, "request", return_value=response):
            assert get_code_coverage(api_call, 42).coverage_data == []


RESULT = {
    "id": 100000,
    "outcome": "Failed",
    "state": "Completed",
    "testCaseTitle": "t",
    "automatedTestName": "a.t",
    "testCase": {"name": "t"},
    "durationInMs": 2000.0,
    "startedDate": "2026-11-23T01:52:25.36Z",
    "errorMessage": "boom",
    "stackTrace": "at x",
    "computerName": "HOST",
    "owner": {"displayName": "U", "id": "u1"},
    "testRun": {"id": "11"},
    "somethingNew": {"x": 1},
}


class TestResultDuration:
    """The duration is derived from the dates, not sent."""

    @staticmethod
    def test_the_dates_are_sent_and_no_duration_field() -> None:
        """CompletedDate and startedDate go out; there is no duration value."""
        row = TestResultCreate(
            test_case_title="t",
            automated_test_name="a.t",
            test_case={"name": "t"},
            outcome=TestOutcome.PASSED,
            started_date=datetime(2026, 11, 23, 10, 0, 0, tzinfo=UTC),
            completed_date=datetime(2026, 11, 23, 10, 0, 3, tzinfo=UTC),
        )
        body = row.model_dump(by_alias=True, mode="json", exclude_none=True)
        assert body["startedDate"].startswith("2026-11-23T10:00:00")
        assert body["completedDate"].startswith("2026-11-23T10:00:03")
        assert not any("uration" in key for key in body)


class TestReadResults:
    """Tests for the result read functions."""

    @staticmethod
    def test_a_result_is_parsed_with_its_text_and_owner(api_call: ApiCall) -> None:
        """Error text, owner, host and duration come back; unknown keys are ignored."""
        with patch.object(
            requests.Session, "request", return_value=_make_mock_response(RESULT)
        ) as mock_req:
            result = get_test_result(api_call, 11, 100000)
        assert mock_req.call_args.kwargs["url"].endswith("/test/runs/11/results/100000")
        assert result.outcome == "Failed"
        assert result.error_message == "boom"
        assert result.owner is not None
        assert result.owner.display_name == "U"
        assert result.computer_name == "HOST"
        assert result.duration_in_ms == pytest.approx(2000.0)

    @staticmethod
    def test_a_minimal_result_reads(api_call: ApiCall) -> None:
        """Only the id is required."""
        with patch.object(
            requests.Session, "request", return_value=_make_mock_response({"id": 5})
        ):
            assert get_test_result(api_call, 11, 5).outcome is None

    @staticmethod
    def test_results_are_read_in_one_page(api_call: ApiCall) -> None:
        """A page shorter than the page size ends the iteration."""
        response = _make_mock_response({"value": [RESULT, {**RESULT, "id": 100001}]})
        with patch.object(
            requests.Session, "request", return_value=response
        ) as mock_req:
            results = list_test_results(api_call, 11)
        assert [r.id for r in results] == [100000, 100001]
        assert mock_req.call_count == 1
        params = mock_req.call_args.kwargs["params"]
        assert params["$top"] == 1000
        assert params["$skip"] == 0

    @staticmethod
    def test_results_are_paged(api_call: ApiCall) -> None:
        """A full page makes the next request skip what was read."""
        pages = [
            _make_mock_response({"value": [RESULT, {**RESULT, "id": 2}]}),
            _make_mock_response({"value": [{**RESULT, "id": 3}]}),
        ]
        with patch.object(requests.Session, "request", side_effect=pages) as mock_req:
            ids = [r.id for r in iter_test_results(api_call, 11, page_size=2)]
        assert ids == [100000, 2, 3]
        assert mock_req.call_args_list[1].kwargs["params"]["$skip"] == 2

    @staticmethod
    def test_an_empty_run_yields_nothing(api_call: ApiCall) -> None:
        """No results is an empty list."""
        with patch.object(
            requests.Session,
            "request",
            return_value=_make_mock_response({"value": []}),
        ):
            assert list_test_results(api_call, 11) == []


ATTACHMENT = {"id": 14, "fileName": "n.txt", "size": 14, "comment": "", "url": "u"}


class TestReadAttachments:
    """Tests for listing and downloading attachments."""

    def test_result_attachments_are_listed(self, api_call: ApiCall) -> None:
        """The listing sits below the result."""
        with patch.object(
            requests.Session,
            "request",
            return_value=_make_mock_response({"value": [ATTACHMENT]}),
        ) as mock_req:
            items = list(iter_test_result_attachments(api_call, 11, 100000))
        url = mock_req.call_args.kwargs["url"]
        assert url.endswith("/test/runs/11/results/100000/attachments")
        assert items[0].file_name == "n.txt"
        assert items[0].size == 14

    def test_run_attachments_are_listed(self, api_call: ApiCall) -> None:
        """The run listing has no result id."""
        with patch.object(
            requests.Session,
            "request",
            return_value=_make_mock_response({"value": [ATTACHMENT]}),
        ) as mock_req:
            items = list(iter_test_run_attachments(api_call, 11))
        assert mock_req.call_args.kwargs["url"].endswith("/test/runs/11/attachments")
        assert items[0].id == 14

    @staticmethod
    def test_a_run_attachment_is_downloaded(api_call: ApiCall) -> None:
        """Without a result id the path is below the run."""
        response = _make_mock_response()
        response.content = b"\x00\xff bytes"
        with patch.object(
            requests.Session, "request", return_value=response
        ) as mock_req:
            data = get_test_attachment_bytes(api_call, 11, 14)
        assert mock_req.call_args.kwargs["url"].endswith("/test/runs/11/attachments/14")
        assert data == b"\x00\xff bytes"

    @staticmethod
    def test_a_result_attachment_is_downloaded(api_call: ApiCall) -> None:
        """With a result id the path is below the result."""
        response = _make_mock_response()
        response.content = b"x"
        with patch.object(
            requests.Session, "request", return_value=response
        ) as mock_req:
            get_test_attachment_bytes(api_call, 11, 14, result_id=100000)
        url = mock_req.call_args.kwargs["url"]
        assert url.endswith("/test/runs/11/results/100000/attachments/14")


class TestDeleteRun:
    """Tests for delete_test_run."""

    @staticmethod
    def test_deletes_the_run(api_call: ApiCall) -> None:
        """A DELETE to test/runs/{id}."""
        with patch.object(
            requests.Session, "request", return_value=_make_mock_response()
        ) as mock_req:
            delete_test_run(api_call, 11)
        assert mock_req.call_args.args[0] == "DELETE"
        assert mock_req.call_args.kwargs["url"].endswith("/test/runs/11")


PROJECT_ID = "0ce61429-ee5e-47ce-8e9e-ed4a56b8f5d9"
PROJECT_CALL_URL = f"https://dev.azure.com/org/{PROJECT_ID}/_apis"
SIGNED = "https://blob.example.net/container-guid-buildid-9?sv=1&sig=SECRET"
FILES = [
    FileCoverage(
        file_path="/w/a.py", line_coverage_status={"1": "covered", "2": "notCovered"}
    ),
    FileCoverage(file_path="/w/b.py", line_coverage_status={"1": "covered"}),
]


class TestTestResultsCall:
    """The coverage routes live on another host than the project routes."""

    @staticmethod
    def test_the_host_and_project_are_taken_from_the_project_call() -> None:
        """vstmr.dev.azure.com/{org}/{project}/_apis/testresults, same session."""
        project = ApiCall(url=PROJECT_CALL_URL)
        results = get_test_results_api_call(project)
        assert results.url.unicode_string() == (
            f"https://vstmr.dev.azure.com/org/{PROJECT_ID}/_apis/testresults"
        )
        assert results.session is project.session


class TestPostCodeCoverage:
    """The figures request that PublishCodeCoverageResults@2 sends."""

    @staticmethod
    def test_it_posts_the_task_body_with_the_preview_version() -> None:
        """Body, query and api-version as seen behind the logging proxy."""
        results = get_test_results_api_call(ApiCall(url=PROJECT_CALL_URL))
        with patch.object(
            requests.Session, "request", return_value=_make_mock_response(None)
        ) as req:
            post_code_coverage(
                results,
                9,
                [CodeCoverageStats(label="line", position=4, total=6, covered=5)],
            )
        kwargs = req.call_args.kwargs
        assert req.call_args.args[0] == "POST"
        assert "/_apis/testresults/codecoverage" in str(kwargs["url"])
        assert kwargs["params"]["buildId"] == 9
        assert kwargs["params"]["api-version"] == "7.2-preview.1"
        assert kwargs["json"] == {
            "coverageStats": [
                {
                    "label": "line",
                    "position": 4,
                    "total": 6,
                    "covered": 5,
                    "isDeltaAvailable": False,
                    "delta": 0.0,
                }
            ],
            "buildPlatform": "",
            "buildFlavor": "",
        }


class TestPostFileCoverage:
    """The two-step per-file upload."""

    @staticmethod
    def test_the_endpoint_is_asked_then_the_blob_is_put() -> None:
        """The signed URL from step 1 receives the JSON in step 2, without the PAT."""
        results = get_test_results_api_call(ApiCall(url=PROJECT_CALL_URL))
        endpoint = _make_mock_response(
            {"endpointSASUri": SIGNED, "endpointType": "AzureBlob"}
        )
        with (
            patch.object(
                requests.Session, "request", return_value=endpoint
            ) as api_request,
            patch("pyado.raw.test.test_results.requests.Session") as blob_cls,
        ):
            blob = blob_cls.return_value.__enter__.return_value
            blob.put.return_value.raise_for_status.return_value = None
            name = post_file_coverage(results, 9, FILES)
        asked = api_request.call_args.kwargs
        assert "/testlogstoreendpoint" in str(asked["url"])
        assert asked["params"]["testLogStoreOperationType"] == "ReadAndCreate"
        url = blob.put.call_args.args[0]
        assert url.startswith("https://blob.example.net/container-guid-buildid-9/")
        assert url.endswith(f"Intermediate/{name}?sv=1&sig=SECRET")
        assert name.endswith(".cjson")
        assert "9" in name
        headers = blob.put.call_args.kwargs["headers"]
        assert headers["x-ms-blob-type"] == "BlockBlob"
        assert "Authorization" not in headers
        body = json.loads(blob.put.call_args.kwargs["data"])
        assert body[0] == {
            "filePath": "/w/a.py",
            "lineCoverageStatus": {"1": "covered", "2": "notCovered"},
            "branchCoverageStatus": None,
        }

    @staticmethod
    def test_a_failed_blob_put_is_raised() -> None:
        """A refused upload must not look like success."""
        results = get_test_results_api_call(ApiCall(url=PROJECT_CALL_URL))
        endpoint = _make_mock_response({"endpointSASUri": SIGNED})
        with (
            patch.object(requests.Session, "request", return_value=endpoint),
            patch("pyado.raw.test.test_results.requests.Session") as blob_cls,
        ):
            blob = blob_cls.return_value.__enter__.return_value
            blob.put.return_value.raise_for_status.side_effect = requests.HTTPError(
                "403"
            )
            with pytest.raises(requests.HTTPError):
                post_file_coverage(results, 9, FILES)


class TestPublishCodeCoverage:
    """Both steps with totals computed from the files."""

    @staticmethod
    def test_the_totals_come_from_the_files_and_the_blob_goes_first() -> None:
        """2 of 3 lines covered; the blob is written before the figures."""
        order: list[str] = []

        def write_files(*_args: object, **_kwargs: object) -> str:
            order.append("files")
            return "n.cjson"

        def write_figures(*_args: object, **_kwargs: object) -> None:
            order.append("figures")

        with (
            patch("pyado.raw.test.test_results.post_file_coverage", write_files),
            patch(
                "pyado.raw.test.test_results.post_code_coverage",
                side_effect=write_figures,
            ) as figures,
        ):
            publish_code_coverage(
                ApiCall(url=PROJECT_CALL_URL),
                9,
                FILES,
                build_flavor="Debug",
                build_platform="x64",
            )
        assert order == ["files", "figures"]
        stats = figures.call_args.args[2]
        assert (stats[0].label, stats[0].covered, stats[0].total) == ("line", 2, 3)
        assert figures.call_args.kwargs == {
            "build_flavor": "Debug",
            "build_platform": "x64",
        }
