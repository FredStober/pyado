"""Tests for pyado.oop.pipelines.build_tests and the Build test/coverage methods."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from pyado.exceptions import AzureDevOpsNotFoundError
from pyado.oop import Build, CodeCoverage, TestResult, TestRun
from pyado.raw import (
    CodeCoverageData,
    CodeCoverageStats,
    CodeCoverageSummary,
    ContainerItem,
    FileCoverage,
    TestAttachmentInfo,
    TestAttachmentType,
    TestOutcome,
    TestResultCreate,
    TestResultInfo,
    TestResultRef,
    TestResultUpdate,
    TestRunInfo,
    TestRunState,
    TestRunUpdate,
)
from tests.oop.conftest import _make_build

_PATH = "pyado.oop.pipelines.build_tests.raw"
_BUILD_PATH = "pyado.oop.pipelines.build.raw"


def _run_info(run_id: int = 7, *, pair: tuple[str, str] | None = None) -> TestRunInfo:
    data: dict[str, object] = {"id": run_id, "name": f"run {run_id}"}
    if pair is not None:
        data["buildConfiguration"] = {"flavor": pair[0], "platform": pair[1]}
    return TestRunInfo.model_validate(data)


def _run(build: Build | None = None, *, pair: tuple[str, str] | None = None) -> TestRun:
    return TestRun(build or _make_build(), _run_info(pair=pair))


def _stats(
    label: str, covered: int, total: int, position: int = 4
) -> CodeCoverageStats:
    return CodeCoverageStats(
        label=label, position=position, covered=covered, total=total
    )


def _summary() -> CodeCoverageSummary:
    return CodeCoverageSummary(
        status="completed",
        coverage_data=[
            CodeCoverageData(
                build_flavor="Debug",
                build_platform="x64",
                coverage_stats=[_stats("branch", 2, 4, 5), _stats("line", 5, 6)],
            ),
            CodeCoverageData(
                build_flavor="",
                build_platform="",
                coverage_stats=[_stats("line", 0, 0)],
            ),
        ],
    )


class TestRunInfoPair:
    """The run's flavor and platform come from ``buildConfiguration``."""

    @staticmethod
    def test_pair_is_none_when_the_list_omits_it() -> None:
        info = _run_info()
        assert info.build_flavor is None
        assert info.build_platform is None

    @staticmethod
    def test_pair_is_read() -> None:
        info = _run_info(pair=("Debug", "x64"))
        assert (info.build_flavor, info.build_platform) == ("Debug", "x64")


