"""Typed OOP policy models for Azure DevOps branch policy configurations.

Each class wraps a specific policy type with strongly-typed fields and
provides round-trip conversion to and from the raw
:class:`~pyado.raw.PolicyConfigurationRequest` /
:class:`~pyado.raw.PolicyConfigurationInfo` models.

Policy scope types
------------------
Two scope variants reflect the two ways ADO applies policies:

* :class:`RepoPolicyScope` — repository-level policies (``repositoryId``
  only; no branch filtering).  Used by :class:`GitRepositoryPolicy`,
  :class:`ReservedNamesPolicy`, :class:`PathLengthPolicy`,
  :class:`FileSizeRestrictionPolicy`, :class:`FileNamePolicy`,
  :class:`SearchBranchesPolicy`, and :class:`CommitAuthorEmailPolicy`.

* :class:`~pyado.raw.PolicyScope` — branch-level policies
  (``repositoryId`` + ``refName`` + ``matchKind``).  Used by the
  remaining seven policy classes.

Typical usage::

    import pyado

    # Branch-level policy
    branch_scope = pyado.PolicyScope.for_default_branch(repo_id)
    policy = pyado.MinimumReviewersPolicy(
        scope=[branch_scope],
        minimum_approver_count=2,
        creator_vote_counts=False,
        allow_downvotes=False,
        reset_on_source_push=True,
        require_vote_on_last_iteration=False,
        reset_rejections_on_source_push=False,
        block_last_pusher_vote=False,
    )
    project.settings.create_policy_configuration(policy.to_request())

    # Repository-level policy
    repo_scope = pyado.RepoPolicyScope(repository_id=repo_id)
    size_policy = pyado.FileSizeRestrictionPolicy(
        scope=[repo_scope],
        maximum_git_blob_size_in_bytes=10_485_760,
        use_uncompressed_size=False,
    )
    project.settings.create_policy_configuration(size_policy.to_request())
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Any, ClassVar, Self
from uuid import UUID

from pyado import raw
from pyado.raw._core import AdoBaseModel

__all__ = [
    "BasePolicyModel",
    "BuildPolicy",
    "CommentRequirementsPolicy",
    "CommitAuthorEmailPolicy",
    "FileNamePolicy",
    "FileSizeRestrictionPolicy",
    "GitRepositoryPolicy",
    "MergeStrategyPolicy",
    "MinimumReviewersPolicy",
    "PathLengthPolicy",
    "RepoPolicyScope",
    "RequiredReviewersPolicy",
    "ReservedNamesPolicy",
    "SearchBranchesPolicy",
    "StatusPolicy",
    "WorkItemLinkingPolicy",
]


class RepoPolicyScope(AdoBaseModel):
    """Repository scope for policies that apply at repository (not branch) level.

    Repository-level policies (e.g. file-size restriction, reserved-names)
    target a whole repository, not a specific branch.  Pass ``None`` as
    ``repository_id`` to apply the policy to every repository in the project.
    """

    repository_id: raw.RepositoryId | None = None


class BasePolicyModel(AdoBaseModel):
    """Base class for typed OOP policy models.

    Subclasses declare a ``POLICY_TYPE_ID`` class variable and the
    policy-specific fields.  The three conversion methods are implemented
    here and require no overriding in concrete subclasses.
    """

    POLICY_TYPE_ID: ClassVar[UUID] = UUID("00000000-0000-0000-0000-000000000000")
    is_enabled: bool = True
    is_blocking: bool = True

    def to_request(self) -> raw.PolicyConfigurationRequest:
        """Serialise this model to a raw PolicyConfigurationRequest.

        The ``is_enabled`` and ``is_blocking`` fields are lifted to the
        top level of the request; all remaining fields are serialised as
        the ``settings`` dict in camelCase.

        Returns:
            A :class:`~pyado.raw.PolicyConfigurationRequest` ready to
            pass to :func:`~pyado.raw.post_policy_configuration` or
            :func:`~pyado.raw.put_policy_configuration`.
        """
        settings = self.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
            exclude={"is_enabled", "is_blocking"},
        )
        return raw.PolicyConfigurationRequest(
            is_enabled=self.is_enabled,
            is_blocking=self.is_blocking,
            type=raw.PolicyTypeIdRef(id=self.POLICY_TYPE_ID),
            settings=settings,
        )

    @classmethod
    def from_info(cls, info: raw.PolicyConfigurationInfo) -> Self:
        """Construct this policy model from a raw PolicyConfigurationInfo.

        Args:
            info: A :class:`~pyado.raw.PolicyConfigurationInfo` returned
                by the ADO policy endpoint.

        Returns:
            A fully populated instance of this policy model.
        """
        return cls.model_validate(
            {
                "isEnabled": info.is_enabled,
                "isBlocking": info.is_blocking,
                **info.settings,
            }
        )

    @classmethod
    def from_request(cls, request: raw.PolicyConfigurationRequest) -> Self:
        """Construct this policy model from a raw PolicyConfigurationRequest.

        Args:
            request: A :class:`~pyado.raw.PolicyConfigurationRequest`
                previously built by :meth:`to_request` or constructed
                manually.

        Returns:
            A fully populated instance of this policy model.
        """
        return cls.model_validate(
            {
                "isEnabled": request.is_enabled,
                "isBlocking": request.is_blocking,
                **request.settings,
            }
        )


class MinimumReviewersPolicy(BasePolicyModel):
    """Typed policy model for 'Minimum number of reviewers'."""

    POLICY_TYPE_ID: ClassVar[UUID] = raw.MinimumReviewersSettings.POLICY_TYPE_ID

    scope: list[raw.PolicyScope]
    minimum_approver_count: int
    creator_vote_counts: bool
    allow_downvotes: bool
    reset_on_source_push: bool
    require_vote_on_last_iteration: bool
    reset_rejections_on_source_push: bool
    block_last_pusher_vote: bool
    require_vote_on_each_iteration: bool | None = None


class CommentRequirementsPolicy(BasePolicyModel):
    """Typed policy model for 'Comment requirements'."""

    POLICY_TYPE_ID: ClassVar[UUID] = raw.CommentRequirementsSettings.POLICY_TYPE_ID

    scope: list[raw.PolicyScope]


class WorkItemLinkingPolicy(BasePolicyModel):
    """Typed policy model for 'Work item linking'."""

    POLICY_TYPE_ID: ClassVar[UUID] = raw.WorkItemLinkingSettings.POLICY_TYPE_ID

    scope: list[raw.PolicyScope]


class GitRepositoryPolicy(BasePolicyModel):
    """Typed policy model for 'Git repository settings'."""

    POLICY_TYPE_ID: ClassVar[UUID] = raw.GitRepositorySettings.POLICY_TYPE_ID

    scope: list[RepoPolicyScope]
    enforce_consistent_case: bool | None = None
    reject_dot_git: bool | None = None
    optimized_by_default: bool | None = None
    breadcrumb_days: int | None = None
    allowed_fork_targets: int | None = None
    gvfs_only: bool | None = None
    gvfs_exempt_users: Any | None = None
    gvfs_allowed_version_ranges: Any | None = None
    detect_rename_false_positives_by_default: bool | None = None
    strict_vote_mode: bool | None = None
    inherit_pull_request_creation_mode: bool | None = None
    repo_pull_request_as_draft_by_default: bool | None = None
    repo_pull_request_auto_complete_by_default: bool | None = None


class ReservedNamesPolicy(BasePolicyModel):
    """Typed policy model for 'Reserved names restriction'."""

    POLICY_TYPE_ID: ClassVar[UUID] = raw.ReservedNamesSettings.POLICY_TYPE_ID

    scope: list[RepoPolicyScope]


class PathLengthPolicy(BasePolicyModel):
    """Typed policy model for 'Path Length restriction'."""

    POLICY_TYPE_ID: ClassVar[UUID] = raw.PathLengthSettings.POLICY_TYPE_ID

    scope: list[RepoPolicyScope]
    max_path_length: int


class FileSizeRestrictionPolicy(BasePolicyModel):
    """Typed policy model for 'File size restriction'."""

    POLICY_TYPE_ID: ClassVar[UUID] = raw.FileSizeRestrictionSettings.POLICY_TYPE_ID

    scope: list[RepoPolicyScope]
    maximum_git_blob_size_in_bytes: int
    use_uncompressed_size: bool


class FileNamePolicy(BasePolicyModel):
    """Typed policy model for 'File name restriction'."""

    POLICY_TYPE_ID: ClassVar[UUID] = raw.FileNameSettings.POLICY_TYPE_ID

    scope: list[RepoPolicyScope]
    filename_patterns: list[str] | None = None


class MergeStrategyPolicy(BasePolicyModel):
    """Typed policy model for 'Require a merge strategy'."""

    POLICY_TYPE_ID: ClassVar[UUID] = raw.MergeStrategySettings.POLICY_TYPE_ID

    scope: list[raw.PolicyScope]
    allow_no_fast_forward: bool | None = None
    allow_squash: bool | None = None
    allow_rebase: bool | None = None
    allow_rebase_merge: bool | None = None


class CommitAuthorEmailPolicy(BasePolicyModel):
    """Typed policy model for 'Commit author email validation'."""

    POLICY_TYPE_ID: ClassVar[UUID] = raw.CommitAuthorEmailSettings.POLICY_TYPE_ID

    scope: list[RepoPolicyScope]
    author_email_patterns: list[str] | None = None


class BuildPolicy(BasePolicyModel):
    """Typed policy model for 'Build' policy."""

    POLICY_TYPE_ID: ClassVar[UUID] = raw.BuildPolicySettings.POLICY_TYPE_ID

    scope: list[raw.PolicyScope]
    build_definition_id: raw.PipelineId
    queue_on_source_update_only: bool
    manual_queue_only: bool
    valid_duration: float
    display_name: str | None = None
    filename_patterns: list[str] | None = None


class SearchBranchesPolicy(BasePolicyModel):
    """Typed policy model for 'Search branches' policy."""

    POLICY_TYPE_ID: ClassVar[UUID] = raw.SearchBranchesPolicySettings.POLICY_TYPE_ID

    scope: list[RepoPolicyScope]
    search_branches: list[raw.GitRefName]


class RequiredReviewersPolicy(BasePolicyModel):
    """Typed policy model for 'Required reviewers'."""

    POLICY_TYPE_ID: ClassVar[UUID] = raw.RequiredReviewersSettings.POLICY_TYPE_ID

    scope: list[raw.PolicyScope]
    required_reviewer_ids: list[raw.ReviewerId]
    minimum_approver_count: int
    creator_vote_counts: bool
    message: str | None = None
    filename_patterns: list[str] | None = None


class StatusPolicy(BasePolicyModel):
    """Typed policy model for 'Status' policy."""

    POLICY_TYPE_ID: ClassVar[UUID] = raw.StatusPolicySettings.POLICY_TYPE_ID

    scope: list[raw.PolicyScope]
    status_name: str
    status_genre: raw.StatusGenre
    author_id: UUID
    invalidate_on_source_update: bool
    default_display_name: str
    policy_applicability: Any | None = None
    filename_patterns: list[str] | None = None
