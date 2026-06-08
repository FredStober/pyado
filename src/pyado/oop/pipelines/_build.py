"""Higher-level wrappers for build and pipeline operations."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator

from pyado.raw import (
    ApiCall,
    BuildDetails,
    BuildQueueRequest,
    BuildRecordInfo,
    BuildStatus,
    JobEventName,
    JobEventPayload,
    JobEventResult,
    JobFeedPayload,
    JobId,
    PipelineApproval,
    PipelineApprovalStatus,
    PipelineApprovalUpdateRequest,
    PipelineId,
    PipelineRunInfo,
    TaskId,
    TimelineRecordsUpdatePayload,
    WorkItemId,
    get_build_api_call,
    get_pipeline_run,
    iter_approvals,
    patch_approvals,
    patch_timeline_records,
    post_build,
    post_job_event,
    post_job_feed,
)
from pyado.raw import (
    iter_build_work_item_ids as _iter_build_work_item_ids,
)
from pyado.raw import (
    patch_build as _patch_build,
)


def cancel_build(build_api_call: ApiCall) -> BuildDetails:
    """Request cancellation of a running build.

    Args:
        build_api_call: Build-level ADO API call (from
            raw.get_build_api_call).

    Returns:
        BuildDetails reflecting the updated build state (status will be
        ``"cancelling"`` immediately; it transitions to ``"completed"`` with
        result ``"canceled"`` once the agent acknowledges the request).
    """
    return _patch_build(build_api_call, BuildStatus.CANCELLING)


def cancel_pipeline_run(
    project_api_call: ApiCall,
    pipeline_id: int,
    run_id: int,
) -> PipelineRunInfo:
    """Cancel a Pipelines v2 run via the Build API.

    The Pipelines v2 REST API has no cancel endpoint; cancellation is
    performed through the Build API (PATCH /build/builds/{buildId} with
    status "cancelling"), then the updated run is re-fetched via the
    Pipelines API to return a PipelineRunInfo.

    Args:
        project_api_call: Project-level ADO API call.
        pipeline_id: Numeric pipeline ID.
        run_id: Numeric run (build) ID to cancel.

    Returns:
        PipelineRunInfo reflecting the cancelling/canceled state.
    """
    build_api_call = get_build_api_call(project_api_call, run_id)
    _patch_build(build_api_call, BuildStatus.CANCELLING)
    return get_pipeline_run(project_api_call, pipeline_id, run_id)


def iter_build_work_item_ids(build_api_call: ApiCall) -> Iterator[WorkItemId]:
    """Iterate over work item IDs linked to a build.

    Args:
        build_api_call: Build-level ADO API call (from
            raw.get_build_api_call).

    Yields:
        Integer work item IDs associated with the build.
    """
    for ref in _iter_build_work_item_ids(build_api_call):
        yield ref.id


def start_build(
    project_api_call: ApiCall,
    definition_id: PipelineId,
    *,
    source_branch: str | None = None,
    source_version: str | None = None,
    parameters: dict[str, str] | None = None,
) -> BuildDetails:
    """Queue a new build run for a pipeline definition.

    Args:
        project_api_call: Project-level ADO API call.
        definition_id: ID of the pipeline definition to run.
        source_branch: Source branch to build (e.g. ``"refs/heads/main"``).
            Uses the definition default when omitted.
        source_version: Commit SHA to build. Uses the branch HEAD when omitted.
        parameters: Optional key/value pairs passed to the pipeline as
            template parameters (serialised as a JSON string by ADO).

    Returns:
        BuildDetails for the queued build run.
    """
    return post_build(
        project_api_call,
        BuildQueueRequest(
            definition_id=definition_id,
            source_branch=source_branch,
            source_version=source_version,
            parameters=parameters,
        ),
    )


def send_job_feed(job_api_call: ApiCall, messages: list[str]) -> None:
    """Send messages to the feed of the running task.

    Args:
        job_api_call: Job-level ADO API call.
        messages: Log lines to append to the feed.
    """
    post_job_feed(job_api_call, JobFeedPayload(value=messages, count=len(messages)))


def send_job_event(
    plan_api_call: ApiCall,
    task_id: TaskId,
    job_id: JobId,
    job_event_name: JobEventName,
    job_event_result: JobEventResult,
) -> None:
    """Notify the pipeline that the task has completed.

    Args:
        plan_api_call: Plan-level ADO API call.
        task_id: UUID of the task.
        job_id: UUID of the job.
        job_event_name: Event name (e.g. ``"TaskCompleted"``).
        job_event_result: Result of the task (``"succeeded"`` or ``"failed"``).
    """
    post_job_event(
        plan_api_call,
        JobEventPayload(
            name=job_event_name,
            task_id=task_id,
            job_id=job_id,
            result=job_event_result,
        ),
    )


def update_timeline_records(
    timeline_api_call: ApiCall,
    records: list[BuildRecordInfo],
) -> None:
    """Update the timeline records for a build.

    Args:
        timeline_api_call: Timeline-level ADO API call.
        records: List of build record updates to apply.
    """
    patch_timeline_records(
        timeline_api_call,
        TimelineRecordsUpdatePayload(value=records, count=len(records)),
    )


def approve_pipeline(
    project_api_call: ApiCall,
    approval_id: str,
    *,
    comment: str = "",
) -> None:
    """Approve a pending pipeline environment approval.

    Args:
        project_api_call: Project-level ADO API call.
        approval_id: UUID string of the approval to approve.
        comment: Optional comment to attach to the approval.
    """
    patch_approvals(
        project_api_call,
        [
            PipelineApprovalUpdateRequest(
                approval_id=approval_id,
                status=PipelineApprovalStatus.APPROVED,
                comment=comment,
            )
        ],
    )


def reject_pipeline(
    project_api_call: ApiCall,
    approval_id: str,
    *,
    comment: str = "",
) -> None:
    """Reject a pending pipeline environment approval.

    Args:
        project_api_call: Project-level ADO API call.
        approval_id: UUID string of the approval to reject.
        comment: Optional comment to attach to the rejection.
    """
    patch_approvals(
        project_api_call,
        [
            PipelineApprovalUpdateRequest(
                approval_id=approval_id,
                status=PipelineApprovalStatus.REJECTED,
                comment=comment,
            )
        ],
    )


def iter_pending_approvals(
    project_api_call: ApiCall,
    pipeline_run_ids: list[int] | None = None,
) -> Iterator[PipelineApproval]:
    """Iterate over pending pipeline approvals in the project.

    Args:
        project_api_call: Project-level ADO API call.
        pipeline_run_ids: Optional list of pipeline run IDs to restrict
            results to approvals belonging to those runs.

    Yields:
        PipelineApproval for each pending approval.
    """
    yield from iter_approvals(
        project_api_call,
        state=PipelineApprovalStatus.PENDING,
        pipeline_run_ids=pipeline_run_ids,
    )