class TestTestRun:
    """Tests for TestRun."""

    @staticmethod
    def test_properties() -> None:
        build = _make_build()
        run = TestRun(build, _run_info(9))
        assert run.id == 9
        assert run.name == "run 9"
        assert run.build is build
        assert run.project is build.project
        assert run.api_call is build.project.api_call
        assert run.info.id == 9

    @staticmethod
    def test_pair_is_fetched_lazily_once() -> None:
        run = _run()
        with patch(f"{_PATH}.get_test_run") as mock_get:
            mock_get.return_value = _run_info(pair=("Release", "arm64"))
            assert (run.flavor, run.platform) == ("Release", "arm64")
            assert run.detail.id == 7
        mock_get.assert_called_once()

    @staticmethod
    def test_pair_known_from_the_list_needs_no_call() -> None:
        run = _run(pair=("Debug", "x64"))
        with patch(f"{_PATH}.get_test_run") as mock_get:
            assert (run.flavor, run.platform) == ("Debug", "x64")
        mock_get.assert_not_called()

    @staticmethod
    def test_run_without_pair_has_empty_strings() -> None:
        run = _run()
        with patch(f"{_PATH}.get_test_run") as mock_get:
            mock_get.return_value = _run_info(pair=("", ""))
            assert (run.flavor, run.platform) == ("", "")

    @staticmethod
    def test_pair_is_empty_when_the_server_sends_none() -> None:
        run = _run()
        with patch(f"{_PATH}.get_test_run") as mock_get:
            mock_get.return_value = _run_info()
            assert (run.flavor, run.platform) == ("", "")

    @staticmethod
    def test_deleted_run_has_no_pair() -> None:
        """A deleted run is listed but answers 404; the pair reads as empty."""
        run = _run()
        with patch(f"{_PATH}.get_test_run") as mock_get:
            mock_get.side_effect = AzureDevOpsNotFoundError(404, "gone")
            assert (run.flavor, run.platform) == ("", "")
            assert run.detail.id == 7
        mock_get.assert_called_once()

    @staticmethod
    def test_refresh_rereads_the_run() -> None:
        run = _run()
        with patch(f"{_PATH}.get_test_run") as mock_get:
            mock_get.return_value = _run_info(pair=("Debug", "x64"))
            run.refresh()
            assert run.flavor == "Debug"
        mock_get.assert_called_once()

    @staticmethod
    def test_results_keep_their_run() -> None:
        run = _run()
        info = TestResultInfo.model_validate({"id": 100000, "outcome": "Passed"})
        with patch(f"{_PATH}.iter_test_results", return_value=iter([info])):
            results = run.list_results()
        assert [r.id for r in results] == [100000]
        assert results[0].run is run

    @staticmethod
    def test_run_attachments() -> None:
        run = _run()
        att = TestAttachmentInfo(id=3, file_name="a.txt")
        with (
            patch(f"{_PATH}.iter_test_run_attachments", return_value=iter([att])),
            patch(f"{_PATH}.get_test_attachment_bytes", return_value=b"x") as mock_get,
        ):
            listed = run.list_attachments()
            assert run.get_attachment_bytes(listed[0]) == b"x"
        assert listed == [att]
        assert mock_get.call_args.args[1:] == (7, 3)


class TestTestResult:
    """Tests for TestResult."""

    @staticmethod
    def _result(**fields: object) -> TestResult:
        info = TestResultInfo.model_validate({"id": 100001, **fields})
        return TestResult(_run(), info)

    def test_properties(self) -> None:
        result = self._result(outcome="Failed", testCaseTitle="t_sub")
        assert result.id == 100001
        assert result.outcome == "Failed"
        assert result.name == "t_sub"
        assert result.info.id == 100001

    def test_name_falls_back_to_the_automated_name(self) -> None:
        assert self._result(automatedTestName="shop.t").name == "shop.t"

    def test_result_attachments(self) -> None:
        result = self._result()
        att = TestAttachmentInfo(id=4, file_name="b.txt")
        with (
            patch(f"{_PATH}.iter_test_result_attachments", return_value=iter([att])),
            patch(f"{_PATH}.get_test_attachment_bytes", return_value=b"y") as mock_get,
        ):
            listed = result.list_attachments()
            assert result.get_attachment_bytes(listed[0]) == b"y"
        assert listed == [att]
        assert mock_get.call_args.args[1:] == (7, 4)
        assert mock_get.call_args.kwargs == {"result_id": 100001}


class TestCodeCoverage:
    """Tests for CodeCoverage."""

    @staticmethod
    def _entry(index: int = 0) -> CodeCoverage:
        summary = _summary()
        return CodeCoverage(_make_build(), summary.coverage_data[index], summary.status)

    def test_properties(self) -> None:
        entry = self._entry()
        assert (entry.flavor, entry.platform, entry.status) == (
            "Debug",
            "x64",
            "completed",
        )
        assert len(entry.stats) == 2
        assert entry.build.id == 100

    def test_stat_is_found_by_label_not_position(self) -> None:
        entry = self._entry()
        stat = entry.stat("line")
        assert stat is not None
        assert (stat.covered, stat.total) == (5, 6)

    def test_stat_matches_the_finalised_label(self) -> None:
        data = CodeCoverageData(coverage_stats=[_stats("Lines", 1, 2)])
        entry = CodeCoverage(_make_build(), data, "finalized")
        assert entry.stat("line") is not None

    def test_missing_stat(self) -> None:
        assert self._entry().stat("function") is None

    def test_percent(self) -> None:
        assert self._entry().percent("branch") == pytest.approx(50.0)

    def test_percent_is_none_without_total_or_stat(self) -> None:
        entry = self._entry(1)
        assert entry.percent() is None
        assert entry.percent("branch") is None


