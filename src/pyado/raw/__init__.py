"""Raw Azure DevOps REST API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

__all__ = [
    "GIT_SECURITY_NAMESPACE_ID",
    "ZERO_SHA",
    "ADOUrl",
    "AccessControlEntry",
    "AccessControlList",
    "AccessToken",
    "ApiCall",
    "BranchName",
    "BranchStatistics",
    "BuildArtifact",
    "BuildArtifactResource",
    "BuildAttemptInfo",
    "BuildDetails",
    "BuildExpand",
    "BuildId",
    "BuildIssue",
    "BuildIssueType",
    "BuildLogId",
    "BuildLogInfo",
    "BuildLogType",
    "BuildQueueRequest",
    "BuildRecordInfo",
    "BuildRecordResult",
    "BuildRecordState",
    "BuildRecordType",
    "BuildRecordTypeInfo",
    "BuildResult",
    "BuildSearchCriteria",
    "BuildStatus",
    "ClassificationNode",
    "ClassificationNodeAttributes",
    "ClassificationNodePatchRequest",
    "ClassificationNodeRequest",
    "ClassificationNodeType",
    "ClassificationNodeUrlType",
    "CommitDiffPage",
    "CommitId",
    "CommitIdRef",
    "ConnectionData",
    "ConnectionDataIdentity",
    "GitChangeType",
    "GitCommitChange",
    "GitCommitChangeItem",
    "GitCommitRef",
    "GitCommitSearchCriteria",
    "GitForkRef",
    "GitItem",
    "GitPushChange",
    "GitPushChangeItem",
    "GitPushCommit",
    "GitPushContentType",
    "GitPushNewContent",
    "GitPushRefUpdate",
    "GitPushRequest",
    "GitPushResult",
    "GitRef",
    "GitRefFilter",
    "GitRefUpdate",
    "GitStatus",
    "GitStatusState",
    "GraphGroup",
    "HTMLTextFilter",
    "IdentityIdRef",
    "IdentityInfo",
    "JobEventName",
    "JobEventPayload",
    "JobEventResult",
    "JobFeedPayload",
    "JobId",
    "JsonPatchAdd",
    "JsonPatchRemove",
    "PipelineApproval",
    "PipelineApprovalStatus",
    "PipelineApprovalStep",
    "PipelineApprovalUpdateRequest",
    "PipelineDefinitionInfo",
    "PipelineId",
    "PipelineInfo",
    "PipelinePermissionEntry",
    "PipelineResourcePermissions",
    "PipelineResourceType",
    "PipelineRunInfo",
    "PipelineRunRequest",
    "PipelineRunResult",
    "PipelineRunState",
    "PlanId",
    "PrIterationChange",
    "PrIterationChangeItem",
    "ProjectId",
    "ProjectInfo",
    "ProjectName",
    "ProjectState",
    "ProjectVisibility",
    "PullRequestCompletionOptions",
    "PullRequestCreateRequest",
    "PullRequestId",
    "PullRequestIteration",
    "PullRequestIterationContext",
    "PullRequestIterationRecord",
    "PullRequestLabel",
    "PullRequestListItem",
    "PullRequestMergeFailureType",
    "PullRequestMergeStatus",
    "PullRequestMergeStrategy",
    "PullRequestResponse",
    "PullRequestReviewer",
    "PullRequestReviewerRequest",
    "PullRequestReviewerVoteRequest",
    "PullRequestSearchCriteria",
    "PullRequestStatus",
    "PullRequestStatusContext",
    "PullRequestStatusInfo",
    "PullRequestStatusRequest",
    "PullRequestStatusState",
    "PullRequestThreadCommentRequest",
    "PullRequestThreadCommentResponse",
    "PullRequestThreadCommentType",
    "PullRequestThreadContext",
    "PullRequestThreadHistoryContext",
    "PullRequestThreadPosition",
    "PullRequestThreadRequest",
    "PullRequestThreadResponse",
    "PullRequestThreadStatus",
    "PullRequestUpdateRequest",
    "PullRequestVote",
    "QueueId",
    "RecursionLevel",
    "RepositoryId",
    "RepositoryInfo",
    "RepositoryName",
    "RepositoryRef",
    "SprintIterationAttributes",
    "SprintIterationId",
    "SprintIterationInfo",
    "SprintIterationPath",
    "SprintIterationTimeframe",
    "SshUrl",
    "TaskId",
    "TeamFieldValue",
    "TeamInfo",
    "TeamMember",
    "TextFormat",
    "TimelineId",
    "TimelineRecordsUpdatePayload",
    "UserId",
    "UserProfile",
    "VariableGroupCreateRequest",
    "VariableGroupId",
    "VariableGroupInfo",
    "VariableGroupProjectReference",
    "VariableGroupUpdateRequest",
    "VariableGroupUserInfo",
    "VariableInfo",
    "VersionDescriptorType",
    "WorkItemArtifactUrlPrefix",
    "WorkItemAttachmentRef",
    "WorkItemComment",
    "WorkItemExpand",
    "WorkItemField",
    "WorkItemFieldName",
    "WorkItemId",
    "WorkItemInfo",
    "WorkItemQuery",
    "WorkItemQueryExpand",
    "WorkItemQueryType",
    "WorkItemRef",
    "WorkItemRelation",
    "WorkItemRelationType",
    "WorkItemState",
    "WorkItemType",
    "WorkItemsBatchRequest",
    "add_team_iteration",
    "create_classification_node",
    "create_tag",
    "delete_build_tag",
    "delete_classification_node",
    "delete_pull_request_label",
    "delete_pull_request_reviewer",
    "delete_tag",
    "delete_team_iteration",
    "delete_variable_group",
    "delete_work_item",
    "delete_work_item_comment",
    "get_build_api_call",
    "get_build_artifact_bytes",
    "get_build_details",
    "get_build_log",
    "get_classification_node",
    "get_commit_diff_page",
    "get_connection_data",
    "get_git_acl",
    "get_identities",
    "get_job_api_call",
    "get_log_api_call",
    "get_my_profile",
    "get_pipeline",
    "get_pipeline_run",
    "get_plan_api_call",
    "get_profile_api_call",
    "get_project",
    "get_pull_request_api_call",
    "get_pull_request_details",
    "get_pull_request_iteration_changes",
    "get_pull_request_labels_details",
    "get_pull_request_reviewers",
    "get_pull_request_thread",
    "get_query_folder",
    "get_query_tree",
    "get_repository_api_call",
    "get_repository_commits",
    "get_repository_info",
    "get_repository_item_bytes",
    "get_repository_statistics",
    "get_session",
    "get_team",
    "get_team_field_values",
    "get_timeline_api_call",
    "get_variable_group_api_call",
    "get_variable_group_details",
    "get_vssps_api_call",
    "get_work_item",
    "get_work_item_api_call",
    "get_work_item_attachment_bytes",
    "iter_approvals",
    "iter_build_artifacts",
    "iter_build_logs",
    "iter_build_tags",
    "iter_build_work_item_ids",
    "iter_builds",
    "iter_graph_groups",
    "iter_pipeline_definitions",
    "iter_pipeline_runs",
    "iter_pipelines",
    "iter_projects",
    "iter_pull_request_commits",
    "iter_pull_request_iterations",
    "iter_pull_request_statuses",
    "iter_pull_request_threads",
    "iter_pull_request_work_item_ids",
    "iter_pull_requests",
    "iter_refs",
    "iter_repository_details",
    "iter_repository_items",
    "iter_sprint_iterations",
    "iter_tags",
    "iter_team_members",
    "iter_teams",
    "iter_timeline_records",
    "iter_variable_group_details",
    "iter_work_item_comments",
    "iter_work_item_revisions",
    "iter_work_items_between_builds",
    "list_approvals",
    "list_build_artifacts",
    "list_build_logs",
    "list_build_tags",
    "list_build_work_item_ids",
    "list_builds",
    "list_graph_groups",
    "list_pipeline_definitions",
    "list_pipeline_runs",
    "list_pipelines",
    "list_projects",
    "list_pull_request_commits",
    "list_pull_request_iterations",
    "list_pull_request_statuses",
    "list_pull_request_threads",
    "list_pull_request_work_item_ids",
    "list_pull_requests",
    "list_refs",
    "list_repository_details",
    "list_repository_items",
    "list_sprint_iterations",
    "list_tags",
    "list_team_members",
    "list_teams",
    "list_timeline_records",
    "list_variable_group_details",
    "list_work_item_comments",
    "list_work_item_revisions",
    "list_work_items_between_builds",
    "make_git_acl_token",
    "make_ref_update",
    "patch_approvals",
    "patch_build",
    "patch_classification_node",
    "patch_pipeline_permission",
    "patch_pull_request",
    "patch_pull_request_thread",
    "patch_timeline_records",
    "patch_work_item",
    "patch_work_item_comment",
    "post_build",
    "post_build_tag",
    "post_job_event",
    "post_job_feed",
    "post_job_logs",
    "post_pipeline_run",
    "post_pull_request",
    "post_pull_request_label",
    "post_pull_request_new_thread",
    "post_pull_request_status",
    "post_pull_request_thread_comment",
    "post_push",
    "post_repository_refs",
    "post_variable_group",
    "post_wiql",
    "post_work_item",
    "post_work_item_attachment_upload",
    "post_work_item_comment",
    "post_work_items_batch",
    "put_pull_request_reviewer",
    "put_pull_request_reviewer_vote",
    "put_variable_group",
    "restore_work_item",
]

from pyado.raw._core import (
    AccessToken as AccessToken,
)
from pyado.raw._core import (
    ADOUrl as ADOUrl,
)
from pyado.raw._core import (
    ApiCall as ApiCall,
)
from pyado.raw._core import (
    HTMLTextFilter as HTMLTextFilter,
)
from pyado.raw._core import (
    JsonPatchAdd as JsonPatchAdd,
)
from pyado.raw._core import (
    JsonPatchRemove as JsonPatchRemove,
)
from pyado.raw._core import (
    get_session as get_session,
)
from pyado.raw.build import (
    BuildArtifact as BuildArtifact,
)
from pyado.raw.build import (
    BuildArtifactResource as BuildArtifactResource,
)
from pyado.raw.build import (
    BuildAttemptInfo as BuildAttemptInfo,
)
from pyado.raw.build import (
    BuildDetails as BuildDetails,
)
from pyado.raw.build import (
    BuildExpand as BuildExpand,
)
from pyado.raw.build import (
    BuildId as BuildId,
)
from pyado.raw.build import (
    BuildIssue as BuildIssue,
)
from pyado.raw.build import (
    BuildIssueType as BuildIssueType,
)
from pyado.raw.build import (
    BuildLogId as BuildLogId,
)
from pyado.raw.build import (
    BuildLogInfo as BuildLogInfo,
)
from pyado.raw.build import (
    BuildLogType as BuildLogType,
)
from pyado.raw.build import (
    BuildQueueRequest as BuildQueueRequest,
)
from pyado.raw.build import (
    BuildRecordInfo as BuildRecordInfo,
)
from pyado.raw.build import (
    BuildRecordResult as BuildRecordResult,
)
from pyado.raw.build import (
    BuildRecordState as BuildRecordState,
)
from pyado.raw.build import (
    BuildRecordType as BuildRecordType,
)
from pyado.raw.build import (
    BuildRecordTypeInfo as BuildRecordTypeInfo,
)
from pyado.raw.build import (
    BuildResult as BuildResult,
)
from pyado.raw.build import (
    BuildSearchCriteria as BuildSearchCriteria,
)
from pyado.raw.build import (
    BuildStatus as BuildStatus,
)
from pyado.raw.build import (
    PipelineDefinitionInfo as PipelineDefinitionInfo,
)
from pyado.raw.build import (
    PlanId as PlanId,
)
from pyado.raw.build import (
    QueueId as QueueId,
)
from pyado.raw.build import (
    TaskId as TaskId,
)
from pyado.raw.build import (
    TimelineId as TimelineId,
)
from pyado.raw.build import (
    delete_build_tag as delete_build_tag,
)
from pyado.raw.build import (
    get_build_api_call as get_build_api_call,
)
from pyado.raw.build import (
    get_build_artifact_bytes as get_build_artifact_bytes,
)
from pyado.raw.build import (
    get_build_details as get_build_details,
)
from pyado.raw.build import (
    get_build_log as get_build_log,
)
from pyado.raw.build import (
    iter_build_artifacts as iter_build_artifacts,
)
from pyado.raw.build import (
    iter_build_logs as iter_build_logs,
)
from pyado.raw.build import (
    iter_build_tags as iter_build_tags,
)
from pyado.raw.build import (
    iter_build_work_item_ids as iter_build_work_item_ids,
)
from pyado.raw.build import (
    iter_builds as iter_builds,
)
from pyado.raw.build import (
    iter_pipeline_definitions as iter_pipeline_definitions,
)
from pyado.raw.build import (
    iter_timeline_records as iter_timeline_records,
)
from pyado.raw.build import (
    iter_work_items_between_builds as iter_work_items_between_builds,
)
from pyado.raw.build import (
    list_build_artifacts as list_build_artifacts,
)
from pyado.raw.build import (
    list_build_logs as list_build_logs,
)
from pyado.raw.build import (
    list_build_tags as list_build_tags,
)
from pyado.raw.build import (
    list_build_work_item_ids as list_build_work_item_ids,
)
from pyado.raw.build import (
    list_builds as list_builds,
)
from pyado.raw.build import (
    list_pipeline_definitions as list_pipeline_definitions,
)
from pyado.raw.build import (
    list_timeline_records as list_timeline_records,
)
from pyado.raw.build import (
    list_work_items_between_builds as list_work_items_between_builds,
)
from pyado.raw.build import (
    patch_build as patch_build,
)
from pyado.raw.build import (
    post_build as post_build,
)
from pyado.raw.build import (
    post_build_tag as post_build_tag,
)
from pyado.raw.git import (
    GIT_SECURITY_NAMESPACE_ID as GIT_SECURITY_NAMESPACE_ID,
)
from pyado.raw.git import (
    ZERO_SHA as ZERO_SHA,
)
from pyado.raw.git import (
    AccessControlEntry as AccessControlEntry,
)
from pyado.raw.git import (
    AccessControlList as AccessControlList,
)
from pyado.raw.git import (
    BranchName as BranchName,
)
from pyado.raw.git import (
    BranchStatistics as BranchStatistics,
)
from pyado.raw.git import (
    CommitDiffPage as CommitDiffPage,
)
from pyado.raw.git import (
    CommitId as CommitId,
)
from pyado.raw.git import (
    GitChangeType as GitChangeType,
)
from pyado.raw.git import (
    GitCommitChange as GitCommitChange,
)
from pyado.raw.git import (
    GitCommitChangeItem as GitCommitChangeItem,
)
from pyado.raw.git import (
    GitCommitRef as GitCommitRef,
)
from pyado.raw.git import (
    GitCommitSearchCriteria as GitCommitSearchCriteria,
)
from pyado.raw.git import (
    GitItem as GitItem,
)
from pyado.raw.git import (
    GitPushChange as GitPushChange,
)
from pyado.raw.git import (
    GitPushChangeItem as GitPushChangeItem,
)
from pyado.raw.git import (
    GitPushCommit as GitPushCommit,
)
from pyado.raw.git import (
    GitPushContentType as GitPushContentType,
)
from pyado.raw.git import (
    GitPushNewContent as GitPushNewContent,
)
from pyado.raw.git import (
    GitPushRefUpdate as GitPushRefUpdate,
)
from pyado.raw.git import (
    GitPushRequest as GitPushRequest,
)
from pyado.raw.git import (
    GitPushResult as GitPushResult,
)
from pyado.raw.git import (
    GitRef as GitRef,
)
from pyado.raw.git import (
    GitRefFilter as GitRefFilter,
)
from pyado.raw.git import (
    GitRefUpdate as GitRefUpdate,
)
from pyado.raw.git import (
    GitStatus as GitStatus,
)
from pyado.raw.git import (
    GitStatusState as GitStatusState,
)
from pyado.raw.git import (
    PullRequestStatusContext as PullRequestStatusContext,
)
from pyado.raw.git import (
    RecursionLevel as RecursionLevel,
)
from pyado.raw.git import (
    RepositoryId as RepositoryId,
)
from pyado.raw.git import (
    RepositoryInfo as RepositoryInfo,
)
from pyado.raw.git import (
    RepositoryName as RepositoryName,
)
from pyado.raw.git import (
    SshUrl as SshUrl,
)
from pyado.raw.git import (
    VersionDescriptorType as VersionDescriptorType,
)
from pyado.raw.git import (
    create_tag as create_tag,
)
from pyado.raw.git import (
    delete_tag as delete_tag,
)
from pyado.raw.git import (
    get_commit_by_id as get_commit_by_id,
)
from pyado.raw.git import (
    get_commit_diff_page as get_commit_diff_page,
)
from pyado.raw.git import (
    get_git_acl as get_git_acl,
)
from pyado.raw.git import (
    get_repository_api_call as get_repository_api_call,
)
from pyado.raw.git import (
    get_repository_commits as get_repository_commits,
)
from pyado.raw.git import (
    get_repository_info as get_repository_info,
)
from pyado.raw.git import (
    get_repository_item_bytes as get_repository_item_bytes,
)
from pyado.raw.git import (
    get_repository_statistics as get_repository_statistics,
)
from pyado.raw.git import (
    iter_refs as iter_refs,
)
from pyado.raw.git import (
    iter_repository_details as iter_repository_details,
)
from pyado.raw.git import (
    iter_repository_items as iter_repository_items,
)
from pyado.raw.git import (
    iter_tags as iter_tags,
)
from pyado.raw.git import (
    list_refs as list_refs,
)
from pyado.raw.git import (
    list_repository_details as list_repository_details,
)
from pyado.raw.git import (
    list_repository_items as list_repository_items,
)
from pyado.raw.git import (
    list_tags as list_tags,
)
from pyado.raw.git import (
    make_git_acl_token as make_git_acl_token,
)
from pyado.raw.git import (
    make_ref_update as make_ref_update,
)
from pyado.raw.git import (
    post_push as post_push,
)
from pyado.raw.git import (
    post_repository_refs as post_repository_refs,
)
from pyado.raw.identity import (
    GraphGroup as GraphGroup,
)
from pyado.raw.identity import (
    IdentityInfo as IdentityInfo,
)
from pyado.raw.identity import (
    get_identities as get_identities,
)
from pyado.raw.identity import (
    get_vssps_api_call as get_vssps_api_call,
)
from pyado.raw.identity import (
    iter_graph_groups as iter_graph_groups,
)
from pyado.raw.identity import (
    list_graph_groups as list_graph_groups,
)
from pyado.raw.pipeline import (
    JobEventName as JobEventName,
)
from pyado.raw.pipeline import (
    JobEventPayload as JobEventPayload,
)
from pyado.raw.pipeline import (
    JobEventResult as JobEventResult,
)
from pyado.raw.pipeline import (
    JobFeedPayload as JobFeedPayload,
)
from pyado.raw.pipeline import (
    JobId as JobId,
)
from pyado.raw.pipeline import (
    PipelineApproval as PipelineApproval,
)
from pyado.raw.pipeline import (
    PipelineApprovalStatus as PipelineApprovalStatus,
)
from pyado.raw.pipeline import (
    PipelineApprovalStep as PipelineApprovalStep,
)
from pyado.raw.pipeline import (
    PipelineApprovalUpdateRequest as PipelineApprovalUpdateRequest,
)
from pyado.raw.pipeline import (
    PipelineId as PipelineId,
)
from pyado.raw.pipeline import (
    PipelineInfo as PipelineInfo,
)
from pyado.raw.pipeline import (
    PipelinePermissionEntry as PipelinePermissionEntry,
)
from pyado.raw.pipeline import (
    PipelineResourcePermissions as PipelineResourcePermissions,
)
from pyado.raw.pipeline import (
    PipelineResourceType as PipelineResourceType,
)
from pyado.raw.pipeline import (
    PipelineRunInfo as PipelineRunInfo,
)
from pyado.raw.pipeline import (
    PipelineRunRequest as PipelineRunRequest,
)
from pyado.raw.pipeline import (
    PipelineRunResult as PipelineRunResult,
)
from pyado.raw.pipeline import (
    PipelineRunState as PipelineRunState,
)
from pyado.raw.pipeline import (
    TimelineRecordsUpdatePayload as TimelineRecordsUpdatePayload,
)
from pyado.raw.pipeline import (
    get_job_api_call as get_job_api_call,
)
from pyado.raw.pipeline import (
    get_log_api_call as get_log_api_call,
)
from pyado.raw.pipeline import (
    get_pipeline as get_pipeline,
)
from pyado.raw.pipeline import (
    get_pipeline_run as get_pipeline_run,
)
from pyado.raw.pipeline import (
    get_plan_api_call as get_plan_api_call,
)
from pyado.raw.pipeline import (
    get_timeline_api_call as get_timeline_api_call,
)
from pyado.raw.pipeline import (
    iter_approvals as iter_approvals,
)
from pyado.raw.pipeline import (
    iter_pipeline_runs as iter_pipeline_runs,
)
from pyado.raw.pipeline import (
    iter_pipelines as iter_pipelines,
)
from pyado.raw.pipeline import (
    list_approvals as list_approvals,
)
from pyado.raw.pipeline import (
    list_pipeline_runs as list_pipeline_runs,
)
from pyado.raw.pipeline import (
    list_pipelines as list_pipelines,
)
from pyado.raw.pipeline import (
    patch_approvals as patch_approvals,
)
from pyado.raw.pipeline import (
    patch_pipeline_permission as patch_pipeline_permission,
)
from pyado.raw.pipeline import (
    patch_timeline_records as patch_timeline_records,
)
from pyado.raw.pipeline import (
    post_job_event as post_job_event,
)
from pyado.raw.pipeline import (
    post_job_feed as post_job_feed,
)
from pyado.raw.pipeline import (
    post_job_logs as post_job_logs,
)
from pyado.raw.pipeline import (
    post_pipeline_run as post_pipeline_run,
)
from pyado.raw.profile import (
    ConnectionData as ConnectionData,
)
from pyado.raw.profile import (
    ConnectionDataIdentity as ConnectionDataIdentity,
)
from pyado.raw.profile import (
    UserProfile as UserProfile,
)
from pyado.raw.profile import (
    get_connection_data as get_connection_data,
)
from pyado.raw.profile import (
    get_my_profile as get_my_profile,
)
from pyado.raw.profile import (
    get_profile_api_call as get_profile_api_call,
)
from pyado.raw.project import (
    ProjectId as ProjectId,
)
from pyado.raw.project import (
    ProjectInfo as ProjectInfo,
)
from pyado.raw.project import (
    ProjectName as ProjectName,
)
from pyado.raw.project import (
    ProjectState as ProjectState,
)
from pyado.raw.project import (
    ProjectVisibility as ProjectVisibility,
)
from pyado.raw.project import (
    get_project as get_project,
)
from pyado.raw.project import (
    iter_projects as iter_projects,
)
from pyado.raw.project import (
    list_projects as list_projects,
)
from pyado.raw.pull_request import (
    CommitIdRef as CommitIdRef,
)
from pyado.raw.pull_request import (
    GitForkRef as GitForkRef,
)
from pyado.raw.pull_request import (
    IdentityIdRef as IdentityIdRef,
)
from pyado.raw.pull_request import (
    PrIterationChange as PrIterationChange,
)
from pyado.raw.pull_request import (
    PrIterationChangeItem as PrIterationChangeItem,
)
from pyado.raw.pull_request import (
    PullRequestCompletionOptions as PullRequestCompletionOptions,
)
from pyado.raw.pull_request import (
    PullRequestCreateRequest as PullRequestCreateRequest,
)
from pyado.raw.pull_request import (
    PullRequestId as PullRequestId,
)
from pyado.raw.pull_request import (
    PullRequestIteration as PullRequestIteration,
)
from pyado.raw.pull_request import (
    PullRequestIterationContext as PullRequestIterationContext,
)
from pyado.raw.pull_request import (
    PullRequestIterationRecord as PullRequestIterationRecord,
)
from pyado.raw.pull_request import (
    PullRequestLabel as PullRequestLabel,
)
from pyado.raw.pull_request import (
    PullRequestListItem as PullRequestListItem,
)
from pyado.raw.pull_request import (
    PullRequestMergeFailureType as PullRequestMergeFailureType,
)
from pyado.raw.pull_request import (
    PullRequestMergeStatus as PullRequestMergeStatus,
)
from pyado.raw.pull_request import (
    PullRequestMergeStrategy as PullRequestMergeStrategy,
)
from pyado.raw.pull_request import (
    PullRequestResponse as PullRequestResponse,
)
from pyado.raw.pull_request import (
    PullRequestReviewer as PullRequestReviewer,
)
from pyado.raw.pull_request import (
    PullRequestReviewerRequest as PullRequestReviewerRequest,
)
from pyado.raw.pull_request import (
    PullRequestReviewerVoteRequest as PullRequestReviewerVoteRequest,
)
from pyado.raw.pull_request import (
    PullRequestSearchCriteria as PullRequestSearchCriteria,
)
from pyado.raw.pull_request import (
    PullRequestStatus as PullRequestStatus,
)
from pyado.raw.pull_request import (
    PullRequestStatusInfo as PullRequestStatusInfo,
)
from pyado.raw.pull_request import (
    PullRequestStatusRequest as PullRequestStatusRequest,
)
from pyado.raw.pull_request import (
    PullRequestStatusState as PullRequestStatusState,
)
from pyado.raw.pull_request import (
    PullRequestThreadCommentRequest as PullRequestThreadCommentRequest,
)
from pyado.raw.pull_request import (
    PullRequestThreadCommentResponse as PullRequestThreadCommentResponse,
)
from pyado.raw.pull_request import (
    PullRequestThreadCommentType as PullRequestThreadCommentType,
)
from pyado.raw.pull_request import (
    PullRequestThreadContext as PullRequestThreadContext,
)
from pyado.raw.pull_request import (
    PullRequestThreadHistoryContext as PullRequestThreadHistoryContext,
)
from pyado.raw.pull_request import (
    PullRequestThreadPosition as PullRequestThreadPosition,
)
from pyado.raw.pull_request import (
    PullRequestThreadRequest as PullRequestThreadRequest,
)
from pyado.raw.pull_request import (
    PullRequestThreadResponse as PullRequestThreadResponse,
)
from pyado.raw.pull_request import (
    PullRequestThreadStatus as PullRequestThreadStatus,
)
from pyado.raw.pull_request import (
    PullRequestUpdateRequest as PullRequestUpdateRequest,
)
from pyado.raw.pull_request import (
    PullRequestVote as PullRequestVote,
)
from pyado.raw.pull_request import (
    RepositoryRef as RepositoryRef,
)
from pyado.raw.pull_request import (
    delete_pull_request_label as delete_pull_request_label,
)
from pyado.raw.pull_request import (
    delete_pull_request_reviewer as delete_pull_request_reviewer,
)
from pyado.raw.pull_request import (
    get_pull_request_api_call as get_pull_request_api_call,
)
from pyado.raw.pull_request import (
    get_pull_request_details as get_pull_request_details,
)
from pyado.raw.pull_request import (
    get_pull_request_iteration_changes as get_pull_request_iteration_changes,
)
from pyado.raw.pull_request import (
    get_pull_request_labels_details as get_pull_request_labels_details,
)
from pyado.raw.pull_request import (
    get_pull_request_reviewers as get_pull_request_reviewers,
)
from pyado.raw.pull_request import (
    get_pull_request_thread as get_pull_request_thread,
)
from pyado.raw.pull_request import (
    iter_pull_request_commits as iter_pull_request_commits,
)
from pyado.raw.pull_request import (
    iter_pull_request_iterations as iter_pull_request_iterations,
)
from pyado.raw.pull_request import (
    iter_pull_request_statuses as iter_pull_request_statuses,
)
from pyado.raw.pull_request import (
    iter_pull_request_threads as iter_pull_request_threads,
)
from pyado.raw.pull_request import (
    iter_pull_request_work_item_ids as iter_pull_request_work_item_ids,
)
from pyado.raw.pull_request import (
    iter_pull_requests as iter_pull_requests,
)
from pyado.raw.pull_request import (
    list_pull_request_commits as list_pull_request_commits,
)
from pyado.raw.pull_request import (
    list_pull_request_iterations as list_pull_request_iterations,
)
from pyado.raw.pull_request import (
    list_pull_request_statuses as list_pull_request_statuses,
)
from pyado.raw.pull_request import (
    list_pull_request_threads as list_pull_request_threads,
)
from pyado.raw.pull_request import (
    list_pull_request_work_item_ids as list_pull_request_work_item_ids,
)
from pyado.raw.pull_request import (
    list_pull_requests as list_pull_requests,
)
from pyado.raw.pull_request import (
    patch_pull_request as patch_pull_request,
)
from pyado.raw.pull_request import (
    patch_pull_request_thread as patch_pull_request_thread,
)
from pyado.raw.pull_request import (
    post_pull_request as post_pull_request,
)
from pyado.raw.pull_request import (
    post_pull_request_label as post_pull_request_label,
)
from pyado.raw.pull_request import (
    post_pull_request_new_thread as post_pull_request_new_thread,
)
from pyado.raw.pull_request import (
    post_pull_request_status as post_pull_request_status,
)
from pyado.raw.pull_request import (
    post_pull_request_thread_comment as post_pull_request_thread_comment,
)
from pyado.raw.pull_request import (
    put_pull_request_reviewer as put_pull_request_reviewer,
)
from pyado.raw.pull_request import (
    put_pull_request_reviewer_vote as put_pull_request_reviewer_vote,
)
from pyado.raw.team import (
    TeamInfo as TeamInfo,
)
from pyado.raw.team import (
    TeamMember as TeamMember,
)
from pyado.raw.team import (
    get_team as get_team,
)
from pyado.raw.team import (
    iter_team_members as iter_team_members,
)
from pyado.raw.team import (
    iter_teams as iter_teams,
)
from pyado.raw.team import (
    list_team_members as list_team_members,
)
from pyado.raw.team import (
    list_teams as list_teams,
)
from pyado.raw.variable_group import (
    UserId as UserId,
)
from pyado.raw.variable_group import (
    VariableGroupCreateRequest as VariableGroupCreateRequest,
)
from pyado.raw.variable_group import (
    VariableGroupId as VariableGroupId,
)
from pyado.raw.variable_group import (
    VariableGroupInfo as VariableGroupInfo,
)
from pyado.raw.variable_group import (
    VariableGroupProjectReference as VariableGroupProjectReference,
)
from pyado.raw.variable_group import (
    VariableGroupUpdateRequest as VariableGroupUpdateRequest,
)
from pyado.raw.variable_group import (
    VariableGroupUserInfo as VariableGroupUserInfo,
)
from pyado.raw.variable_group import (
    VariableInfo as VariableInfo,
)
from pyado.raw.variable_group import (
    delete_variable_group as delete_variable_group,
)
from pyado.raw.variable_group import (
    get_variable_group_api_call as get_variable_group_api_call,
)
from pyado.raw.variable_group import (
    get_variable_group_details as get_variable_group_details,
)
from pyado.raw.variable_group import (
    iter_variable_group_details as iter_variable_group_details,
)
from pyado.raw.variable_group import (
    list_variable_group_details as list_variable_group_details,
)
from pyado.raw.variable_group import (
    post_variable_group as post_variable_group,
)
from pyado.raw.variable_group import (
    put_variable_group as put_variable_group,
)
from pyado.raw.work_item import (
    ClassificationNode as ClassificationNode,
)
from pyado.raw.work_item import (
    ClassificationNodeAttributes as ClassificationNodeAttributes,
)
from pyado.raw.work_item import (
    ClassificationNodePatchRequest as ClassificationNodePatchRequest,
)
from pyado.raw.work_item import (
    ClassificationNodeRequest as ClassificationNodeRequest,
)
from pyado.raw.work_item import (
    ClassificationNodeType as ClassificationNodeType,
)
from pyado.raw.work_item import (
    ClassificationNodeUrlType as ClassificationNodeUrlType,
)
from pyado.raw.work_item import (
    SprintIterationAttributes as SprintIterationAttributes,
)
from pyado.raw.work_item import (
    SprintIterationId as SprintIterationId,
)
from pyado.raw.work_item import (
    SprintIterationInfo as SprintIterationInfo,
)
from pyado.raw.work_item import (
    SprintIterationPath as SprintIterationPath,
)
from pyado.raw.work_item import (
    SprintIterationTimeframe as SprintIterationTimeframe,
)
from pyado.raw.work_item import (
    TeamFieldValue as TeamFieldValue,
)
from pyado.raw.work_item import (
    TextFormat as TextFormat,
)
from pyado.raw.work_item import (
    WorkItemArtifactUrlPrefix as WorkItemArtifactUrlPrefix,
)
from pyado.raw.work_item import (
    WorkItemAttachmentRef as WorkItemAttachmentRef,
)
from pyado.raw.work_item import (
    WorkItemComment as WorkItemComment,
)
from pyado.raw.work_item import (
    WorkItemExpand as WorkItemExpand,
)
from pyado.raw.work_item import (
    WorkItemField as WorkItemField,
)
from pyado.raw.work_item import (
    WorkItemFieldName as WorkItemFieldName,
)
from pyado.raw.work_item import (
    WorkItemId as WorkItemId,
)
from pyado.raw.work_item import (
    WorkItemInfo as WorkItemInfo,
)
from pyado.raw.work_item import (
    WorkItemQuery as WorkItemQuery,
)
from pyado.raw.work_item import (
    WorkItemQueryExpand as WorkItemQueryExpand,
)
from pyado.raw.work_item import (
    WorkItemQueryType as WorkItemQueryType,
)
from pyado.raw.work_item import (
    WorkItemRef as WorkItemRef,
)
from pyado.raw.work_item import (
    WorkItemRelation as WorkItemRelation,
)
from pyado.raw.work_item import (
    WorkItemRelationType as WorkItemRelationType,
)
from pyado.raw.work_item import (
    WorkItemsBatchRequest as WorkItemsBatchRequest,
)
from pyado.raw.work_item import (
    WorkItemState as WorkItemState,
)
from pyado.raw.work_item import (
    WorkItemType as WorkItemType,
)
from pyado.raw.work_item import (
    add_team_iteration as add_team_iteration,
)
from pyado.raw.work_item import (
    create_classification_node as create_classification_node,
)
from pyado.raw.work_item import (
    delete_classification_node as delete_classification_node,
)
from pyado.raw.work_item import (
    delete_team_iteration as delete_team_iteration,
)
from pyado.raw.work_item import (
    delete_work_item as delete_work_item,
)
from pyado.raw.work_item import (
    delete_work_item_comment as delete_work_item_comment,
)
from pyado.raw.work_item import (
    get_classification_node as get_classification_node,
)
from pyado.raw.work_item import (
    get_query_folder as get_query_folder,
)
from pyado.raw.work_item import (
    get_query_tree as get_query_tree,
)
from pyado.raw.work_item import (
    get_team_field_values as get_team_field_values,
)
from pyado.raw.work_item import (
    get_work_item as get_work_item,
)
from pyado.raw.work_item import (
    get_work_item_api_call as get_work_item_api_call,
)
from pyado.raw.work_item import (
    get_work_item_attachment_bytes as get_work_item_attachment_bytes,
)
from pyado.raw.work_item import (
    iter_sprint_iterations as iter_sprint_iterations,
)
from pyado.raw.work_item import (
    iter_work_item_comments as iter_work_item_comments,
)
from pyado.raw.work_item import (
    iter_work_item_revisions as iter_work_item_revisions,
)
from pyado.raw.work_item import (
    list_sprint_iterations as list_sprint_iterations,
)
from pyado.raw.work_item import (
    list_work_item_comments as list_work_item_comments,
)
from pyado.raw.work_item import (
    list_work_item_revisions as list_work_item_revisions,
)
from pyado.raw.work_item import (
    patch_classification_node as patch_classification_node,
)
from pyado.raw.work_item import (
    patch_work_item as patch_work_item,
)
from pyado.raw.work_item import (
    patch_work_item_comment as patch_work_item_comment,
)
from pyado.raw.work_item import (
    post_wiql as post_wiql,
)
from pyado.raw.work_item import (
    post_work_item as post_work_item,
)
from pyado.raw.work_item import (
    post_work_item_attachment_upload as post_work_item_attachment_upload,
)
from pyado.raw.work_item import (
    post_work_item_comment as post_work_item_comment,
)
from pyado.raw.work_item import (
    post_work_items_batch as post_work_items_batch,
)
from pyado.raw.work_item import (
    restore_work_item as restore_work_item,
)
