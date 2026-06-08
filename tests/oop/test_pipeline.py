"""Tests for pyado.oop.pipelines._build pipeline helpers — OOP layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import cast
from unittest.mock import MagicMock, patch
from uuid import uuid4

import requests

from pyado.oop import Pipeline, Project
from pyado.oop.pipelines._build import (
    approve_pipeline,
    iter_pending_approvals,
    reject_pipeline,
    send_job_event,
    send_job_feed,
    update_timeline_records,
)
from pyado.oop.pipelines.pipeline import PipelineRun
from pyado.raw import (
    ApiCall,
    BuildRecordInfo,
    BuildStatus,
    JobEventName,
    JobEventResult,
    PipelineApprovalStatus,
    PipelineResourcePermissions,
    PipelineResourceType,
    PipelineRunInfo,
    VariableInfo,
)
from tests.conftest import NOW_ISO, _make_mock_response, make_build_record_dict
from tests.oop.conftest import (
    _make_build,
    _make_pipeline,
    _make_pipeline_resource_permissions,
    _make_project,
    _make_service,
    _pipeline_info,
    _pipeline_run_info,
    _project_info,
)

HUB_NAME = "Build"
PLAN_ID = uuid4()
TIMELINE_ID = uuid4()
JOB_ID = uuid4()
TASK_ID = uuid4()
LOG_ID = 7


class TestSendJobFeed:
    """Tests for send_job_feed."""

    @staticmethod
    def test_posts_messages_to_feed(api_call: ApiCall) -> None:
        """send_job_feed POSTs the messages payload to the feed endpoint."""
        mock_response = _make_mock_response()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            send_job_feed(api_call, ["line 1", "line 2"])
        mock_req.assert_called_once()
        call = mock_req.call_args
        assert call.args[0] == "POST"
        # Verify payload was sent
        sent_json = call.kwargs.get("json") or {}
        assert sent_json.get("count") == 2
        assert sent_json.get("value") == ["line 1", "line 2"]


class TestSendJobEvent:
    """Tests for send_job_event."""

    @staticmethod
    def test_posts_job_event_payload(api_call: ApiCall) -> None:
        """send_job_event POSTs a correctly structured event payload."""
        mock_response = _make_mock_response()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            send_job_event(
                api_call,
                TASK_ID,
                JOB_ID,
                cast("JobEventName", "TaskCompleted"),
                cast("JobEventResult", "succeeded"),
            )
        mock_req.assert_called_once()
        call = mock_req.call_args
        assert call.args[0] == "POST"
        sent_json = call.kwargs.get("json") or {}
        assert sent_json.get("name") == "TaskCompleted"
        assert sent_json.get("result") == "succeeded"
        assert sent_json.get("taskId") == str(TASK_ID)
        assert sent_json.get("jobId") == str(JOB_ID)


class TestUpdateTimelineRecords:
    """Tests for update_timeline_records."""

    @staticmethod
    def test_patches_records_endpoint(api_call: ApiCall) -> None:
        """update_timeline_records PATCHes the records endpoint."""
        record = BuildRecordInfo.model_validate(make_build_record_dict())
        mock_response = _make_mock_response(json_data={"count": 1, "value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            update_timeline_records(api_call, [record])
        mock_req.assert_called_once()
        call = mock_req.call_args
        assert call.args[0] == "PATCH"
        sent_json = call.kwargs.get("json") or {}
        assert sent_json.get("count") == 1


class TestIterPendingApprovals:
    """Tests for iter_pending_approvals."""

    @staticmethod
    def test_delegates_to_iter_approvals_with_pending_state(
        api_call: ApiCall,
    ) -> None:
        """Delegates to iter_approvals with state=pending."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_pending_approvals(api_call))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("state") == "pending"

    @staticmethod
    def test_forwards_pipeline_run_ids(api_call: ApiCall) -> None:
        """Forwards pipeline_run_ids as pipelineIds query parameter."""
        mock_response = _make_mock_response({"value": []})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            list(iter_pending_approvals(api_call, pipeline_run_ids=[7]))
        params = mock_req.call_args.kwargs.get("params") or {}
        assert params.get("pipelineIds") == "7"