class TestBuildTests:
    """Tests for the Build methods that wrap runs and coverage."""

    @staticmethod
    def test_iter_test_runs() -> None:
        build = _make_build()
        with patch(
            f"{_BUILD_PATH}.iter_build_test_runs",
            return_value=iter([_run_info(1), _run_info(2)]),
        ):
            runs = build.list_test_runs()
        assert [r.id for r in runs] == [1, 2]
        assert all(r.build is build for r in runs)

    @staticmethod
    def test_deleted_runs_are_skipped_unless_asked_for() -> None:
        build = _make_build()
        deleted = TestRunInfo.model_validate({"id": 3, "name": "gone", "state": "255"})
        listed = [_run_info(1), deleted]
        with patch(
            f"{_BUILD_PATH}.iter_build_test_runs", side_effect=lambda *_: iter(listed)
        ):
            assert [r.id for r in build.list_test_runs()] == [1]
            both = build.list_test_runs(include_deleted=True)
        assert [(r.id, r.is_deleted) for r in both] == [(1, False), (3, True)]

    @staticmethod
    def test_results_are_flattened_across_runs() -> None:
        build = _make_build()
        infos = {
            1: [TestResultInfo.model_validate({"id": 100000})],
            2: [TestResultInfo.model_validate({"id": 100000})],
        }
        with (
            patch(
                f"{_BUILD_PATH}.iter_build_test_runs",
                return_value=iter([_run_info(1), _run_info(2)]),
            ),
            patch(
                f"{_PATH}.iter_test_results",
                side_effect=lambda _call, run_id: iter(infos[run_id]),
            ),
        ):
            results = build.list_test_results()
        assert [(r.run.id, r.id) for r in results] == [(1, 100000), (2, 100000)]

    @staticmethod
    def test_code_coverage_entries_and_lookup() -> None:
        build = _make_build()
        with patch(f"{_BUILD_PATH}.get_code_coverage", return_value=_summary()):
            entries = build.list_code_coverage()
            debug = build.get_code_coverage("Debug", "x64")
            empty = build.get_code_coverage()
            missing = build.get_code_coverage("Release", "x64")
        assert [(e.flavor, e.platform) for e in entries] == [("Debug", "x64"), ("", "")]
        assert debug is not None
        assert empty is not None
        assert (empty.flavor, empty.platform) == ("", "")
        assert missing is None

    @staticmethod
    def test_no_coverage_yields_nothing() -> None:
        build = _make_build()
        with patch(
            f"{_BUILD_PATH}.get_code_coverage", return_value=CodeCoverageSummary()
        ):
            assert build.list_code_coverage() == []

    @staticmethod
    def test_coverage_is_joined_to_a_run_by_pair() -> None:
        build = _make_build()
        run = _run(build, pair=("Debug", "x64"))
        with patch(f"{_BUILD_PATH}.get_code_coverage", return_value=_summary()):
            entry = build.get_coverage_for_run(run)
        assert entry is not None
        assert entry.platform == "x64"

    @staticmethod
    def test_attachments() -> None:
        build = _make_build()
        with patch(f"{_BUILD_PATH}.iter_build_attachments") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            assert len(build.list_attachments("t")) == 1
        assert mock_iter.call_args.args[1:] == (100, "t")


