"""Module to interact with Azure DevOps builds."""
from datetime import datetime
from typing import Any
from typing import Iterator
from typing import Literal
from typing import Optional
from typing import TypeAlias
from uuid import UUID

from pydantic import BaseModel
from pydantic import Field
from pydantic.networks import AnyUrl

from pyado.api_call import ADOUrl
from pyado.api_call import ApiCall
from pyado.api_call import get_test_api_call
from pyado.work_item import WorkItemId


BuildId: TypeAlias = int
TimelineId: TypeAlias = UUID
TaskId: TypeAlias = UUID
QueueId: TypeAlias = int
BuildLogId: TypeAlias = int
BuildRecordType: TypeAlias = Literal[
    "Checkpoint",
    "Checkpoint.Approval",
    "Checkpoint.ExtendsCheck",
    "Phase",
    "Stage",
    "Job",
    "Task",
]


def get_build_api_call(project_api_call: ApiCall, build_id: BuildId) -> ApiCall:
    """Get pull request API call."""
    return project_api_call.build_call(
        "build",
        "builds",
        build_id,
    )


def iter_build_work_item_ids(build_api_call: ApiCall) -> Iterator[WorkItemId]:
    """Get work items linked to the build pipeline."""
    max_results = 100
    response = build_api_call.get(
        "workitems",
        parameters={"$top": max_results},
        version="7.0",
    )
    for entry in response["value"]:
        yield int(entry["id"])


class BuildLogInfo(BaseModel, extra="forbid"):
    """Type to store build log details."""

    id: BuildLogId
    log_type: Literal["Container"] = Field(alias="type")
    url: ADOUrl


class BuildRecordTypeInfo(BaseModel, extra="forbid"):
    """Type to store build task type details."""

    id: TaskId
    name: str
    version: str


class BuildAttemptInfo(BaseModel, extra="forbid"):
    """Type to store build attempt details."""

    attempt: int
    timeline_id: UUID = Field(alias="timelineId")
    record_id: UUID = Field(alias="recordId")


class BuildIssue(BaseModel, extra="forbid"):
    """Type for build message issues."""

    category: str
    data: Optional[dict[str, str]] = {}
    message: str
    type: Literal["error", "warning"]


class BuildRecordInfo(BaseModel, extra="forbid"):
    """Type to store build task details."""

    attempt: int
    change_id: Optional[int] = Field(alias="changeId")
    current_operation: Any = Field(alias="currentOperation")
    details: Any
    error_count: Optional[int] = Field(default=None, alias="errorCount")
    finish_time: Optional[datetime] = Field(alias="finishTime")
    id: TaskId
    identifier: Optional[str]
    issues: Optional[list[BuildIssue]] = None
    last_modified: datetime = Field(alias="lastModified")
    log: Optional[BuildLogInfo]
    name: str
    order: Optional[int] = None
    parent_id: Optional[TaskId] = Field(alias="parentId")
    percent_complete: Optional[int] = Field(alias="percentComplete")
    previous_attempts: list[BuildAttemptInfo] = Field(alias="previousAttempts")
    queue_id: Optional[QueueId] = Field(default=None, alias="queueId")
    result: Optional[Literal["failed", "succeeded", "skipped", "canceled"]]
    result_code: Optional[str] = Field(alias="resultCode")
    start_time: Optional[datetime] = Field(alias="startTime")
    state: Literal["completed", "pending", "inProgress"]
    task: Optional[BuildRecordTypeInfo]
    type_name: BuildRecordType = Field(alias="type")
    url: Optional[AnyUrl]
    warning_count: Optional[int] = Field(default=None, alias="warningCount")
    worker_name: Optional[str] = Field(alias="workerName")


class _BuildRecordInfoResults(BaseModel):
    """Type to read build record details results."""

    records: list[BuildRecordInfo]
    id: TimelineId


def iter_timeline_records(build_api_call: ApiCall) -> Iterator[BuildRecordInfo]:
    """Iterate over task in the timeline.

    Reference: https://github.com/MicrosoftDocs/vsts-rest-api-specs/blob/master
    /specification/build/7.1/build.json#L2478
    """
    response = build_api_call.get(
        "timeline",
        version="7.1",
    )
    results = _BuildRecordInfoResults.model_validate(response)
    yield from results.records


def test() -> None:
    """Function to test the functions."""
    test_api_call, test_config = get_test_api_call()
    build_api_call = get_build_api_call(test_api_call, test_config["build_id"])
    for build_work_item in iter_build_work_item_ids(build_api_call):
        print(build_work_item)
    for task in iter_timeline_records(build_api_call):
        print(task)


if __name__ == "__main__":
    test()
