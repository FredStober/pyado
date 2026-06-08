"""Typed settings models for each Azure DevOps branch policy type."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from enum import StrEnum
from typing import Any, ClassVar, TypeAlias
from uuid import UUID

from pyado.raw._core import AdoBaseModel
from pyado.raw.pipelines.pipeline import PipelineId
from pyado.raw.repos.git import GitRefName
from pyado.raw.repos.policy import PolicyScope

__all__ = [
    "BuildPolicySettings",
    "CommentRequirementsSettings",
    "CommitAuthorEmailSettings",
    "FileNameSettings",
    "FileSizeRestrictionSettings",
    "GitRepositorySettings",
    "MergeStrategySettings",
    "MinimumReviewersSettings",
    "PathLengthSettings",
    "RequiredReviewersSettings",
    "ReservedNamesSettings",
    "ReviewerId",
    "SearchBranchesPolicySettings",
    "StatusGenre",
    "StatusPolicySettings",
    "WorkItemLinkingSettings",
]

ReviewerId: TypeAlias = UUID


class StatusGenre(StrEnum):
    """Grouping category for 'Status' policy checks.

    ADO uses this to organise status checks shown on a pull request.
    """

    BUILD = "build"
    CHECKS = "checks"
    MERGE = "merge"
    TEST = "test"


class MinimumReviewersSettings(AdoBaseModel):
    """Settings for the 'Minimum number of reviewers' policy.

    Policy type id: ``fa4e907d-c16b-4a4c-9dfa-4906e5d171dd``.
    """

    POLICY_TYPE_ID: ClassVar[UUID] = UUID("fa4e907d-c16b-4a4c-9dfa-4906e5d171dd")
    POLICY_TYPE_NAME: ClassVar[str] = "Minimum number of reviewers"

    scope: list[PolicyScope]
    minimum_approver_count: int
    creator_vote_counts: bool
    allow_downvotes: bool
    reset_on_source_push: bool
    require_vote_on_last_iteration: bool
    reset_rejections_on_source_push: bool
    block_last_pusher_vote: bool
    require_vote_on_each_iteration: bool | None = None


class CommentRequirementsSettings(AdoBaseModel):
    """Settings for the 'Comment requirements' policy.

    Policy type id: ``c6a1889d-b943-4856-b76f-9e46bb6b0df2``.
    """

    POLICY_TYPE_ID: ClassVar[UUID] = UUID("c6a1889d-b943-4856-b76f-9e46bb6b0df2")
    POLICY_TYPE_NAME: ClassVar[str] = "Comment requirements"

    scope: list[PolicyScope]


class WorkItemLinkingSettings(AdoBaseModel):
    """Settings for the 'Work item linking' policy.

    Policy type id: ``40e92b44-2fe1-4dd6-b3d8-74a9c21d0c6e``.
    """

    POLICY_TYPE_ID: ClassVar[UUID] = UUID("40e92b44-2fe1-4dd6-b3d8-74a9c21d0c6e")
    POLICY_TYPE_NAME: ClassVar[str] = "Work item linking"

    scope: list[PolicyScope]


class GitRepositorySettings(AdoBaseModel):
    """Settings for the 'Git repository settings' policy.

    Policy type id: ``7ed39669-655c-494e-b4a0-a08b4da0fcce``.
    """

    POLICY_TYPE_ID: ClassVar[UUID] = UUID("7ed39669-655c-494e-b4a0-a08b4da0fcce")
    POLICY_TYPE_NAME: ClassVar[str] = "Git repository settings"

    scope: list[PolicyScope]
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


class ReservedNamesSettings(AdoBaseModel):
    """Settings for the 'Reserved names restriction' policy.

    Policy type id: ``db2b9b4c-180d-4529-9701-01541d19f36b``.
    """

    POLICY_TYPE_ID: ClassVar[UUID] = UUID("db2b9b4c-180d-4529-9701-01541d19f36b")
    POLICY_TYPE_NAME: ClassVar[str] = "Reserved names restriction"

    scope: list[PolicyScope]


class PathLengthSettings(AdoBaseModel):
    """Settings for the 'Path Length restriction' policy.

    Policy type id: ``001a79cf-fda1-4c4e-9e7c-bac40ee5ead8``.
    """

    POLICY_TYPE_ID: ClassVar[UUID] = UUID("001a79cf-fda1-4c4e-9e7c-bac40ee5ead8")

    scope: list[PolicyScope]
    max_path_length: int


class FileSizeRestrictionSettings(AdoBaseModel):
    """Settings for the 'File size restriction' policy.

    Policy type id: ``2e26e725-8201-4edd-8bf5-978563c34a80``.
    """

    POLICY_TYPE_ID: ClassVar[UUID] = UUID("2e26e725-8201-4edd-8bf5-978563c34a80")

    scope: list[PolicyScope]
    maximum_git_blob_size_in_bytes: int
    use_uncompressed_size: bool


class FileNameSettings(AdoBaseModel):
    """Settings for the 'File name restriction' policy.

    Policy type id: ``51c78909-e838-41a2-9496-c647091e3c61``.
    """

    POLICY_TYPE_ID: ClassVar[UUID] = UUID("51c78909-e838-41a2-9496-c647091e3c61")

    scope: list[PolicyScope]
    filename_patterns: list[str] | None = None


class MergeStrategySettings(AdoBaseModel):
    """Settings for the 'Require a merge strategy' policy.

    Policy type id: ``fa4e907d-c16b-4a4c-9dfa-4916e5d171ab``.
    All merge-type flags default to ``None`` (absent), meaning that strategy
    is not explicitly permitted.
    """

    POLICY_TYPE_ID: ClassVar[UUID] = UUID("fa4e907d-c16b-4a4c-9dfa-4916e5d171ab")

    scope: list[PolicyScope]
    allow_no_fast_forward: bool | None = None
    allow_squash: bool | None = None
    allow_rebase: bool | None = None
    allow_rebase_merge: bool | None = None


class CommitAuthorEmailSettings(AdoBaseModel):
    """Settings for the 'Commit author email validation' policy.

    Policy type id: ``77ed4bd3-b063-4689-934a-175e4d0a78d7``.
    """

    POLICY_TYPE_ID: ClassVar[UUID] = UUID("77ed4bd3-b063-4689-934a-175e4d0a78d7")

    scope: list[PolicyScope]
    author_email_patterns: list[str] | None = None


class BuildPolicySettings(AdoBaseModel):
    """Settings for the 'Build' policy.

    Policy type id: ``0609b952-1397-4640-95ec-e00a01b2c241``.
    """

    POLICY_TYPE_ID: ClassVar[UUID] = UUID("0609b952-1397-4640-95ec-e00a01b2c241")

    scope: list[PolicyScope]
    build_definition_id: PipelineId
    queue_on_source_update_only: bool
    manual_queue_only: bool
    valid_duration: float
    display_name: str | None = None
    filename_patterns: list[str] | None = None


class SearchBranchesPolicySettings(AdoBaseModel):
    """Settings for the 'GitRepositorySettingsPolicyName' policy.

    Policy type id: ``0517f88d-4ec5-4343-9d26-9930ebd53069``.
    Defines which branches are indexed for cross-branch search operations.
    """

    POLICY_TYPE_ID: ClassVar[UUID] = UUID("0517f88d-4ec5-4343-9d26-9930ebd53069")

    scope: list[PolicyScope]
    search_branches: list[GitRefName]


class RequiredReviewersSettings(AdoBaseModel):
    """Settings for the 'Required reviewers' policy.

    Policy type id: ``fd2167ab-b0be-447a-8ec8-39368250530e``.
    """

    POLICY_TYPE_ID: ClassVar[UUID] = UUID("fd2167ab-b0be-447a-8ec8-39368250530e")

    scope: list[PolicyScope]
    required_reviewer_ids: list[ReviewerId]
    minimum_approver_count: int
    creator_vote_counts: bool
    message: str | None = None
    filename_patterns: list[str] | None = None


class StatusPolicySettings(AdoBaseModel):
    """Settings for the 'Status' policy.

    Policy type id: ``cbdc66da-9728-4af8-aada-9a5a32e4a226``.
    """

    POLICY_TYPE_ID: ClassVar[UUID] = UUID("cbdc66da-9728-4af8-aada-9a5a32e4a226")

    scope: list[PolicyScope]
    status_name: str
    status_genre: StatusGenre
    author_id: UUID
    invalidate_on_source_update: bool
    default_display_name: str
    policy_applicability: Any | None = None
    filename_patterns: list[str] | None = None
