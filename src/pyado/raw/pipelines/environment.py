"""Azure DevOps distributed task environment API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import datetime
from typing import TypeAlias

from pydantic import Field

from pyado.raw._core import AdoBaseModel, ApiCall

__all__ = [
    "ApprovalCheckSettings",
    "DeploymentRecordId",
    "EnvironmentCheckId",
    "EnvironmentCheckInfo",
    "EnvironmentDeploymentRecord",
    "EnvironmentId",
    "EnvironmentInfo",
    "get_environment",
    "get_environment_api_call",
    "iter_environment_checks",
    "iter_environment_deployments",
    "iter_environments",
    "list_environment_checks",
    "list_environment_deployments",
    "list_environments",
]

EnvironmentId: TypeAlias = int
#: Numeric identifier for an environment deployment record.
DeploymentRecordId: TypeAlias = int
#: Numeric identifier for an environment check configuration.
EnvironmentCheckId: TypeAlias = int

_ENVIRONMENT_API_VERSION = "7.1"
_ENVIRONMENT_DEPLOYMENT_API_VERSION = "7.1"


class _EnvironmentIdentityRef(AdoBaseModel):
    """Identity reference embedded in environment responses."""

    id: str
    display_name: str
    unique_name: str | None = None


class _EnvironmentProjectRef(AdoBaseModel):
    """Project reference embedded in environment responses."""

    id: str
    name: str | None = None


class EnvironmentInfo(AdoBaseModel):
    """Minimal representation of an ADO pipeline environment."""

    id: EnvironmentId
    name: str
    description: str = ""
    created_by: _EnvironmentIdentityRef | None = None
    created_on: datetime | None = None
    last_modified_by: _EnvironmentIdentityRef | None = None
    last_modified_on: datetime | None = None
    project: _EnvironmentProjectRef | None = None


class EnvironmentDeploymentRecord(AdoBaseModel):
    """A single deployment record for a pipeline environment."""

    id: DeploymentRecordId
    definition_name: str = ""
    start_time: datetime | None = None
    finish_time: datetime | None = None
    result: str | None = None
    owner: str | None = None


def get_environment_api_call(
    project_api_call: ApiCall,
    environment_id: EnvironmentId,
) -> ApiCall:
    """Build an environment-scoped API call.

    Args:
        project_api_call: Project-level ADO API call.
        environment_id: Numeric environment ID.

    Returns:
        An ApiCall pointing at the environment resource.
    """
    return project_api_call.build_call(
        "distributedtask",
        "environments",
        environment_id,
        version=_ENVIRONMENT_API_VERSION,
    )


def iter_environments(
    project_api_call: ApiCall,
) -> Iterator[EnvironmentInfo]:
    """Iterate over all pipeline environments in a project.

    Args:
        project_api_call: Project-level ADO API call.

    Yields:
        EnvironmentInfo for each environment in the project.
    """
    result = project_api_call.get(
        "distributedtask",
        "environments",
        version=_ENVIRONMENT_API_VERSION,
    )
    for item in result.get("value", []):
        yield EnvironmentInfo.model_validate(item)


def get_environment(
    project_api_call: ApiCall,
    environment_id: EnvironmentId,
) -> EnvironmentInfo:
    """Return a single pipeline environment by ID.

    Args:
        project_api_call: Project-level ADO API call.
        environment_id: Numeric environment ID.

    Returns:
        EnvironmentInfo for the requested environment.
    """
    result = project_api_call.get(
        "distributedtask",
        "environments",
        environment_id,
        version=_ENVIRONMENT_API_VERSION,
    )
    return EnvironmentInfo.model_validate(result)


def iter_environment_deployments(
    env_api_call: ApiCall,
    *,
    top: int | None = None,
) -> Iterator[EnvironmentDeploymentRecord]:
    """Iterate over deployment records for a pipeline environment.

    Args:
        env_api_call: Environment-level ADO API call (from
            get_environment_api_call).
        top: Maximum number of records to return.  When ``None``, the API
            default is used.

    Yields:
        EnvironmentDeploymentRecord for each deployment.
    """
    parameters: dict[str, int | str | bool] = {}
    if top is not None:
        parameters["top"] = top
    result = env_api_call.get(
        "environmentdeploymentrecords",
        parameters=parameters,
        version=_ENVIRONMENT_DEPLOYMENT_API_VERSION,
    )
    for item in result.get("value", []):
        yield EnvironmentDeploymentRecord.model_validate(item)


def list_environments(
    project_api_call: ApiCall,
) -> list[EnvironmentInfo]:
    """Return all pipeline environments in a project as a list."""
    return list(iter_environments(project_api_call))


def list_environment_deployments(
    env_api_call: ApiCall,
    *,
    top: int | None = None,
) -> list[EnvironmentDeploymentRecord]:
    """Return all deployment records for a pipeline environment as a list."""
    return list(iter_environment_deployments(env_api_call, top=top))


_CHECKS_API_VERSION = "7.1-preview.1"


class _CheckTypeRef(AdoBaseModel):
    """Check type reference embedded in EnvironmentCheckInfo."""

    id: str
    name: str


class ApprovalCheckSettings(AdoBaseModel):
    """Settings for an Approval check on a pipeline environment."""

    approvers: list[_EnvironmentIdentityRef] = Field(default_factory=list)
    instructions: str = ""
    requester_cannot_be_approver: bool = False
    required_approver_count: int = 1
    allow_approvers_to_approve_their_own_runs: bool = False


class EnvironmentCheckInfo(AdoBaseModel):
    """A single check configuration on a pipeline environment."""

    id: EnvironmentCheckId
    type: _CheckTypeRef
    settings: ApprovalCheckSettings | None = None
    timeout: int | None = None
    created_by: _EnvironmentIdentityRef | None = None
    created_on: datetime | None = None


def iter_environment_checks(
    project_api_call: ApiCall,
    environment_id: EnvironmentId,
) -> Iterator[EnvironmentCheckInfo]:
    """Iterate over all check configurations for a pipeline environment.

    Args:
        project_api_call: Project-level ADO API call.
        environment_id: Numeric environment ID.

    Yields:
        EnvironmentCheckInfo for each check configuration.
    """
    result = project_api_call.get(
        "pipelines",
        "checks",
        "configurations",
        parameters={
            "resourceType": "environment",
            "resourceId": environment_id,
        },
        version=_CHECKS_API_VERSION,
    )
    for item in result.get("value", []):
        yield EnvironmentCheckInfo.model_validate(item)


def list_environment_checks(
    project_api_call: ApiCall,
    environment_id: EnvironmentId,
) -> list[EnvironmentCheckInfo]:
    """Return all check configurations for a pipeline environment as a list."""
    return list(iter_environment_checks(project_api_call, environment_id))