class TestApprovePipeline:
    """Tests for approve_pipeline."""

    @staticmethod
    def test_patches_approval_with_approved_status(api_call: ApiCall) -> None:
        """Sends a PATCH with status=approved for the given approval ID."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            approve_pipeline(api_call, "approval-uuid-1")
        assert mock_req.call_args.args[0] == "PATCH"
        sent_json = mock_req.call_args.kwargs.get("json") or []
        assert sent_json[0]["approvalId"] == "approval-uuid-1"
        assert sent_json[0]["status"] == "approved"

    @staticmethod
    def test_includes_comment_in_payload(api_call: ApiCall) -> None:
        """Includes the provided comment in the approval payload."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            approve_pipeline(api_call, "approval-uuid-2", comment="LGTM")
        sent_json = mock_req.call_args.kwargs.get("json") or []
        assert sent_json[0]["comment"] == "LGTM"


class TestRejectPipeline:
    """Tests for reject_pipeline."""

    @staticmethod
    def test_patches_approval_with_rejected_status(api_call: ApiCall) -> None:
        """Sends a PATCH with status=rejected for the given approval ID."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            reject_pipeline(api_call, "approval-uuid-3")
        assert mock_req.call_args.args[0] == "PATCH"
        sent_json = mock_req.call_args.kwargs.get("json") or []
        assert sent_json[0]["approvalId"] == "approval-uuid-3"
        assert sent_json[0]["status"] == "rejected"

    @staticmethod
    def test_includes_comment_in_payload(api_call: ApiCall) -> None:
        """Includes the provided comment in the rejection payload."""
        mock_response = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            reject_pipeline(api_call, "approval-uuid-4", comment="Not ready")
        sent_json = mock_req.call_args.kwargs.get("json") or []
        assert sent_json[0]["comment"] == "Not ready"


# ---------------------------------------------------------------------------
# OOP Pipeline tests
# ---------------------------------------------------------------------------


class TestPipeline:
    def test_id(self) -> None:
        assert _make_pipeline(7).id == 7

    def test_name(self) -> None:
        assert _make_pipeline().name == "MyPipeline"

    def test_info_from_pre_fetched(self) -> None:
        assert _make_pipeline().info.id == 7

    def test_info_lazy_fetch(self) -> None:
        proj = _make_project()
        pipe = Pipeline(proj, 7, "MyPipeline")
        assert pipe._info is None
        with patch("pyado.oop.pipelines.pipeline.raw.get_pipeline") as mock_get:
            mock_get.return_value = _pipeline_info(7)
            info = pipe.info
        assert info.id == 7

    def test_api_call_is_project_level(self) -> None:
        pipe = _make_pipeline()
        assert pipe.api_call is pipe.project.api_call

    def test_project_reference(self) -> None:
        proj = _make_project()
        pipe = Pipeline(proj, 7, "MyPipeline")
        assert pipe.project is proj

    def test_org_via_project(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        pipe = Pipeline(proj, 7, "MyPipeline")
        assert pipe.org is svc.org

    def test_refresh_clears_info(self) -> None:
        pipe = _make_pipeline()
        pipe.refresh()
        assert pipe._info is None

    def test_iter_runs_delegates(self) -> None:
        with patch("pyado.oop.pipelines.pipeline.raw.iter_pipeline_runs") as mock_iter:
            mock_iter.return_value = iter([])
            list(_make_pipeline().iter_runs())
        assert mock_iter.call_args.args[1] == 7

    def test_start_run_no_args_passes_none(self) -> None:
        with patch("pyado.oop.pipelines.pipeline.raw.post_pipeline_run") as mock_run:
            mock_run.return_value = MagicMock()
            _make_pipeline().start_run()
        assert mock_run.call_args.args[2] is None

    def test_start_run_with_variables_builds_request(self) -> None:
        with patch("pyado.oop.pipelines.pipeline.raw.post_pipeline_run") as mock_run:
            mock_run.return_value = MagicMock()
            _make_pipeline().start_run(variables={"env": VariableInfo(value="test")})
        request_arg = mock_run.call_args.args[2]
        assert request_arg is not None
        assert request_arg.variables == {"env": VariableInfo(value="test")}

    def test_get_run_delegates(self) -> None:
        with patch("pyado.oop.pipelines.pipeline.raw.get_pipeline_run") as mock_get:
            mock_get.return_value = MagicMock()
            _make_pipeline().get_run(42)
        assert mock_get.call_args.args[2] == 42


# ---------------------------------------------------------------------------
# OOP PipelineAuthorizeResource tests
# ---------------------------------------------------------------------------


class TestPipelineAuthorizeResource:
    def test_authorize_resource_delegates(self) -> None:
        pipe = _make_pipeline()
        with patch(
            "pyado.oop.pipelines.pipeline.raw.patch_pipeline_permission"
        ) as mock_post:
            mock_post.return_value = _make_pipeline_resource_permissions()
            result = pipe.authorize_resource(PipelineResourceType.VARIABLE_GROUP, "42")
        assert isinstance(result, PipelineResourcePermissions)
        mock_post.assert_called_once()

    def test_authorize_resource_passes_pipeline_id(self) -> None:
        pipe = _make_pipeline(pipeline_id=7)
        with patch(
            "pyado.oop.pipelines.pipeline.raw.patch_pipeline_permission"
        ) as mock_post:
            mock_post.return_value = _make_pipeline_resource_permissions()
            pipe.authorize_resource(PipelineResourceType.ENDPOINT, "svc-conn-1")
        call = mock_post.call_args
        assert call.args[3] == 7  # pipeline_id

    def test_authorize_resource_default_authorized_true(self) -> None:
        pipe = _make_pipeline()
        with patch(
            "pyado.oop.pipelines.pipeline.raw.patch_pipeline_permission"
        ) as mock_post:
            mock_post.return_value = _make_pipeline_resource_permissions()
            pipe.authorize_resource(PipelineResourceType.QUEUE, "1")
        call = mock_post.call_args
        assert call.kwargs["authorized"] is True

    def test_authorize_resource_can_deauthorize(self) -> None:
        pipe = _make_pipeline()
        with patch(
            "pyado.oop.pipelines.pipeline.raw.patch_pipeline_permission"
        ) as mock_post:
            mock_post.return_value = _make_pipeline_resource_permissions(
                authorized=False
            )
            pipe.authorize_resource(
                PipelineResourceType.REPOSITORY, "proj/repo", authorized=False
            )
        call = mock_post.call_args
        assert call.kwargs["authorized"] is False


# ---------------------------------------------------------------------------
# OOP PipelineGetLatestRun tests
# ---------------------------------------------------------------------------


class TestPipelineGetLatestRun:
    def test_returns_latest_run_when_runs_exist(self) -> None:
        run = PipelineRunInfo.model_validate(
            {
                "id": 99,
                "name": "20240101.1",
                "state": "completed",
                "result": "succeeded",
                "createdDate": NOW_ISO,
                "pipeline": {
                    "id": 7,
                    "revision": 1,
                    "name": "MyPipeline",
                    "folder": "\\",
                    "url": "https://x",
                },
                "url": "https://dev.azure.com/testorg/TestProject/_apis/pipelines/7/runs/99",
            }
        )
        with patch("pyado.oop.pipelines.pipeline.raw.iter_pipeline_runs") as mock_iter:
            mock_iter.return_value = iter([run])
            result = _make_pipeline().get_latest_run()
        assert result is not None
        assert result.info is run

    def test_returns_none_when_no_runs(self) -> None:
        with patch("pyado.oop.pipelines.pipeline.raw.iter_pipeline_runs") as mock_iter:
            mock_iter.return_value = iter([])
            result = _make_pipeline().get_latest_run()
        assert result is None


# ---------------------------------------------------------------------------
# OOP PipelineCancelRun tests
# ---------------------------------------------------------------------------


class TestPipelineCancelRun:
    def test_cancel_run_delegates_to_high(self) -> None:
        run = PipelineRunInfo.model_validate(
            {
                "id": 55,
                "name": "20240101.5",
                "state": "canceling",
                "result": None,
                "createdDate": NOW_ISO,
                "pipeline": {
                    "id": 7,
                    "revision": 1,
                    "name": "MyPipeline",
                    "folder": "\\",
                    "url": "https://x",
                },
                "url": "https://dev.azure.com/testorg/TestProject/_apis/pipelines/7/runs/55",
            }
        )
        with patch(
            "pyado.oop.pipelines.pipeline._build.cancel_pipeline_run"
        ) as mock_cancel:
            mock_cancel.return_value = run
            result = _make_pipeline(7).cancel_run(55)
        assert result is run
        assert mock_cancel.call_args.args[1] == 7
        assert mock_cancel.call_args.args[2] == 55


# ---------------------------------------------------------------------------
# OOP PipelineRunProperties tests
# ---------------------------------------------------------------------------


class TestPipelineRunProperties:
    def _make_run(self) -> PipelineRun:
        return PipelineRun(_make_pipeline(), _pipeline_run_info())

    def test_info_returns_pipeline_run_info(self) -> None:
        info = _pipeline_run_info()
        run = PipelineRun(_make_pipeline(), info)
        assert run.info is info

    def test_id_returns_numeric_run_id(self) -> None:
        run = PipelineRun(_make_pipeline(), _pipeline_run_info(run_id=55))
        assert run.id == 55

    def test_status_returns_state(self) -> None:
        run = self._make_run()
        assert run.status == "canceling"

    def test_result_returns_none_when_not_completed(self) -> None:
        run = self._make_run()
        assert run.result is None

    def test_pipeline_reference(self) -> None:
        pipe = _make_pipeline()
        run = PipelineRun(pipe, _pipeline_run_info())
        assert run.pipeline is pipe

    def test_org_reference(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        pipe = Pipeline(proj, 7, "MyPipeline")
        run = PipelineRun(pipe, _pipeline_run_info())
        assert run.org is svc.org

    def test_project_reference(self) -> None:
        proj = _make_project()
        pipe = Pipeline(proj, 7, "MyPipeline")
        run = PipelineRun(pipe, _pipeline_run_info())
        assert run.project is proj

    def test_api_call_returns_project_api_call(self) -> None:
        proj = _make_project()
        pipe = Pipeline(proj, 7, "MyPipeline")
        run = PipelineRun(pipe, _pipeline_run_info())
        assert run.api_call is proj.api_call

    def test_cancel_updates_info_and_returns_self(self) -> None:
        new_info = _pipeline_run_info(run_id=100)
        run = PipelineRun(_make_pipeline(), _pipeline_run_info())
        with patch(
            "pyado.oop.pipelines.pipeline._build.cancel_pipeline_run"
        ) as mock_cancel:
            mock_cancel.return_value = new_info
            result = run.cancel()
        assert result is run
        assert run.info is new_info

    def test_refresh_updates_info(self) -> None:
        refreshed = _pipeline_run_info(run_id=100)
        run = PipelineRun(_make_pipeline(), _pipeline_run_info(run_id=100))
        with patch("pyado.oop.pipelines.pipeline.raw.get_pipeline_run") as mock_get:
            mock_get.return_value = refreshed
            run.refresh()
            # refresh() lazily invalidates; the actual fetch happens on next info access
            assert run.info is refreshed

    def test_refresh_passes_pipeline_and_run_ids(self) -> None:
        pipe = _make_pipeline(7)
        run = PipelineRun(pipe, _pipeline_run_info(run_id=55))
        with patch("pyado.oop.pipelines.pipeline.raw.get_pipeline_run") as mock_get:
            mock_get.return_value = _pipeline_run_info(run_id=55)
            run.refresh()
            # refresh() lazily invalidates; trigger the fetch inside the mock context
            _ = run.info
        assert mock_get.call_args.args[1] == 7
        assert mock_get.call_args.args[2] == 55

    def test_iter_approvals_scopes_to_run_id(self) -> None:
        """Passes the run ID as pipeline_run_ids to raw.iter_approvals."""
        run = PipelineRun(_make_pipeline(), _pipeline_run_info(run_id=55))
        with patch(
            "pyado.oop.pipelines.pipeline.raw.iter_approvals", return_value=iter([])
        ) as mock_iter:
            list(run.iter_approvals())
        mock_iter.assert_called_once_with(
            run.api_call,
            state=None,
            pipeline_run_ids=[55],
        )

    def test_iter_approvals_passes_state_filter(self) -> None:
        """Forwards the state argument to raw.iter_approvals."""
        run = PipelineRun(_make_pipeline(), _pipeline_run_info(run_id=10))
        with patch(
            "pyado.oop.pipelines.pipeline.raw.iter_approvals", return_value=iter([])
        ) as mock_iter:
            list(run.iter_approvals(state=PipelineApprovalStatus.PENDING))
        mock_iter.assert_called_once_with(
            run.api_call,
            state=PipelineApprovalStatus.PENDING,
            pipeline_run_ids=[10],
        )

    def test_list_approvals_delegates_to_iter(self) -> None:
        """list_approvals returns results of iter_approvals as a list."""
        run = PipelineRun(_make_pipeline(), _pipeline_run_info())
        with patch.object(run, "iter_approvals", return_value=iter([])):
            assert run.list_approvals() == []


class TestPipelineIterRunsYield:
    def test_iter_runs_yields_pipeline_run_wrappers(self) -> None:
        info = _pipeline_run_info(run_id=77)
        with patch("pyado.oop.pipelines.pipeline.raw.iter_pipeline_runs") as mock_iter:
            mock_iter.return_value = iter([info])
            result = list(_make_pipeline().iter_runs())
        assert len(result) == 1
        assert isinstance(result[0], PipelineRun)
        assert result[0].info is info


class TestPipelineIterRunsTop:
    def test_iter_runs_passes_top_to_raw(self) -> None:
        with patch("pyado.oop.pipelines.pipeline.raw.iter_pipeline_runs") as mock_iter:
            mock_iter.return_value = iter([])
            list(_make_pipeline().iter_runs(top=3))
        assert mock_iter.call_args.kwargs.get("top") == 3

    def test_iter_runs_passes_none_top_by_default(self) -> None:
        with patch("pyado.oop.pipelines.pipeline.raw.iter_pipeline_runs") as mock_iter:
            mock_iter.return_value = iter([])
            list(_make_pipeline().iter_runs())
        assert mock_iter.call_args.kwargs.get("top") is None


class TestPipelineIterBuilds:
    def test_delegates_to_project_iter_builds(self) -> None:
        build = _make_build(build_id=5, pipeline_id=7)
        pipe = _make_pipeline()
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.iter_builds",
                return_value=iter([build.info]),
            ) as mock_iter,
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.get_build_api_call",
                return_value=build.api_call,
            ),
        ):
            result = list(pipe.iter_builds())
        assert len(result) == 1
        sc = mock_iter.call_args.kwargs["search_criteria"]
        assert sc.definition_id == 7

    def test_forwards_status_filter(self) -> None:
        pipe = _make_pipeline()
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.iter_builds",
                return_value=iter([]),
            ) as mock_iter,
            patch("pyado.oop.pipelines.project_pipelines.raw.get_build_api_call"),
        ):
            list(pipe.iter_builds(status_filter=BuildStatus.COMPLETED))
        sc = mock_iter.call_args.kwargs["search_criteria"]
        assert sc.status_filter == BuildStatus.COMPLETED

    def test_forwards_branch_name(self) -> None:
        pipe = _make_pipeline()
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.iter_builds",
                return_value=iter([]),
            ) as mock_iter,
            patch("pyado.oop.pipelines.project_pipelines.raw.get_build_api_call"),
        ):
            list(pipe.iter_builds(branch_name="refs/heads/main"))
        assert (
            mock_iter.call_args.kwargs["search_criteria"].branch_name
            == "refs/heads/main"
        )

    def test_forwards_top(self) -> None:
        pipe = _make_pipeline()
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.iter_builds",
                return_value=iter([]),
            ) as mock_iter,
            patch("pyado.oop.pipelines.project_pipelines.raw.get_build_api_call"),
        ):
            list(pipe.iter_builds(top=10))
        assert mock_iter.call_args.kwargs["search_criteria"].top == 10


class TestPipelineListMethods:
    def test_list_runs_delegates(self) -> None:
        pipe = _make_pipeline()
        with patch.object(pipe, "iter_runs", return_value=iter([])):
            assert pipe.list_runs() == []

    def test_list_builds_delegates(self) -> None:
        pipe = _make_pipeline()
        with patch.object(pipe, "iter_builds", return_value=iter([])):
            assert pipe.list_builds() == []