class TestBuildContainer:
    """Tests for the build file container methods."""

    @staticmethod
    def test_items_and_file() -> None:
        build = _make_build()
        item = ContainerItem(path="a/b.txt", item_type="file")
        with (
            patch(f"{_BUILD_PATH}.get_build_container_id", return_value=5),
            patch(f"{_BUILD_PATH}.get_container_api_call") as mock_call,
            patch(f"{_BUILD_PATH}.iter_container_items", return_value=iter([item])),
            patch(f"{_BUILD_PATH}.get_container_item_bytes", return_value=b"z"),
        ):
            assert build.list_container_items("a") == [item]
            assert build.get_container_file("a/b.txt") == b"z"
        assert mock_call.call_args.args[1] == 5

    @staticmethod
    def test_build_without_a_container() -> None:
        build = _make_build()
        with patch(f"{_BUILD_PATH}.get_build_container_id", return_value=None):
            assert build.list_container_items() == []
            assert build.get_container_file("a.txt") is None


def _result_create(name: str = "t_add") -> TestResultCreate:
    return TestResultCreate(
        test_case_title=name,
        automated_test_name=f"shop.{name}",
        test_case={"name": name},
        outcome=TestOutcome.PASSED,
    )


class TestRunWrites:
    """Tests for the TestRun methods that write."""

    @staticmethod
    def test_add_results_reads_them_back() -> None:
        run = _run()
        info = TestResultInfo.model_validate({"id": 100000, "outcome": "Passed"})
        with (
            patch(
                f"{_PATH}.post_test_results",
                return_value=[TestResultRef(id=100000)],
            ) as mock_post,
            patch(f"{_PATH}.get_test_result", return_value=info) as mock_get,
        ):
            results = run.add_results([_result_create()])
        assert [(r.run, r.id, r.outcome) for r in results] == [(run, 100000, "Passed")]
        assert mock_post.call_args.args[1] == 7
        assert mock_get.call_args.args[1:] == (7, 100000)

    @staticmethod
    def test_complete_and_update_reread_the_run() -> None:
        run = _run()
        with (
            patch(f"{_PATH}.patch_test_run") as mock_patch,
            patch(f"{_PATH}.get_test_run", return_value=_run_info()),
        ):
            run.complete()
        assert mock_patch.call_args.args[1:] == (
            7,
            TestRunUpdate(state=TestRunState.COMPLETED),
        )

    @staticmethod
    def test_delete_marks_the_run_deleted() -> None:
        run = _run()
        with patch(f"{_PATH}.delete_test_run") as mock_del:
            run.delete()
        mock_del.assert_called_once()
        assert run.is_deleted

    @staticmethod
    def test_add_attachment_encodes_the_content() -> None:
        run = _run()
        with patch(f"{_PATH}.post_test_run_attachment", return_value=5) as mock_post:
            attachment_id = run.add_attachment(
                "log.txt", b"hi", attachment_type=TestAttachmentType.CONSOLE_LOG
            )
        request = mock_post.call_args.args[2]
        assert attachment_id == 5
        assert (request.file_name, request.stream) == ("log.txt", "aGk=")
        assert request.attachment_type == TestAttachmentType.CONSOLE_LOG


class TestResultWrites:
    """Tests for the TestResult methods that write."""

    @staticmethod
    def _result() -> TestResult:
        return TestResult(
            _run(), TestResultInfo.model_validate({"id": 100001, "outcome": "Failed"})
        )

    def test_update_uses_this_results_id_and_rereads(self) -> None:
        result = self._result()
        new_info = TestResultInfo.model_validate({"id": 100001, "outcome": "Passed"})
        with (
            patch(f"{_PATH}.patch_test_results") as mock_patch,
            patch(f"{_PATH}.get_test_result", return_value=new_info),
        ):
            result.update(TestResultUpdate(id=0, outcome=TestOutcome.PASSED))
        sent = mock_patch.call_args.args[2]
        assert [(u.id, u.outcome) for u in sent] == [(100001, TestOutcome.PASSED)]
        assert result.outcome == "Passed"

    def test_link_bugs(self) -> None:
        result = self._result()
        with (
            patch(f"{_PATH}.patch_test_results") as mock_patch,
            patch(f"{_PATH}.get_test_result", return_value=result.info),
        ):
            result.link_bugs([11, 12])
        sent = mock_patch.call_args.args[2][0]
        assert sent.associated_bugs is not None
        assert [b.id for b in sent.associated_bugs] == [11, 12]

    def test_add_attachment(self) -> None:
        result = self._result()
        with patch(f"{_PATH}.post_test_result_attachment", return_value=9) as mock_post:
            assert result.add_attachment("a.txt", b"x", comment="c") == 9
        assert mock_post.call_args.args[1:3] == (7, 100001)
        assert mock_post.call_args.args[3].comment == "c"


