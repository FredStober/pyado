"""Module to interact with Azure DevOps work items."""
from typing import Literal
from typing import TypeAlias
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from pyado.api_call import ApiCall
from pyado.api_call import get_test_api_call
from pyado.build import BuildLogId
from pyado.build import BuildRecordInfo
from pyado.build import TaskId
from pyado.build import TimelineId
from pyado.build import get_build_api_call
from pyado.build import iter_timeline_records


PlanId: TypeAlias = UUID
JobId: TypeAlias = UUID
JobEventName: TypeAlias = Literal["TaskCompleted"]
JobEventResult: TypeAlias = Literal["succeeded", "failed"]


def get_plan_api_call(
    project_api_call: ApiCall, hub_name: str, plan_id: PlanId
) -> ApiCall:
    """Get job API call."""
    return project_api_call.build_call(
        "distributedtask",
        "hubs",
        hub_name,
        "plans",
        plan_id,
    )


def get_timeline_api_call(
    project_api_call: ApiCall, hub_name: str, plan_id: PlanId, timeline_id: TimelineId
) -> ApiCall:
    """Get timeline API call."""
    api_call = get_plan_api_call(project_api_call, hub_name, plan_id)
    return api_call.build_call("timelines", timeline_id)


def get_job_api_call(
    project_api_call: ApiCall,
    hub_name: str,
    plan_id: PlanId,
    timeline_id: TimelineId,
    job_id: JobId,
) -> ApiCall:
    """Get job API call."""
    api_call = get_timeline_api_call(project_api_call, hub_name, plan_id, timeline_id)
    return api_call.build_call("records", job_id)


def get_log_api_call(
    project_api_call: ApiCall, hub_name: str, plan_id: PlanId, log_id: BuildLogId
) -> ApiCall:
    """Get job log API call."""
    api_call = get_plan_api_call(project_api_call, hub_name, plan_id)
    return api_call.build_call("logs", log_id)


def send_job_feed(job_api_call: ApiCall, messages: list[str]) -> None:
    """Sends messages to feed of the running task.

    Reference: https://github.com/MicrosoftDocs/vsts-rest-api-specs/blob/master
    /specification/distributedTask/7.1/httpExamples/feed/
    POST__distributedtask_AppendTimelineRecordFeed_.json
    """
    feed_payload = {
        "value": messages,
        "count": len(messages),
    }
    job_api_call.post(
        "feed",
        version="7.1-preview.1",
        json=feed_payload,
    )


def send_job_logs(log_api_call: ApiCall, message: str) -> None:
    """Sends messages to the log of the running task.

    Reference: https://github.com/MicrosoftDocs/vsts-rest-api-specs/blob/master
    /specification/distributedTask/7.1/httpExamples/logs/
    POST__distributedtask_AppendLogContent_.json
    """
    log_api_call.post(
        version="7.1-preview.1",
        data=message.encode("utf-8"),
    )


class _JobEventPayload(BaseModel):
    """Type to store the job event payload."""

    model_config = ConfigDict(populate_by_name=True)

    name: JobEventName
    task_id: TaskId = Field(alias="taskId")
    job_id: JobId = Field(alias="jobId")
    result: JobEventResult


def send_job_event(
    plan_api_call: ApiCall,
    task_id: TaskId,
    job_id: JobId,
    job_event_name: JobEventName,
    job_event_result: JobEventResult,
) -> None:
    """This notifies the pipeline that the task has completed.

    Reference: https://github.com/MicrosoftDocs/vsts-rest-api-specs/blob/master
    /specification/distributedTask/7.1/httpExamples/events/
    POST_distributedtask_PostEvent.json
    """
    job_event_payload = _JobEventPayload(
        name=job_event_name,
        taskId=task_id,
        jobId=job_id,
        result=job_event_result,
    )
    plan_api_call.post(
        "events",
        version="7.1-preview.1",
        json=job_event_payload.model_dump(mode="json", by_alias=True),
    )


class _TimelineRecordsUpdatePayload(BaseModel):
    """Type to update timeline records."""

    count: int
    value: list[BuildRecordInfo]


def update_timeline_records(
    timeline_api_call: ApiCall, records: list[BuildRecordInfo]
) -> None:
    """Update the timeline records."""
    payload = _TimelineRecordsUpdatePayload(value=records, count=len(records))
    payload_dict = payload.model_dump(mode="json", by_alias=True, exclude_defaults=True)
    timeline_api_call.patch(
        "records",
        version="7.1",
        json=payload_dict,
    )


def test() -> None:
    """Function to test the functions."""
    test_api_call, test_config = get_test_api_call()
    build_api_call = get_build_api_call(test_api_call, test_config["build_id"])
    active_records = [
        record
        for record in iter_timeline_records(build_api_call)
        if str(record.id) == test_config["active_task_id"]
    ]
    timeline_api_call = get_timeline_api_call(
        test_api_call,
        test_config["hub_name"],
        test_config["plan_id"],
        test_config["timeline_id"],
    )
    update_timeline_records(timeline_api_call, active_records)

    job_api_call = get_job_api_call(
        test_api_call,
        test_config["hub_name"],
        test_config["plan_id"],
        test_config["timeline_id"],
        test_config["job_id"],
    )
    send_job_feed(job_api_call, ["Test Feed Message"])

    log_api_call = get_log_api_call(
        test_api_call,
        test_config["hub_name"],
        test_config["plan_id"],
        test_config["log_id"],
    )
    send_job_logs(log_api_call, "Test Log Message")

    plan_api_call = get_plan_api_call(
        test_api_call,
        test_config["hub_name"],
        test_config["plan_id"],
    )
    send_job_event(
        plan_api_call,
        test_config["active_task_id"],
        test_config["job_id"],
        "TaskCompleted",
        "succeeded",
    )


if __name__ == "__main__":
    test()
