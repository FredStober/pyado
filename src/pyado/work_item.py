"""Module to interact with Azure DevOps work items."""
from datetime import datetime
from typing import Any
from typing import Iterator
from typing import Optional
from typing import TypeAlias
from uuid import UUID

from pydantic import BaseModel
from pydantic import Field

from pyado.api_call import ApiCall
from pyado.api_call import JsonPatchAdd
from pyado.api_call import get_test_api_call


WorkItemId: TypeAlias = int
WorkItemField: TypeAlias = str
SprintIterationId: TypeAlias = UUID
SprintIterationPath: TypeAlias = str


class WorkItemInfo(BaseModel):
    """Type to store work item details."""

    id: WorkItemId
    fields: dict[str, Any]


class _WorkItemInfoResults(BaseModel):
    """Type to read work item detail results."""

    value: list[WorkItemInfo]


def iter_work_item_details(
    project_api_call: ApiCall,
    work_item_id_list: list[WorkItemId],
    work_item_field_list: Optional[list[WorkItemField]] = None,
) -> Iterator[WorkItemInfo]:
    """Iterate over the work items."""
    request_json: dict[str, Any] = {"ids": work_item_id_list}
    if work_item_field_list:
        request_json["fields"] = work_item_field_list
    response = project_api_call.post(
        "wit",
        "workitemsbatch",
        version="7.1-preview.1",
        json=request_json,
    )
    results = _WorkItemInfoResults.model_validate(response)
    yield from results.value


def create_work_item(
    project_api_call: ApiCall, fields: dict[WorkItemField, Any]
) -> WorkItemInfo:
    """Create work items."""
    ticket_type: Optional[str] = fields.pop("System.WorkItemType", None)
    if ticket_type is None:
        raise RuntimeError(f"Work item type must be specified! {fields!r}")
    json_patch_list = [
        JsonPatchAdd(path=f"/fields/{key}", value=value).model_dump(mode="json")
        for key, value in fields.items()
    ]
    response = project_api_call.post(
        "wit",
        "workitems",
        f"${ticket_type}",
        version="7.1",
        json=json_patch_list,
    )
    return WorkItemInfo.model_validate(response)


class SprintIterationAttributes(BaseModel):
    """Type to store sprint attribute information."""

    start_date: datetime = Field(alias="startDate")
    finish_date: datetime = Field(alias="finishDate")
    timeframe: str = Field(alias="timeFrame")


class SprintIterationInfo(BaseModel):
    """Type to store sprint information."""

    id: SprintIterationId
    name: str
    path: SprintIterationPath
    attributes: SprintIterationAttributes


class _SprintIterationInfoResults(BaseModel):
    count: int
    value: list[SprintIterationInfo]


def iter_sprint_iterations(
    team_api_call_api_call: ApiCall, timeframe_filter: Optional[str] = None
) -> Iterator[SprintIterationInfo]:
    """Iterate over the sprint iterations."""
    parameters: dict[str, int | str] = {}
    if timeframe_filter:
        parameters["$timeframe"] = timeframe_filter
    response = team_api_call_api_call.get(
        "work",
        "teamsettings",
        "iterations",
        version="7.1",
        parameters=parameters,
    )
    results = _SprintIterationInfoResults.model_validate(response)
    yield from results.value


def test() -> None:
    """Function to test the functions."""
    test_api_call, test_config = get_test_api_call()
    for iteration in iter_sprint_iterations(test_api_call):
        print(iteration)
    for iteration in iter_sprint_iterations(test_api_call, timeframe_filter="current"):
        print(iteration)
    for work_item in iter_work_item_details(test_api_call, [test_config["ticket_id"]]):
        print(work_item)
    create_work_item(test_api_call, test_config["fields"])


if __name__ == "__main__":
    test()
