"""Azure DevOps branch policy configuration and types API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from enum import StrEnum
from typing import Any, TypeAlias
from uuid import UUID

from pyado.raw._core import AdoBaseModel, ApiCall
from pyado.raw.repos.git import GitRefName, RepositoryId

__all__ = [
    "PolicyConfigurationId",
    "PolicyConfigurationInfo",
    "PolicyConfigurationRequest",
    "PolicyCreatedBy",
    "PolicyScope",
    "PolicyScopeMatchKind",
    "PolicyType",
    "PolicyTypeId",
    "PolicyTypeIdRef",
    "delete_policy_configuration",
    "get_policy_configuration",
    "get_policy_configuration_api_call",
    "get_policy_type",
    "iter_policy_configurations",
    "iter_policy_types",
    "list_policy_configurations",
    "list_policy_types",
    "post_policy_configuration",
    "put_policy_configuration",
]

_POLICY_API_VERSION = "7.1"
_ALL_BRANCHES_REF_PREFIX: GitRefName = "refs/heads/"

PolicyConfigurationId: TypeAlias = int
PolicyTypeId: TypeAlias = UUID


class PolicyScopeMatchKind(StrEnum):
    """How a policy scope's ``ref_name`` is matched against branch names.

    ``EXACT`` matches a single named branch.  ``PREFIX`` matches all branches
    whose ref begins with ``ref_name`` (typically ``"refs/heads/"`` to cover
    every branch in the repository).  ``DEFAULT_BRANCH`` matches the current
    default branch regardless of its name; ``ref_name`` is ignored in this
    case.
    """

    EXACT = "Exact"
    PREFIX = "Prefix"
    DEFAULT_BRANCH = "DefaultBranch"


class PolicyScope(AdoBaseModel):
    """Repository or branch scope entry for a policy configuration.

    A policy's ``settings["scope"]`` is a list of these objects.  Each entry
    restricts the policy to a specific repository and, optionally, a subset of
    branches.  Use the factory class methods to build the most common variants.

    Serialize with ``model_dump(by_alias=True, exclude_none=True)`` unless you
    need to express an explicit ``null`` ``repository_id`` (meaning "all
    repositories in the project"), in which case omit ``exclude_none``.
    """

    repository_id: RepositoryId | None = None
    ref_name: GitRefName | None = None
    match_kind: PolicyScopeMatchKind | None = None

    @classmethod
    def for_branch(
        cls,
        repository_id: RepositoryId,
        ref_name: GitRefName,
        match_kind: PolicyScopeMatchKind = PolicyScopeMatchKind.EXACT,
    ) -> "PolicyScope":
        """Create a scope that targets a specific branch (or prefix) in a repository.

        Args:
            repository_id: RepositoryId of the target repository.
            ref_name: Full ref name, e.g. ``"refs/heads/main"``.
            match_kind: How ``ref_name`` is matched; defaults to
                ``PolicyScopeMatchKind.EXACT``.

        Returns:
            PolicyScope targeting the specified branch.
        """
        return cls(
            repository_id=repository_id,
            ref_name=ref_name,
            match_kind=match_kind,
        )

    @classmethod
    def for_default_branch(cls, repository_id: RepositoryId) -> "PolicyScope":
        """Create a scope that targets the default branch of a repository.

        Args:
            repository_id: RepositoryId of the target repository.

        Returns:
            PolicyScope targeting the default branch (``matchKind=DefaultBranch``).
        """
        return cls(
            repository_id=repository_id,
            match_kind=PolicyScopeMatchKind.DEFAULT_BRANCH,
        )

    @classmethod
    def for_all_branches(cls, repository_id: RepositoryId) -> "PolicyScope":
        """Create a scope that targets every branch in a repository.

        Uses a prefix match on ``"refs/heads/"`` so that all branches, including
        those created after the policy is applied, are covered.

        Args:
            repository_id: RepositoryId of the target repository.

        Returns:
            PolicyScope targeting all branches.
        """
        return cls(
            repository_id=repository_id,
            ref_name=_ALL_BRANCHES_REF_PREFIX,
            match_kind=PolicyScopeMatchKind.PREFIX,
        )


class PolicyTypeIdRef(AdoBaseModel):
    """Minimal policy type reference used in write requests."""

    id: PolicyTypeId


class PolicyType(AdoBaseModel):
    """Policy type, returned by the types API and embedded in configurations."""

    id: PolicyTypeId
    display_name: str
    url: str | None = None
    description: str | None = None


class PolicyCreatedBy(AdoBaseModel):
    """Identity reference embedded in a policy configuration."""

    id: UUID
    display_name: str


class PolicyConfigurationInfo(AdoBaseModel):
    """A single ADO branch policy configuration.

    The ``settings`` field is a catch-all dict because the schema varies
    by policy type and is too wide to enumerate strictly.
    """

    id: PolicyConfigurationId
    type: PolicyType
    is_enabled: bool
    is_blocking: bool
    settings: dict[str, Any]
    is_deleted: bool = False
    is_enterprise_managed: bool = False
    revision: int | None = None
    url: str | None = None
    created_by: PolicyCreatedBy | None = None
    created_date: str | None = None


class PolicyConfigurationRequest(AdoBaseModel):
    """Request body for creating or updating a policy configuration."""

    is_enabled: bool
    is_blocking: bool
    type: PolicyTypeIdRef
    settings: dict[str, Any]


def get_policy_configuration_api_call(
    project_api_call: ApiCall,
    config_id: PolicyConfigurationId,
) -> ApiCall:
    """Build a policy-configuration-scoped API call.

    Args:
        project_api_call: Project-level ADO API call.
        config_id: Numeric ID of the policy configuration.

    Returns:
        An ApiCall pointing at the policy configuration resource.
    """
    return project_api_call.build_call("policy", "configurations", config_id)


def iter_policy_configurations(
    project_api_call: ApiCall,
) -> Iterator[PolicyConfigurationInfo]:
    """Iterate over all policy configurations in a project.

    Args:
        project_api_call: Project-level ADO API call.

    Yields:
        PolicyConfigurationInfo for each configured policy.
    """
    result = project_api_call.get(
        "policy",
        "configurations",
        version=_POLICY_API_VERSION,
    )
    for item in result.get("value", []):
        yield PolicyConfigurationInfo.model_validate(item)


def list_policy_configurations(
    project_api_call: ApiCall,
) -> list[PolicyConfigurationInfo]:
    """Return all policy configurations in a project as a list."""
    return list(iter_policy_configurations(project_api_call))


def get_policy_configuration(
    policy_configuration_api_call: ApiCall,
) -> PolicyConfigurationInfo:
    """Return a single policy configuration by ID.

    Args:
        policy_configuration_api_call: Configuration-level ADO API call
            (from ``get_policy_configuration_api_call``).

    Returns:
        The matching PolicyConfigurationInfo.
    """
    result = policy_configuration_api_call.get(version=_POLICY_API_VERSION)
    return PolicyConfigurationInfo.model_validate(result)


def post_policy_configuration(
    project_api_call: ApiCall,
    request: PolicyConfigurationRequest,
) -> PolicyConfigurationInfo:
    """Create a new policy configuration in a project.

    Args:
        project_api_call: Project-level ADO API call.
        request: Request specifying the type, settings, and blocking flag.

    Returns:
        The newly created PolicyConfigurationInfo.
    """
    result = project_api_call.post(
        "policy",
        "configurations",
        version=_POLICY_API_VERSION,
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return PolicyConfigurationInfo.model_validate(result)


def put_policy_configuration(
    policy_configuration_api_call: ApiCall,
    request: PolicyConfigurationRequest,
) -> PolicyConfigurationInfo:
    """Update an existing policy configuration.

    Args:
        policy_configuration_api_call: Configuration-level ADO API call
            (from ``get_policy_configuration_api_call``).
        request: Updated settings for the policy configuration.

    Returns:
        The updated PolicyConfigurationInfo.
    """
    result = policy_configuration_api_call.put(
        version=_POLICY_API_VERSION,
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return PolicyConfigurationInfo.model_validate(result)


def delete_policy_configuration(
    policy_configuration_api_call: ApiCall,
) -> None:
    """Delete a policy configuration.

    Args:
        policy_configuration_api_call: Configuration-level ADO API call
            (from ``get_policy_configuration_api_call``).
    """
    policy_configuration_api_call.delete(version=_POLICY_API_VERSION)


def iter_policy_types(
    project_api_call: ApiCall,
) -> Iterator[PolicyType]:
    """Iterate over all available policy types in a project.

    Args:
        project_api_call: Project-level ADO API call.

    Yields:
        PolicyType for each available policy type.
    """
    result = project_api_call.get(
        "policy",
        "types",
        version=_POLICY_API_VERSION,
    )
    items = result if isinstance(result, list) else result.get("value", [])
    for item in items:
        yield PolicyType.model_validate(item)


def list_policy_types(
    project_api_call: ApiCall,
) -> list[PolicyType]:
    """Return all available policy types in a project as a list."""
    return list(iter_policy_types(project_api_call))


def get_policy_type(
    project_api_call: ApiCall,
    type_id: PolicyTypeId,
) -> PolicyType:
    """Return a single policy type by ID.

    Args:
        project_api_call: Project-level ADO API call.
        type_id: UUID of the policy type.

    Returns:
        The matching PolicyType.
    """
    result = project_api_call.get(
        "policy",
        "types",
        type_id,
        version=_POLICY_API_VERSION,
    )
    return PolicyType.model_validate(result)