class TestBuildWrites:
    """Tests for the Build methods that create runs and publish coverage."""

    @staticmethod
    def test_add_test_run_tags_the_run_with_the_pair() -> None:
        build = _make_build()
        with patch(
            f"{_BUILD_PATH}.post_test_run",
            return_value=_run_info(5, pair=("Debug", "x64")),
        ) as mock_post:
            run = build.add_test_run("unit", flavor="Debug", platform="x64")
        request = mock_post.call_args.args[1]
        assert (request.build_flavor, request.build_platform) == ("Debug", "x64")
        assert request.build.id == 100
        assert (run.id, run.flavor, run.platform) == (5, "Debug", "x64")

    @staticmethod
    def test_publish_code_coverage_passes_the_pair() -> None:
        build = _make_build()
        files = [FileCoverage(file_path="/a.py", line_coverage_status={"1": "covered"})]
        with patch(f"{_BUILD_PATH}.publish_code_coverage") as mock_pub:
            build.publish_code_coverage(files, flavor="Debug", platform="x64")
        assert mock_pub.call_args.args[1:] == (100, files)
        assert mock_pub.call_args.kwargs == {
            "label": "line",
            "build_flavor": "Debug",
            "build_platform": "x64",
        }

    @staticmethod
    def test_publish_coverage_report() -> None:
        build = _make_build()
        with (
            patch(f"{_BUILD_PATH}.get_build_container_id", return_value=5),
            patch(f"{_BUILD_PATH}.publish_coverage_report") as mock_pub,
        ):
            build.publish_coverage_report({"index.html": b"<html/>"})
        assert mock_pub.call_args.args[2:4] == (100, 5)

    @staticmethod
    def test_publish_coverage_report_needs_a_container() -> None:
        build = _make_build()
        with (
            patch(f"{_BUILD_PATH}.get_build_container_id", return_value=None),
            pytest.raises(ValueError, match="no file container"),
        ):
            build.publish_coverage_report({"index.html": b"x"})


class TestBuildSummaries:
    """Tests for the task summary methods of Build."""

    @staticmethod
    def test_iter_summaries() -> None:
        build = _make_build()
        with patch(f"{_BUILD_PATH}.iter_build_summaries") as mock_iter:
            mock_iter.return_value = iter([MagicMock()])
            assert len(build.list_summaries()) == 1
        assert mock_iter.call_args.args[1] == 100

    @staticmethod
    def test_add_summaries_writes_to_the_builds_timeline() -> None:
        build = _make_build()
        plan = uuid4()
        record = uuid4()
        with (
            patch.object(type(build._api_call), "get", return_value={"id": str(plan)}),
            patch(f"{_BUILD_PATH}.put_record_summaries") as mock_put,
        ):
            build.add_summaries(record, {"card.md": "# hi"})
        assert mock_put.call_args.args[1:] == (str(record), {"card.md": "# hi"})
        url = str(mock_put.call_args.args[0].url)
        assert str(plan) in url
        assert str(build.project.id) in url
        assert build.project.name not in url

    @staticmethod
    def test_add_summaries_needs_a_timeline() -> None:
        build = _make_build()
        with (
            patch.object(type(build._api_call), "get", return_value={}),
            pytest.raises(ValueError, match="no timeline yet"),
        ):
            build.add_summaries(uuid4(), {"a.md": "x"})
