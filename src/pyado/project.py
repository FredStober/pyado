"""Module to interact with Azure DevOps projects."""
from datetime import datetime
from typing import Literal
from typing import TypeAlias
from uuid import UUID

from pydantic import BaseModel
from pydantic import Field


ProjectName: TypeAlias = str
ProjectId: TypeAlias = UUID


class ProjectInfo(BaseModel):
    """Type to store project details."""

    id: ProjectId
    name: ProjectName
    description: str
    state: Literal["wellFormed"]
    revision: int
    visibility: Literal["private"]
    last_update_time: datetime = Field(alias="lastUpdateTime")
