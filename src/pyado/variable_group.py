"""Module to interact with Azure DevOps repositories."""
from datetime import datetime
from typing import Any
from typing import Iterator
from typing import Literal
from typing import Optional
from typing import TypeAlias
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from pyado.api_call import ApiCall
from pyado.api_call import get_test_api_call


UserId: TypeAlias = UUID
VariableGroupId: TypeAlias = int


class VariableGroupUserInfo(BaseModel, extra="forbid"):
    """Type to store variable group user information."""

    model_config = ConfigDict(populate_by_name=True)

    display_name: Optional[str] = Field(default=None, alias="displayName")
    id: UserId
    unique_name: Optional[str] = Field(default=None, alias="uniqueName")


class VariableInfo(BaseModel, extra="forbid"):
    """Type to store information about variables."""

    model_config = ConfigDict(populate_by_name=True)

    is_secret: bool = Field(default=False, alias="isSecret")
    value: Optional[str] = None


class VariableGroupInfo(BaseModel, extra="forbid"):
    """Type to store variable group details."""

    model_config = ConfigDict(populate_by_name=True)

    created_by: VariableGroupUserInfo = Field(alias="createdBy")
    created_on: datetime = Field(alias="createdOn")
    description: Optional[str] = None
    id: VariableGroupId
    is_shared: bool = Field(alias="isShared")
    modified_by: VariableGroupUserInfo = Field(alias="modifiedBy")
    modified_on: datetime = Field(alias="modifiedOn")
    name: str
    type: Literal["Vsts"]
    variable_group_refs: Any = Field(alias="variableGroupProjectReferences")
    variables: dict[str, VariableInfo]


class _VariableGroupInfoResults(BaseModel):
    """Type to read repository details results."""

    value: list[VariableGroupInfo]


def iter_variable_group_details(
    project_api_call: ApiCall,
) -> Iterator[VariableGroupInfo]:
    """Iterate over the variable groups of the project."""
    response = project_api_call.get(
        "distributedtask",
        "variablegroups",
        version="5.1-preview.1",
    )
    results = _VariableGroupInfoResults.model_validate(response)
    yield from results.value


class _VariableGroupUpdateInfo(BaseModel):
    """Type to store updates for variable group values."""

    name: str
    variables: dict[str, VariableInfo]


def update_variable_group_entries(
    project_api_call: ApiCall,
    var_group_id: VariableGroupId,
    var_group_name: str,
    variables: dict[str, VariableInfo],
) -> VariableGroupInfo:
    """Update variables in the variable group."""
    update_info = _VariableGroupUpdateInfo(name=var_group_name, variables=variables)
    response = project_api_call.put(
        "distributedtask",
        "variablegroups",
        var_group_id,
        version="5.1-preview.1",
        json=update_info.model_dump(mode="json", by_alias=True),
    )
    return VariableGroupInfo.model_validate(response)


def test() -> None:
    """Function to test the functions."""
    test_api_call, test_config = get_test_api_call()
    del test_config
    for var_group in iter_variable_group_details(test_api_call):
        print(var_group)


if __name__ == "__main__":
    test()
