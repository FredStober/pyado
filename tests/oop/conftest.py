"""Shared helpers and constants for pyado.oop tests."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Any
from uuid import UUID, uuid4

from pyado.oop import (
    Area,
    AzureDevOpsService,
    Build,
    BuildJob,
    BuildPhase,
    BuildStage,
    DistributedTaskSession,
    Iteration,
    Pipeline,
    Project,
    PullRequest,
    Repository,
    VariableGroup,
    WorkItem,
)
from pyado.raw import (
    ApiCall,
    BuildDetails,
    BuildId,
    BuildRecordInfo,
    ClassificationNode,
    GitCommitRef,
    GraphGroup,
    IdentityInfo,
    JobId,
    PipelineInfo,
    PipelineResourcePermissions,
    PipelineRunInfo,
    PlanId,
    ProjectInfo,
    PullRequestListItem,
    PullRequestResponse,
    RepositoryInfo,
    TaskId,
    TeamInfo,
    TimelineId,
    VariableGroupInfo,
    WorkItemInfo,
)
from tests.conftest import NOW_ISO

# ---------------------------------------------------------------------------
# Core constants
# ---------------------------------------------------------------------------

ORG_NAME = "testorg"
ORG_URL = f"https://dev.azure.com/{ORG_NAME}"
TOKEN = "test-token"
PROJECT_ID: UUID = uuid4()
REPO_ID: UUID = uuid4()

# ---------------------------------------------------------------------------
# Build timeline constants
# ---------------------------------------------------------------------------

STAGE_ID: UUID = uuid4()
PHASE_ID: UUID = uuid4()
JOB_ID: UUID = uuid4()
TASK_ID: UUID = uuid4()

# ---------------------------------------------------------------------------
# DistributedTaskSession constants
# ---------------------------------------------------------------------------

HUB_NAME = "build"
PLAN_ID: PlanId = uuid4()
TIMELINE_ID: TimelineId = uuid4()
ACTIVE_JOB_ID: JobId = uuid4()
ACTIVE_BUILD_ID: BuildId = 42
TASK_INSTANCE_ID: TaskId = uuid4()


# ---------------------------------------------------------------------------
# Core factory helpers
# ---------------------------------------------------------------------------


def _api_call(url: str = f"{ORG_URL}/_apis") -> ApiCall:
    return ApiCall(url=url)


def _make_service() -> AzureDevOpsService:
    return AzureDevOpsService(org=ORG_NAME, pat=TOKEN)


def _project_info(name: str = "TestProject") -> ProjectInfo:
    return ProjectInfo.model_validate(
        {
            "id": str(PROJECT_ID),
            "name": name,
            "state": "wellFormed",
            "revision": 1,
            "visibility": "private",
            "lastUpdateTime": NOW_ISO,
        }
    )


def _repo_info(name: str = "myrepo") -> RepositoryInfo:
    return RepositoryInfo.model_validate(
        {
            "id": str(REPO_ID),
            "name": name,
            "project": {
                "id": str(PROJECT_ID),
                "name": "TestProject",
                "state": "wellFormed",
                "revision": 1,
                "visibility": "private",
                "lastUpdateTime": NOW_ISO,
            },
            "defaultBranch": "refs/heads/main",
            "size": 0,
            "remoteUrl": "https://dev.azure.com/testorg/_git/myrepo",
            "sshUrl": "git@ssh.dev.azure.com:v3/testorg/TestProject/myrepo",
            "webUrl": "https://dev.azure.com/testorg/TestProject/_git/myrepo",
            "isDisabled": False,
            "isInMaintenance": False,
        }
    )


def _pr_list_item(pr_id: int = 42) -> PullRequestListItem:
    return PullRequestListItem.model_validate(
        {
            "pullRequestId": pr_id,
            "repository": {"id": str(REPO_ID)},
            "title": "Test PR",
            "status": "active",
        }
    )


def _pr_created(pr_id: int = 42) -> PullRequestResponse:
    return PullRequestResponse.model_validate(
        {
            "pullRequestId": pr_id,
            "repository": {"id": str(REPO_ID)},
            "status": "active",
            "url": f"https://dev.azure.com/testorg/TestProject/_git/myrepo/pullrequests/{pr_id}",
            "title": "Test PR",
            "sourceRefName": "refs/heads/feature/x",
            "targetRefName": "refs/heads/main",
        }
    )


def _work_item_info(wi_id: int = 10) -> WorkItemInfo:
    return WorkItemInfo.model_validate(
        {"id": wi_id, "fields": {"System.Title": "My WI"}}
    )


def _build_details(build_id: int = 100, pipeline_id: int = 1) -> BuildDetails:
    return BuildDetails.model_validate(
        {
            "id": build_id,
            "buildNumber": "20240101.1",
            "status": "completed",
            "result": "succeeded",
            "queueTime": NOW_ISO,
            "lastChangedDate": NOW_ISO,
            "sourceBranch": "refs/heads/main",
            "sourceVersion": "abc123",
            "definition": {"id": pipeline_id, "name": "MyPipeline"},
            "requestedBy": {"id": str(uuid4()), "displayName": "User"},
            "requestedFor": {"id": str(uuid4()), "displayName": "User"},
            "reason": "manual",
            "priority": "normal",
            "url": "https://dev.azure.com/testorg/TestProject/_build/results?buildId=100",
            "repository": {"id": "repo-id", "name": "myrepo", "type": "TfsGit"},
            "project": {
                "id": str(PROJECT_ID),
                "name": "TestProject",
                "state": "wellFormed",
                "revision": 1,
                "visibility": "private",
                "lastUpdateTime": NOW_ISO,
            },
        }
    )


def _pipeline_info(pipeline_id: int = 7) -> PipelineInfo:
    return PipelineInfo.model_validate(
        {
            "id": pipeline_id,
            "revision": 1,
            "name": "MyPipeline",
            "folder": "\\",
            "url": f"https://dev.azure.com/testorg/TestProject/_apis/pipelines/{pipeline_id}",
        }
    )


def _git_commit_ref(sha: str = "aaa000bbb111") -> GitCommitRef:
    return GitCommitRef.model_validate(
        {"commitId": sha, "comment": "Test commit", "commentTruncated": False}
    )


def _make_project(name: str = "TestProject") -> Project:
    return Project(_make_service(), name, _project_info(name))


def _make_repo(name: str = "myrepo") -> Repository:
    proj = _make_project()
    api_call = _api_call(f"{ORG_URL}/TestProject/_apis/git/repositories/{REPO_ID}")
    return Repository(proj, api_call, _repo_info(name), proj._service)


def _make_pr(pr_id: int = 42) -> PullRequest:
    repo = _make_repo()
    api_call = _api_call(
        f"{ORG_URL}/TestProject/_apis/git/repositories/{REPO_ID}/pullrequests/{pr_id}"
    )
    return PullRequest(repo, api_call, _pr_list_item(pr_id))


def _make_wi(wi_id: int = 10) -> WorkItem:
    proj = _make_project()
    api_call = _api_call(f"{ORG_URL}/TestProject/_apis/wit/workitems/{wi_id}")
    return WorkItem(proj, api_call, _work_item_info(wi_id))


def _make_build(build_id: int = 100, pipeline_id: int = 1) -> Build:
    proj = _make_project()
    api_call = _api_call(f"{ORG_URL}/TestProject/_apis/build/builds/{build_id}")
    return Build(proj, api_call, _build_details(build_id, pipeline_id), proj._service)


def _make_pipeline(pipeline_id: int = 7) -> Pipeline:
    proj = _make_project()
    return Pipeline(proj, pipeline_id, "MyPipeline", _pipeline_info(pipeline_id))


# ---------------------------------------------------------------------------
# Build timeline helpers
# ---------------------------------------------------------------------------


def _record(
    record_id: UUID,
    type_name: str,
    name: str,
    parent_id: UUID | None = None,
    state: str = "completed",
    result: str | None = "succeeded",
) -> BuildRecordInfo:
    return BuildRecordInfo.model_validate(
        {
            "attempt": 1,
            "changeId": None,
            "currentOperation": None,
            "details": None,
            "finishTime": NOW_ISO,
            "id": str(record_id),
            "identifier": None,
            "lastModified": NOW_ISO,
            "log": None,
            "name": name,
            "refName": None,
            "parentId": str(parent_id) if parent_id else None,
            "percentComplete": None,
            "previousAttempts": [],
            "result": result,
            "resultCode": None,
            "startTime": NOW_ISO,
            "state": state,
            "task": None,
            "type": type_name,
            "url": None,
            "workerName": "Hosted Agent" if type_name == "Job" else None,
        }
    )


def _make_all_records(use_phase: bool = False) -> list[BuildRecordInfo]:
    """Build a flat timeline record list with one stage, one job, one task.

    When use_phase is True, inserts a Phase between the stage and job.
    """
    stage = _record(STAGE_ID, "Stage", "Build Stage")
    task = _record(TASK_ID, "Task", "Run tests", parent_id=JOB_ID)
    if use_phase:
        phase = _record(PHASE_ID, "Phase", "__default", parent_id=STAGE_ID)
        job = _record(JOB_ID, "Job", "CI Job", parent_id=PHASE_ID)
        return [stage, phase, job, task]
    job = _record(JOB_ID, "Job", "CI Job", parent_id=STAGE_ID)
    return [stage, job, task]


def _make_tl_stage(
    all_records: list[BuildRecordInfo],
    record: BuildRecordInfo | None = None,
    build: Build | None = None,
) -> BuildStage:
    """Create a BuildStage with an optional build back-reference."""
    rec = record or next(r for r in all_records if r.type_name == "Stage")
    return BuildStage(rec, all_records, build=build or _make_build())


def _make_tl_phase(
    all_records: list[BuildRecordInfo],
    record: BuildRecordInfo | None = None,
    stage: BuildStage | None = None,
) -> BuildPhase:
    """Create a BuildPhase with an optional stage back-reference."""
    rec = record or next(r for r in all_records if r.type_name == "Phase")
    return BuildPhase(rec, all_records, stage=stage or _make_tl_stage(all_records))


def _make_tl_job(
    all_records: list[BuildRecordInfo],
    record: BuildRecordInfo | None = None,
    stage: BuildStage | None = None,
    phase: BuildPhase | None = None,
) -> BuildJob:
    """Create a BuildJob with stage/phase back-references."""
    rec = record or next(r for r in all_records if r.type_name == "Job")
    return BuildJob(
        rec, all_records, stage=stage or _make_tl_stage(all_records), phase=phase
    )


# ---------------------------------------------------------------------------
# DistributedTaskSession helpers
# ---------------------------------------------------------------------------


def _make_active_task(build: Build | None = None) -> DistributedTaskSession:
    return DistributedTaskSession(
        build or _make_build(),
        hub_name=HUB_NAME,
        plan_id=PLAN_ID,
        timeline_id=TIMELINE_ID,
        job_id=ACTIVE_JOB_ID,
        task_instance_id=TASK_INSTANCE_ID,
    )


def _task_record(log_id: int | None = None) -> BuildRecordInfo:
    """Build a Task-type timeline record with an optional log entry."""
    raw_log = (
        {
            "id": log_id,
            "type": "Container",
            "url": f"https://dev.azure.com/testorg/_apis/build/builds/{ACTIVE_BUILD_ID}/logs/1",
        }
        if log_id is not None
        else None
    )
    return BuildRecordInfo.model_validate(
        {
            "attempt": 1,
            "changeId": None,
            "currentOperation": None,
            "details": None,
            "finishTime": NOW_ISO,
            "id": str(TASK_INSTANCE_ID),
            "identifier": None,
            "lastModified": NOW_ISO,
            "log": raw_log,
            "name": "My Task",
            "refName": None,
            "parentId": str(ACTIVE_JOB_ID),
            "percentComplete": None,
            "previousAttempts": [],
            "result": "succeeded",
            "resultCode": None,
            "startTime": NOW_ISO,
            "state": "completed",
            "task": None,
            "type": "Task",
            "url": None,
            "workerName": None,
        }
    )


# ---------------------------------------------------------------------------
# Pipeline run helpers
# ---------------------------------------------------------------------------


def _pipeline_run_info(run_id: int = 100, pipeline_id: int = 1) -> PipelineRunInfo:
    return PipelineRunInfo.model_validate(
        {
            "id": run_id,
            "name": f"20240101.{run_id}",
            "state": "canceling",
            "pipeline": {
                "id": pipeline_id,
                "revision": 1,
                "name": "MyPipeline",
                "folder": "\\",
                "url": f"https://dev.azure.com/testorg/TestProject/_apis/pipelines/{pipeline_id}",
            },
            "createdDate": NOW_ISO,
            "url": f"https://dev.azure.com/testorg/TestProject/_apis/pipelines/{pipeline_id}/runs/{run_id}",
        }
    )


# ---------------------------------------------------------------------------
# Variable group helpers
# ---------------------------------------------------------------------------


def _variable_group_info(group_id: int = 1, name: str = "MyVars") -> VariableGroupInfo:
    user_id = str(uuid4())
    return VariableGroupInfo.model_validate(
        {
            "id": group_id,
            "name": name,
            "type": "Vsts",
            "variables": {"FOO": {"value": "bar"}},
            "createdBy": {
                "id": user_id,
                "displayName": "User",
                "uniqueName": "user@example.com",
            },
            "createdOn": NOW_ISO,
            "modifiedBy": {
                "id": user_id,
                "displayName": "User",
                "uniqueName": "user@example.com",
            },
            "modifiedOn": NOW_ISO,
            "isShared": False,
            "variableGroupProjectReferences": [],
        }
    )


def _make_variable_group(group_id: int = 1, name: str = "MyVars") -> VariableGroup:
    proj = _make_project()
    api_call = _api_call(
        f"{ORG_URL}/TestProject/_apis/distributedtask/variablegroups/{group_id}"
    )
    return VariableGroup(proj, api_call, _variable_group_info(group_id, name))


# ---------------------------------------------------------------------------
# Iteration and Area helpers
# ---------------------------------------------------------------------------


def _iteration_node(
    node_id: int = 1,
    name: str = "Sprint 1",
    path: str | None = "\\TestProject\\Sprint 1",
    start_date: str | None = "2024-01-01T00:00:00Z",
    finish_date: str | None = "2024-01-14T00:00:00Z",
    children: list[dict[str, Any]] | None = None,
) -> ClassificationNode:
    data: dict[str, Any] = {
        "id": node_id,
        "name": name,
        "structureType": "iteration",
        "hasChildren": children is not None and len(children) > 0,
        "path": path,
    }
    if start_date or finish_date:
        data["attributes"] = {}
        if start_date:
            data["attributes"]["startDate"] = start_date
        if finish_date:
            data["attributes"]["finishDate"] = finish_date
    if children is not None:
        data["children"] = children
    return ClassificationNode.model_validate(data)


def _area_node(
    node_id: int = 10,
    name: str = "Team A",
    path: str | None = "\\TestProject\\Team A",
    children: list[dict[str, Any]] | None = None,
) -> ClassificationNode:
    data: dict[str, Any] = {
        "id": node_id,
        "name": name,
        "structureType": "area",
        "hasChildren": children is not None and len(children) > 0,
        "path": path,
    }
    if children is not None:
        data["children"] = children
    return ClassificationNode.model_validate(data)


def _make_iteration(
    node_id: int = 1,
    name: str = "Sprint 1",
    path: str | None = "\\TestProject\\Sprint 1",
) -> Iteration:
    return Iteration(_make_project(), _iteration_node(node_id, name, path))


def _make_area(
    node_id: int = 10,
    name: str = "Team A",
    path: str = "\\TestProject\\Team A",
) -> Area:
    return Area(_make_project(), _area_node(node_id, name, path))


# ---------------------------------------------------------------------------
# Team helpers
# ---------------------------------------------------------------------------


def _team_info(team_id: str = "team-001", name: str = "My Team") -> TeamInfo:
    return TeamInfo(id=team_id, name=name, description="A team")


# ---------------------------------------------------------------------------
# Identity / group helpers
# ---------------------------------------------------------------------------


def _make_identity_info(uid: str = "id-1") -> IdentityInfo:
    return IdentityInfo.model_validate(
        {
            "id": uid,
            "providerDisplayName": "User One",
            "isActive": True,
            "isContainer": False,
        }
    )


def _make_graph_group(name: str = "Readers") -> GraphGroup:
    return GraphGroup.model_validate(
        {
            "displayName": name,
            "descriptor": "vssgp.abc",
            "principalName": f"[TestProject]\\{name}",
            "subjectKind": "group",
        }
    )


# ---------------------------------------------------------------------------
# Pipeline resource permission helpers
# ---------------------------------------------------------------------------


def _make_pipeline_resource_permissions(
    authorized: bool = True,
) -> PipelineResourcePermissions:
    return PipelineResourcePermissions.model_validate(
        {"allPipelines": {"authorized": authorized}}
    )
