"""Tests for pyado.oop.repos.policy_types typed OOP policy models."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import ClassVar
from uuid import UUID, uuid4

import pytest

from pyado.oop.repos.policy_types import (
    BuildPolicy,
    CommentRequirementsPolicy,
    CommitAuthorEmailPolicy,
    FileNamePolicy,
    FileSizeRestrictionPolicy,
    GitRepositoryPolicy,
    MergeStrategyPolicy,
    MinimumReviewersPolicy,
    PathLengthPolicy,
    RepoPolicyScope,
    RequiredReviewersPolicy,
    ReservedNamesPolicy,
    SearchBranchesPolicy,
    StatusPolicy,
    WorkItemLinkingPolicy,
)
from pyado.raw import (
    PolicyConfigurationInfo,
    PolicyConfigurationRequest,
    PolicyScope,
    PolicyScopeMatchKind,
    PolicyTypeIdRef,
    StatusGenre,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_REPO_ID = uuid4()


def _branch_scope() -> PolicyScope:
    return PolicyScope(
        repository_id=_REPO_ID,
        ref_name="refs/heads/main",
        match_kind=PolicyScopeMatchKind.EXACT,
    )


def _branch_scope_dict() -> dict:  # type: ignore[type-arg]
    return {
        "repositoryId": str(_REPO_ID),
        "refName": "refs/heads/main",
        "matchKind": "Exact",
    }


def _repo_scope() -> RepoPolicyScope:
    return RepoPolicyScope(repository_id=_REPO_ID)


def _repo_scope_dict() -> dict:  # type: ignore[type-arg]
    return {"repositoryId": str(_REPO_ID)}


def _make_info(type_id: UUID, settings: dict) -> PolicyConfigurationInfo:  # type: ignore[type-arg]
    return PolicyConfigurationInfo.model_validate(
        {
            "id": 1,
            "type": {"id": str(type_id), "displayName": "test"},
            "isEnabled": True,
            "isBlocking": True,
            "settings": settings,
        }
    )


def _make_request(type_id: UUID, settings: dict) -> PolicyConfigurationRequest:  # type: ignore[type-arg]
    return PolicyConfigurationRequest(
        is_enabled=True,
        is_blocking=True,
        type=PolicyTypeIdRef(id=type_id),
        settings=settings,
    )


# ---------------------------------------------------------------------------
# RepoPolicyScope
# ---------------------------------------------------------------------------


class TestRepoPolicyScope:
    def test_serialises_repository_id(self) -> None:
        scope = RepoPolicyScope(repository_id=_REPO_ID)
        dumped = scope.model_dump(by_alias=True, exclude_none=True)
        assert dumped == {"repositoryId": _REPO_ID}

    def test_none_repository_id_excluded_with_exclude_none(self) -> None:
        scope = RepoPolicyScope(repository_id=None)
        dumped = scope.model_dump(by_alias=True, exclude_none=True)
        assert dumped == {}

    def test_validates_from_dict(self) -> None:
        scope = RepoPolicyScope.model_validate({"repositoryId": str(_REPO_ID)})
        assert scope.repository_id == _REPO_ID


# ---------------------------------------------------------------------------
# BasePolicyModel: settings exclusion
# ---------------------------------------------------------------------------


class TestBasePolicyModelToRequestExcludesEnabledBlocking:
    def test_to_request_excludes_enabled_blocking(self) -> None:
        policy = MinimumReviewersPolicy(
            scope=[_branch_scope()],
            minimum_approver_count=1,
            creator_vote_counts=False,
            allow_downvotes=False,
            reset_on_source_push=False,
            require_vote_on_last_iteration=False,
            reset_rejections_on_source_push=False,
            block_last_pusher_vote=False,
        )
        result = policy.to_request()
        assert "isEnabled" not in result.settings
        assert "isBlocking" not in result.settings


# ---------------------------------------------------------------------------
# MinimumReviewersPolicy
# ---------------------------------------------------------------------------


class TestMinimumReviewersPolicy:
    _settings: ClassVar[dict] = {  # type: ignore[type-arg]
        "scope": [_branch_scope_dict()],
        "minimumApproverCount": 2,
        "creatorVoteCounts": False,
        "allowDownvotes": False,
        "resetOnSourcePush": True,
        "requireVoteOnLastIteration": False,
        "resetRejectionsOnSourcePush": False,
        "blockLastPusherVote": False,
    }

    def test_to_request(self) -> None:
        policy = MinimumReviewersPolicy(
            scope=[_branch_scope()],
            minimum_approver_count=2,
            creator_vote_counts=False,
            allow_downvotes=False,
            reset_on_source_push=True,
            require_vote_on_last_iteration=False,
            reset_rejections_on_source_push=False,
            block_last_pusher_vote=False,
        )
        result = policy.to_request()
        assert result.type.id == MinimumReviewersPolicy.POLICY_TYPE_ID
        assert result.is_enabled is True
        assert result.is_blocking is True
        assert isinstance(result.settings, dict)

    def test_from_info(self) -> None:
        info = _make_info(MinimumReviewersPolicy.POLICY_TYPE_ID, self._settings)
        policy = MinimumReviewersPolicy.from_info(info)
        assert policy.minimum_approver_count == 2
        assert policy.reset_on_source_push is True

    def test_from_request(self) -> None:
        request = _make_request(MinimumReviewersPolicy.POLICY_TYPE_ID, self._settings)
        policy = MinimumReviewersPolicy.from_request(request)
        assert policy.minimum_approver_count == 2


# ---------------------------------------------------------------------------
# CommentRequirementsPolicy
# ---------------------------------------------------------------------------


class TestCommentRequirementsPolicy:
    _settings: ClassVar[dict] = {"scope": [_branch_scope_dict()]}  # type: ignore[type-arg]

    def test_to_request(self) -> None:
        policy = CommentRequirementsPolicy(scope=[_branch_scope()])
        result = policy.to_request()
        assert result.type.id == CommentRequirementsPolicy.POLICY_TYPE_ID
        assert result.is_enabled is True
        assert result.is_blocking is True
        assert isinstance(result.settings, dict)

    def test_from_info(self) -> None:
        info = _make_info(CommentRequirementsPolicy.POLICY_TYPE_ID, self._settings)
        policy = CommentRequirementsPolicy.from_info(info)
        assert len(policy.scope) == 1

    def test_from_request(self) -> None:
        request = _make_request(
            CommentRequirementsPolicy.POLICY_TYPE_ID, self._settings
        )
        policy = CommentRequirementsPolicy.from_request(request)
        assert len(policy.scope) == 1


# ---------------------------------------------------------------------------
# WorkItemLinkingPolicy
# ---------------------------------------------------------------------------


class TestWorkItemLinkingPolicy:
    _settings: ClassVar[dict] = {"scope": [_branch_scope_dict()]}  # type: ignore[type-arg]

    def test_to_request(self) -> None:
        policy = WorkItemLinkingPolicy(scope=[_branch_scope()])
        result = policy.to_request()
        assert result.type.id == WorkItemLinkingPolicy.POLICY_TYPE_ID
        assert isinstance(result.settings, dict)

    def test_from_info(self) -> None:
        info = _make_info(WorkItemLinkingPolicy.POLICY_TYPE_ID, self._settings)
        policy = WorkItemLinkingPolicy.from_info(info)
        assert len(policy.scope) == 1

    def test_from_request(self) -> None:
        request = _make_request(WorkItemLinkingPolicy.POLICY_TYPE_ID, self._settings)
        policy = WorkItemLinkingPolicy.from_request(request)
        assert len(policy.scope) == 1


# ---------------------------------------------------------------------------
# GitRepositoryPolicy
# ---------------------------------------------------------------------------


class TestGitRepositoryPolicy:
    _settings: ClassVar[dict] = {  # type: ignore[type-arg]
        "scope": [_repo_scope_dict()],
        "enforceConsistentCase": True,
    }

    def test_to_request(self) -> None:
        policy = GitRepositoryPolicy(
            scope=[_repo_scope()], enforce_consistent_case=True
        )
        result = policy.to_request()
        assert result.type.id == GitRepositoryPolicy.POLICY_TYPE_ID
        assert isinstance(result.settings, dict)

    def test_from_info(self) -> None:
        info = _make_info(GitRepositoryPolicy.POLICY_TYPE_ID, self._settings)
        policy = GitRepositoryPolicy.from_info(info)
        assert policy.enforce_consistent_case is True
        assert policy.scope[0].repository_id == _REPO_ID

    def test_from_request(self) -> None:
        request = _make_request(GitRepositoryPolicy.POLICY_TYPE_ID, self._settings)
        policy = GitRepositoryPolicy.from_request(request)
        assert policy.enforce_consistent_case is True


# ---------------------------------------------------------------------------
# ReservedNamesPolicy
# ---------------------------------------------------------------------------


class TestReservedNamesPolicy:
    _settings: ClassVar[dict] = {"scope": [_repo_scope_dict()]}  # type: ignore[type-arg]

    def test_to_request(self) -> None:
        policy = ReservedNamesPolicy(scope=[_repo_scope()])
        result = policy.to_request()
        assert result.type.id == ReservedNamesPolicy.POLICY_TYPE_ID
        assert isinstance(result.settings, dict)

    def test_from_info(self) -> None:
        info = _make_info(ReservedNamesPolicy.POLICY_TYPE_ID, self._settings)
        policy = ReservedNamesPolicy.from_info(info)
        assert policy.scope[0].repository_id == _REPO_ID

    def test_from_request(self) -> None:
        request = _make_request(ReservedNamesPolicy.POLICY_TYPE_ID, self._settings)
        policy = ReservedNamesPolicy.from_request(request)
        assert policy.scope[0].repository_id == _REPO_ID


# ---------------------------------------------------------------------------
# PathLengthPolicy
# ---------------------------------------------------------------------------


class TestPathLengthPolicy:
    _settings: ClassVar[dict] = {  # type: ignore[type-arg]
        "scope": [_repo_scope_dict()],
        "maxPathLength": 260,
    }

    def test_to_request(self) -> None:
        policy = PathLengthPolicy(scope=[_repo_scope()], max_path_length=260)
        result = policy.to_request()
        assert result.type.id == PathLengthPolicy.POLICY_TYPE_ID
        assert isinstance(result.settings, dict)

    def test_from_info(self) -> None:
        info = _make_info(PathLengthPolicy.POLICY_TYPE_ID, self._settings)
        policy = PathLengthPolicy.from_info(info)
        assert policy.max_path_length == 260

    def test_from_request(self) -> None:
        request = _make_request(PathLengthPolicy.POLICY_TYPE_ID, self._settings)
        policy = PathLengthPolicy.from_request(request)
        assert policy.max_path_length == 260


# ---------------------------------------------------------------------------
# FileSizeRestrictionPolicy
# ---------------------------------------------------------------------------


class TestFileSizeRestrictionPolicy:
    _settings: ClassVar[dict] = {  # type: ignore[type-arg]
        "scope": [_repo_scope_dict()],
        "maximumGitBlobSizeInBytes": 104857600,
        "useUncompressedSize": False,
    }

    def test_to_request(self) -> None:
        policy = FileSizeRestrictionPolicy(
            scope=[_repo_scope()],
            maximum_git_blob_size_in_bytes=104857600,
            use_uncompressed_size=False,
        )
        result = policy.to_request()
        assert result.type.id == FileSizeRestrictionPolicy.POLICY_TYPE_ID
        assert isinstance(result.settings, dict)

    def test_from_info(self) -> None:
        info = _make_info(FileSizeRestrictionPolicy.POLICY_TYPE_ID, self._settings)
        policy = FileSizeRestrictionPolicy.from_info(info)
        assert policy.maximum_git_blob_size_in_bytes == 104857600

    def test_from_request(self) -> None:
        request = _make_request(
            FileSizeRestrictionPolicy.POLICY_TYPE_ID, self._settings
        )
        policy = FileSizeRestrictionPolicy.from_request(request)
        assert policy.use_uncompressed_size is False


# ---------------------------------------------------------------------------
# FileNamePolicy
# ---------------------------------------------------------------------------


class TestFileNamePolicy:
    _settings: ClassVar[dict] = {  # type: ignore[type-arg]
        "scope": [_repo_scope_dict()],
        "filenamePatterns": ["*.exe"],
    }

    def test_to_request(self) -> None:
        policy = FileNamePolicy(scope=[_repo_scope()], filename_patterns=["*.exe"])
        result = policy.to_request()
        assert result.type.id == FileNamePolicy.POLICY_TYPE_ID
        assert isinstance(result.settings, dict)

    def test_from_info(self) -> None:
        info = _make_info(FileNamePolicy.POLICY_TYPE_ID, self._settings)
        policy = FileNamePolicy.from_info(info)
        assert policy.filename_patterns == ["*.exe"]

    def test_from_request(self) -> None:
        request = _make_request(FileNamePolicy.POLICY_TYPE_ID, self._settings)
        policy = FileNamePolicy.from_request(request)
        assert policy.filename_patterns == ["*.exe"]


# ---------------------------------------------------------------------------
# MergeStrategyPolicy
# ---------------------------------------------------------------------------


class TestMergeStrategyPolicy:
    _settings: ClassVar[dict] = {  # type: ignore[type-arg]
        "scope": [_branch_scope_dict()],
        "allowSquash": True,
    }

    def test_to_request(self) -> None:
        policy = MergeStrategyPolicy(scope=[_branch_scope()], allow_squash=True)
        result = policy.to_request()
        assert result.type.id == MergeStrategyPolicy.POLICY_TYPE_ID
        assert isinstance(result.settings, dict)

    def test_from_info(self) -> None:
        info = _make_info(MergeStrategyPolicy.POLICY_TYPE_ID, self._settings)
        policy = MergeStrategyPolicy.from_info(info)
        assert policy.allow_squash is True

    def test_from_request(self) -> None:
        request = _make_request(MergeStrategyPolicy.POLICY_TYPE_ID, self._settings)
        policy = MergeStrategyPolicy.from_request(request)
        assert policy.allow_squash is True


# ---------------------------------------------------------------------------
# CommitAuthorEmailPolicy
# ---------------------------------------------------------------------------


class TestCommitAuthorEmailPolicy:
    _settings: ClassVar[dict] = {  # type: ignore[type-arg]
        "scope": [_repo_scope_dict()],
        "authorEmailPatterns": ["*@example.com"],
    }

    def test_to_request(self) -> None:
        policy = CommitAuthorEmailPolicy(
            scope=[_repo_scope()], author_email_patterns=["*@example.com"]
        )
        result = policy.to_request()
        assert result.type.id == CommitAuthorEmailPolicy.POLICY_TYPE_ID
        assert isinstance(result.settings, dict)

    def test_from_info(self) -> None:
        info = _make_info(CommitAuthorEmailPolicy.POLICY_TYPE_ID, self._settings)
        policy = CommitAuthorEmailPolicy.from_info(info)
        assert policy.author_email_patterns == ["*@example.com"]

    def test_from_request(self) -> None:
        request = _make_request(CommitAuthorEmailPolicy.POLICY_TYPE_ID, self._settings)
        policy = CommitAuthorEmailPolicy.from_request(request)
        assert policy.author_email_patterns == ["*@example.com"]


# ---------------------------------------------------------------------------
# BuildPolicy
# ---------------------------------------------------------------------------

_BUILD_DEF_ID = 42


class TestBuildPolicy:
    _settings: ClassVar[dict] = {  # type: ignore[type-arg]
        "scope": [_branch_scope_dict()],
        "buildDefinitionId": _BUILD_DEF_ID,
        "queueOnSourceUpdateOnly": True,
        "manualQueueOnly": False,
        "validDuration": 720.0,
    }

    def test_to_request(self) -> None:
        policy = BuildPolicy(
            scope=[_branch_scope()],
            build_definition_id=_BUILD_DEF_ID,
            queue_on_source_update_only=True,
            manual_queue_only=False,
            valid_duration=720.0,
        )
        result = policy.to_request()
        assert result.type.id == BuildPolicy.POLICY_TYPE_ID
        assert result.is_enabled is True
        assert result.is_blocking is True
        assert isinstance(result.settings, dict)

    def test_from_info(self) -> None:
        info = _make_info(BuildPolicy.POLICY_TYPE_ID, self._settings)
        policy = BuildPolicy.from_info(info)
        assert policy.build_definition_id == _BUILD_DEF_ID
        assert policy.valid_duration == pytest.approx(720.0)

    def test_from_request(self) -> None:
        request = _make_request(BuildPolicy.POLICY_TYPE_ID, self._settings)
        policy = BuildPolicy.from_request(request)
        assert policy.queue_on_source_update_only is True


# ---------------------------------------------------------------------------
# SearchBranchesPolicy
# ---------------------------------------------------------------------------


class TestSearchBranchesPolicy:
    _settings: ClassVar[dict] = {  # type: ignore[type-arg]
        "scope": [_repo_scope_dict()],
        "searchBranches": ["refs/heads/main"],
    }

    def test_to_request(self) -> None:
        policy = SearchBranchesPolicy(
            scope=[_repo_scope()], search_branches=["refs/heads/main"]
        )
        result = policy.to_request()
        assert result.type.id == SearchBranchesPolicy.POLICY_TYPE_ID
        assert isinstance(result.settings, dict)

    def test_from_info(self) -> None:
        info = _make_info(SearchBranchesPolicy.POLICY_TYPE_ID, self._settings)
        policy = SearchBranchesPolicy.from_info(info)
        assert policy.search_branches == ["refs/heads/main"]

    def test_from_request(self) -> None:
        request = _make_request(SearchBranchesPolicy.POLICY_TYPE_ID, self._settings)
        policy = SearchBranchesPolicy.from_request(request)
        assert policy.search_branches == ["refs/heads/main"]


# ---------------------------------------------------------------------------
# RequiredReviewersPolicy
# ---------------------------------------------------------------------------

_REVIEWER_ID = uuid4()


class TestRequiredReviewersPolicy:
    _settings: ClassVar[dict] = {  # type: ignore[type-arg]
        "scope": [_branch_scope_dict()],
        "requiredReviewerIds": [str(_REVIEWER_ID)],
        "minimumApproverCount": 1,
        "creatorVoteCounts": False,
    }

    def test_to_request(self) -> None:
        policy = RequiredReviewersPolicy(
            scope=[_branch_scope()],
            required_reviewer_ids=[_REVIEWER_ID],
            minimum_approver_count=1,
            creator_vote_counts=False,
        )
        result = policy.to_request()
        assert result.type.id == RequiredReviewersPolicy.POLICY_TYPE_ID
        assert isinstance(result.settings, dict)

    def test_from_info(self) -> None:
        info = _make_info(RequiredReviewersPolicy.POLICY_TYPE_ID, self._settings)
        policy = RequiredReviewersPolicy.from_info(info)
        assert policy.minimum_approver_count == 1

    def test_from_request(self) -> None:
        request = _make_request(RequiredReviewersPolicy.POLICY_TYPE_ID, self._settings)
        policy = RequiredReviewersPolicy.from_request(request)
        assert policy.creator_vote_counts is False


# ---------------------------------------------------------------------------
# StatusPolicy
# ---------------------------------------------------------------------------

_AUTHOR_ID = uuid4()


class TestStatusPolicy:
    _settings: ClassVar[dict] = {  # type: ignore[type-arg]
        "scope": [_branch_scope_dict()],
        "statusName": "ci/build",
        "statusGenre": "build",
        "authorId": str(_AUTHOR_ID),
        "invalidateOnSourceUpdate": True,
        "defaultDisplayName": "Build CI",
    }

    def test_to_request(self) -> None:
        policy = StatusPolicy(
            scope=[_branch_scope()],
            status_name="ci/build",
            status_genre=StatusGenre.BUILD,
            author_id=_AUTHOR_ID,
            invalidate_on_source_update=True,
            default_display_name="Build CI",
        )
        result = policy.to_request()
        assert result.type.id == StatusPolicy.POLICY_TYPE_ID
        assert result.is_enabled is True
        assert result.is_blocking is True
        assert isinstance(result.settings, dict)

    def test_from_info(self) -> None:
        info = _make_info(StatusPolicy.POLICY_TYPE_ID, self._settings)
        policy = StatusPolicy.from_info(info)
        assert policy.status_name == "ci/build"
        assert policy.status_genre == StatusGenre.BUILD
        assert policy.author_id == _AUTHOR_ID

    def test_from_request(self) -> None:
        request = _make_request(StatusPolicy.POLICY_TYPE_ID, self._settings)
        policy = StatusPolicy.from_request(request)
        assert policy.default_display_name == "Build CI"
