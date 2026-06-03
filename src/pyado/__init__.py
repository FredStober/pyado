"""Python Interface for Azure DevOps."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

__all__ = [
    "ZERO_SHA",
    "ADOUrl",
    "AccessToken",
    "ApiCall",
    "BranchName",
    "BuildArtifact",
    "BuildArtifactResource",
    "BuildAttemptInfo",
    "BuildDetails",
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
    "CommitDiffPage",
    "CommitId",
    "ConnectionData",
    "ConnectionDataIdentity",
    "CustomWorkItemBase",
    "GitCommitChange",
    "GitCommitChangeItem",
    "GitCommitRef",
    "GitCommitSearchCriteria",
    "GitForkRef",
    "GitPullRequestMergeStrategy",
    "GitPushChange",
    "GitPushChangeItem",
    "GitPushChangeType",
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
    "HTMLTextFilter",
    "JobEventName",
    "JobEventPayload",
    "JobEventResult",
    "JobFeedPayload",
    "JobId",
    "JsonPatchAdd",
    "PipelineApproval",
    "PipelineApprovalStatus",
    "PipelineApprovalStep",
    "PipelineApprovalUpdateRequest",
    "PipelineDefinitionInfo",
    "PipelineInfo",
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
    "PullRequestCreated",
    "PullRequestId",
    "PullRequestIteration",
    "PullRequestIterationContext",
    "PullRequestIterationRecord",
    "PullRequestListItem",
    "PullRequestMergeFailureType",
    "PullRequestMergeStatus",
    "PullRequestReviewer",
    "PullRequestReviewerRequest",
    "PullRequestReviewerVoteRequest",
    "PullRequestSearchCriteria",
    "PullRequestStatus",
    "PullRequestStatusContext",
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
    "TimelineId",
    "TimelineRecordsUpdatePayload",
    "UserId",
    "UserProfile",
    "VariableGroupId",
    "VariableGroupInfo",
    "VariableGroupUpdateRequest",
    "VariableGroupUserInfo",
    "VariableInfo",
    "WorkItemArtifactUrlPrefix",
    "WorkItemAttachmentRef",
    "WorkItemComment",
    "WorkItemExpand",
    "WorkItemField",
    "WorkItemFieldMap",
    "WorkItemFieldName",
    "WorkItemId",
    "WorkItemInfo",
    "WorkItemLink",
    "WorkItemRef",
    "WorkItemRelation",
    "WorkItemRelationType",
    "WorkItemsBatchRequest",
    "abandon_pr",
    "add_file",
    "add_pr_reviewer",
    "add_team_iteration",
    "add_work_item_attachment",
    "add_work_item_link",
    "add_work_item_tag",
    "approve_pipeline",
    "cancel_build",
    "cancel_pipeline_run",
    "complete_pr",
    "create_branch",
    "create_classification_node",
    "create_pr",
    "create_pr_thread",
    "create_ref_update",
    "create_work_item",
    "delete_branch",
    "delete_build_tag",
    "delete_file",
    "delete_pr_label",
    "delete_pr_reviewer",
    "edit_file",
    "get_build_api_call",
    "get_build_details",
    "get_classification_node",
    "get_commit_diff_page",
    "get_connection_data",
    "get_file_content_at_branch",
    "get_file_content_at_commit",
    "get_job_api_call",
    "get_last_commit_touching_file",
    "get_log_api_call",
    "get_my_profile",
    "get_pipeline",
    "get_pipeline_run",
    "get_plan_api_call",
    "get_pr_api_call",
    "get_pr_details",
    "get_pr_iteration_changes",
    "get_pr_labels",
    "get_pr_labels_details",
    "get_pr_reviewers",
    "get_profile_api_call",
    "get_repository_api_call",
    "get_repository_commits",
    "get_repository_item_bytes",
    "get_session",
    "get_team_field_values",
    "get_test_api_call",
    "get_timeline_api_call",
    "get_variable_group_api_call",
    "get_work_item",
    "get_work_item_api_call",
    "get_work_item_tags",
    "iter_approvals",
    "iter_build_artifacts",
    "iter_build_tags",
    "iter_build_work_item_ids",
    "iter_builds",
    "iter_commit_diff",
    "iter_open_prs",
    "iter_pending_approvals",
    "iter_pipeline_definitions",
    "iter_pipeline_runs",
    "iter_pipelines",
    "iter_pr_commits",
    "iter_pr_iterations",
    "iter_pr_threads",
    "iter_pr_work_item_ids",
    "iter_projects",
    "iter_prs",
    "iter_refs",
    "iter_repository_details",
    "iter_sprint_iterations",
    "iter_timeline_records",
    "iter_variable_group_details",
    "iter_work_item_comments",
    "iter_work_item_details",
    "iter_work_items_between_builds",
    "link_pr_work_item",
    "make_commit",
    "make_ref_update",
    "patch_approvals",
    "patch_build",
    "patch_classification_node",
    "patch_pipeline_run",
    "patch_pr",
    "patch_timeline_records",
    "patch_work_item",
    "post_build",
    "post_build_tag",
    "post_job_event",
    "post_job_feed",
    "post_job_logs",
    "post_pipeline_run",
    "post_pr_label",
    "post_pr_new_thread",
    "post_pr_status",
    "post_pr_thread_comment",
    "post_pull_request",
    "post_push",
    "post_repository_refs",
    "post_wiql",
    "post_work_item",
    "post_work_item_attachment_upload",
    "post_work_item_comment",
    "post_work_items_batch",
    "push_commits",
    "put_pr_reviewer",
    "put_pr_reviewer_vote",
    "put_variable_group",
    "query_work_items",
    "remove_work_item_tag",
    "rename_file",
    "reply_to_pr_thread",
    "send_job_event",
    "send_job_feed",
    "set_pr_reviewer_vote",
    "start_build",
    "update_pr_work_item_refs",
    "update_timeline_records",
    "update_variable_group",
    "update_work_item",
]

from pyado.high import (
    CustomWorkItemBase as CustomWorkItemBase,
)
from pyado.high import (
    WorkItemFieldMap as WorkItemFieldMap,
)
from pyado.high import (
    WorkItemLink as WorkItemLink,
)
from pyado.high import (
    abandon_pr as abandon_pr,
)
from pyado.high import (
    add_file as add_file,
)
from pyado.high import (
    add_pr_reviewer as add_pr_reviewer,
)
from pyado.high import (
    add_work_item_attachment as add_work_item_attachment,
)
from pyado.high import (
    add_work_item_link as add_work_item_link,
)
from pyado.high import (
    add_work_item_tag as add_work_item_tag,
)
from pyado.high import (
    approve_pipeline as approve_pipeline,
)
from pyado.high import (
    cancel_build as cancel_build,
)
from pyado.high import (
    cancel_pipeline_run as cancel_pipeline_run,
)
from pyado.high import (
    complete_pr as complete_pr,
)
from pyado.high import (
    create_branch as create_branch,
)
from pyado.high import (
    create_pr as create_pr,
)
from pyado.high import (
    create_pr_thread as create_pr_thread,
)
from pyado.high import (
    create_ref_update as create_ref_update,
)
from pyado.high import (
    create_work_item as create_work_item,
)
from pyado.high import (
    delete_branch as delete_branch,
)
from pyado.high import (
    delete_file as delete_file,
)
from pyado.high import (
    edit_file as edit_file,
)
from pyado.high import (
    get_file_content_at_branch as get_file_content_at_branch,
)
from pyado.high import (
    get_file_content_at_commit as get_file_content_at_commit,
)
from pyado.high import (
    get_last_commit_touching_file as get_last_commit_touching_file,
)
from pyado.high import (
    get_pr_labels as get_pr_labels,
)
from pyado.high import (
    get_work_item_tags as get_work_item_tags,
)
from pyado.high import (
    iter_build_work_item_ids as iter_build_work_item_ids,
)
from pyado.high import (
    iter_commit_diff as iter_commit_diff,
)
from pyado.high import (
    iter_open_prs as iter_open_prs,
)
from pyado.high import (
    iter_pending_approvals as iter_pending_approvals,
)
from pyado.high import (
    iter_pr_work_item_ids as iter_pr_work_item_ids,
)
from pyado.high import (
    iter_work_item_details as iter_work_item_details,
)
from pyado.high import (
    link_pr_work_item as link_pr_work_item,
)
from pyado.high import (
    make_commit as make_commit,
)
from pyado.high import (
    push_commits as push_commits,
)
from pyado.high import (
    query_work_items as query_work_items,
)
from pyado.high import (
    remove_work_item_tag as remove_work_item_tag,
)
from pyado.high import (
    rename_file as rename_file,
)
from pyado.high import (
    reply_to_pr_thread as reply_to_pr_thread,
)
from pyado.high import (
    send_job_event as send_job_event,
)
from pyado.high import (
    send_job_feed as send_job_feed,
)
from pyado.high import (
    set_pr_reviewer_vote as set_pr_reviewer_vote,
)
from pyado.high import (
    start_build as start_build,
)
from pyado.high import (
    update_pr_work_item_refs as update_pr_work_item_refs,
)
from pyado.high import (
    update_timeline_records as update_timeline_records,
)
from pyado.high import (
    update_variable_group as update_variable_group,
)
from pyado.high import (
    update_work_item as update_work_item,
)
from pyado.raw import (
    ZERO_SHA as ZERO_SHA,
)
from pyado.raw import (
    AccessToken as AccessToken,
)
from pyado.raw import (
    ADOUrl as ADOUrl,
)
from pyado.raw import (
    ApiCall as ApiCall,
)
from pyado.raw import (
    BranchName as BranchName,
)
from pyado.raw import (
    BuildArtifact as BuildArtifact,
)
from pyado.raw import (
    BuildArtifactResource as BuildArtifactResource,
)
from pyado.raw import (
    BuildAttemptInfo as BuildAttemptInfo,
)
from pyado.raw import (
    BuildDetails as BuildDetails,
)
from pyado.raw import (
    BuildId as BuildId,
)
from pyado.raw import (
    BuildIssue as BuildIssue,
)
from pyado.raw import (
    BuildIssueType as BuildIssueType,
)
from pyado.raw import (
    BuildLogId as BuildLogId,
)
from pyado.raw import (
    BuildLogInfo as BuildLogInfo,
)
from pyado.raw import (
    BuildLogType as BuildLogType,
)
from pyado.raw import (
    BuildQueueRequest as BuildQueueRequest,
)
from pyado.raw import (
    BuildRecordInfo as BuildRecordInfo,
)
from pyado.raw import (
    BuildRecordResult as BuildRecordResult,
)
from pyado.raw import (
    BuildRecordState as BuildRecordState,
)
from pyado.raw import (
    BuildRecordType as BuildRecordType,
)
from pyado.raw import (
    BuildRecordTypeInfo as BuildRecordTypeInfo,
)
from pyado.raw import (
    BuildResult as BuildResult,
)
from pyado.raw import (
    BuildSearchCriteria as BuildSearchCriteria,
)
from pyado.raw import (
    BuildStatus as BuildStatus,
)
from pyado.raw import (
    ClassificationNode as ClassificationNode,
)
from pyado.raw import (
    ClassificationNodeAttributes as ClassificationNodeAttributes,
)
from pyado.raw import (
    CommitDiffPage as CommitDiffPage,
)
from pyado.raw import (
    CommitId as CommitId,
)
from pyado.raw import (
    ConnectionData as ConnectionData,
)
from pyado.raw import (
    ConnectionDataIdentity as ConnectionDataIdentity,
)
from pyado.raw import (
    GitCommitChange as GitCommitChange,
)
from pyado.raw import (
    GitCommitChangeItem as GitCommitChangeItem,
)
from pyado.raw import (
    GitCommitRef as GitCommitRef,
)
from pyado.raw import (
    GitCommitSearchCriteria as GitCommitSearchCriteria,
)
from pyado.raw import (
    GitForkRef as GitForkRef,
)
from pyado.raw import (
    GitPullRequestMergeStrategy as GitPullRequestMergeStrategy,
)
from pyado.raw import (
    GitPushChange as GitPushChange,
)
from pyado.raw import (
    GitPushChangeItem as GitPushChangeItem,
)
from pyado.raw import (
    GitPushChangeType as GitPushChangeType,
)
from pyado.raw import (
    GitPushCommit as GitPushCommit,
)
from pyado.raw import (
    GitPushContentType as GitPushContentType,
)
from pyado.raw import (
    GitPushNewContent as GitPushNewContent,
)
from pyado.raw import (
    GitPushRefUpdate as GitPushRefUpdate,
)
from pyado.raw import (
    GitPushRequest as GitPushRequest,
)
from pyado.raw import (
    GitPushResult as GitPushResult,
)
from pyado.raw import (
    GitRef as GitRef,
)
from pyado.raw import (
    GitRefFilter as GitRefFilter,
)
from pyado.raw import (
    GitRefUpdate as GitRefUpdate,
)
from pyado.raw import (
    GitStatus as GitStatus,
)
from pyado.raw import (
    HTMLTextFilter as HTMLTextFilter,
)
from pyado.raw import (
    JobEventName as JobEventName,
)
from pyado.raw import (
    JobEventPayload as JobEventPayload,
)
from pyado.raw import (
    JobEventResult as JobEventResult,
)
from pyado.raw import (
    JobFeedPayload as JobFeedPayload,
)
from pyado.raw import (
    JobId as JobId,
)
from pyado.raw import (
    JsonPatchAdd as JsonPatchAdd,
)
from pyado.raw import (
    PipelineApproval as PipelineApproval,
)
from pyado.raw import (
    PipelineApprovalStatus as PipelineApprovalStatus,
)
from pyado.raw import (
    PipelineApprovalStep as PipelineApprovalStep,
)
from pyado.raw import (
    PipelineApprovalUpdateRequest as PipelineApprovalUpdateRequest,
)
from pyado.raw import (
    PipelineDefinitionInfo as PipelineDefinitionInfo,
)
from pyado.raw import (
    PipelineInfo as PipelineInfo,
)
from pyado.raw import (
    PipelineRunInfo as PipelineRunInfo,
)
from pyado.raw import (
    PipelineRunRequest as PipelineRunRequest,
)
from pyado.raw import (
    PipelineRunResult as PipelineRunResult,
)
from pyado.raw import (
    PipelineRunState as PipelineRunState,
)
from pyado.raw import (
    PlanId as PlanId,
)
from pyado.raw import (
    PrIterationChange as PrIterationChange,
)
from pyado.raw import (
    PrIterationChangeItem as PrIterationChangeItem,
)
from pyado.raw import (
    ProjectId as ProjectId,
)
from pyado.raw import (
    ProjectInfo as ProjectInfo,
)
from pyado.raw import (
    ProjectName as ProjectName,
)
from pyado.raw import (
    ProjectState as ProjectState,
)
from pyado.raw import (
    ProjectVisibility as ProjectVisibility,
)
from pyado.raw import (
    PullRequestCompletionOptions as PullRequestCompletionOptions,
)
from pyado.raw import (
    PullRequestCreated as PullRequestCreated,
)
from pyado.raw import (
    PullRequestCreateRequest as PullRequestCreateRequest,
)
from pyado.raw import (
    PullRequestId as PullRequestId,
)
from pyado.raw import (
    PullRequestIteration as PullRequestIteration,
)
from pyado.raw import (
    PullRequestIterationContext as PullRequestIterationContext,
)
from pyado.raw import (
    PullRequestIterationRecord as PullRequestIterationRecord,
)
from pyado.raw import (
    PullRequestListItem as PullRequestListItem,
)
from pyado.raw import (
    PullRequestMergeFailureType as PullRequestMergeFailureType,
)
from pyado.raw import (
    PullRequestMergeStatus as PullRequestMergeStatus,
)
from pyado.raw import (
    PullRequestReviewer as PullRequestReviewer,
)
from pyado.raw import (
    PullRequestReviewerRequest as PullRequestReviewerRequest,
)
from pyado.raw import (
    PullRequestReviewerVoteRequest as PullRequestReviewerVoteRequest,
)
from pyado.raw import (
    PullRequestSearchCriteria as PullRequestSearchCriteria,
)
from pyado.raw import (
    PullRequestStatus as PullRequestStatus,
)
from pyado.raw import (
    PullRequestStatusContext as PullRequestStatusContext,
)
from pyado.raw import (
    PullRequestStatusRequest as PullRequestStatusRequest,
)
from pyado.raw import (
    PullRequestStatusState as PullRequestStatusState,
)
from pyado.raw import (
    PullRequestThreadCommentRequest as PullRequestThreadCommentRequest,
)
from pyado.raw import (
    PullRequestThreadCommentResponse as PullRequestThreadCommentResponse,
)
from pyado.raw import (
    PullRequestThreadCommentType as PullRequestThreadCommentType,
)
from pyado.raw import (
    PullRequestThreadContext as PullRequestThreadContext,
)
from pyado.raw import (
    PullRequestThreadHistoryContext as PullRequestThreadHistoryContext,
)
from pyado.raw import (
    PullRequestThreadPosition as PullRequestThreadPosition,
)
from pyado.raw import (
    PullRequestThreadRequest as PullRequestThreadRequest,
)
from pyado.raw import (
    PullRequestThreadResponse as PullRequestThreadResponse,
)
from pyado.raw import (
    PullRequestThreadStatus as PullRequestThreadStatus,
)
from pyado.raw import (
    PullRequestUpdateRequest as PullRequestUpdateRequest,
)
from pyado.raw import (
    PullRequestVote as PullRequestVote,
)
from pyado.raw import (
    QueueId as QueueId,
)
from pyado.raw import (
    RepositoryId as RepositoryId,
)
from pyado.raw import (
    RepositoryInfo as RepositoryInfo,
)
from pyado.raw import (
    RepositoryName as RepositoryName,
)
from pyado.raw import (
    RepositoryRef as RepositoryRef,
)
from pyado.raw import (
    SprintIterationAttributes as SprintIterationAttributes,
)
from pyado.raw import (
    SprintIterationId as SprintIterationId,
)
from pyado.raw import (
    SprintIterationInfo as SprintIterationInfo,
)
from pyado.raw import (
    SprintIterationPath as SprintIterationPath,
)
from pyado.raw import (
    SprintIterationTimeframe as SprintIterationTimeframe,
)
from pyado.raw import (
    SshUrl as SshUrl,
)
from pyado.raw import (
    TaskId as TaskId,
)
from pyado.raw import (
    TeamFieldValue as TeamFieldValue,
)
from pyado.raw import (
    TimelineId as TimelineId,
)
from pyado.raw import (
    TimelineRecordsUpdatePayload as TimelineRecordsUpdatePayload,
)
from pyado.raw import (
    UserId as UserId,
)
from pyado.raw import (
    UserProfile as UserProfile,
)
from pyado.raw import (
    VariableGroupId as VariableGroupId,
)
from pyado.raw import (
    VariableGroupInfo as VariableGroupInfo,
)
from pyado.raw import (
    VariableGroupUpdateRequest as VariableGroupUpdateRequest,
)
from pyado.raw import (
    VariableGroupUserInfo as VariableGroupUserInfo,
)
from pyado.raw import (
    VariableInfo as VariableInfo,
)
from pyado.raw import (
    WorkItemArtifactUrlPrefix as WorkItemArtifactUrlPrefix,
)
from pyado.raw import (
    WorkItemAttachmentRef as WorkItemAttachmentRef,
)
from pyado.raw import (
    WorkItemComment as WorkItemComment,
)
from pyado.raw import (
    WorkItemExpand as WorkItemExpand,
)
from pyado.raw import (
    WorkItemField as WorkItemField,
)
from pyado.raw import (
    WorkItemFieldName as WorkItemFieldName,
)
from pyado.raw import (
    WorkItemId as WorkItemId,
)
from pyado.raw import (
    WorkItemInfo as WorkItemInfo,
)
from pyado.raw import (
    WorkItemRef as WorkItemRef,
)
from pyado.raw import (
    WorkItemRelation as WorkItemRelation,
)
from pyado.raw import (
    WorkItemRelationType as WorkItemRelationType,
)
from pyado.raw import (
    WorkItemsBatchRequest as WorkItemsBatchRequest,
)
from pyado.raw import (
    add_team_iteration as add_team_iteration,
)
from pyado.raw import (
    create_classification_node as create_classification_node,
)
from pyado.raw import (
    delete_build_tag as delete_build_tag,
)
from pyado.raw import (
    delete_pr_label as delete_pr_label,
)
from pyado.raw import (
    delete_pr_reviewer as delete_pr_reviewer,
)
from pyado.raw import (
    get_build_api_call as get_build_api_call,
)
from pyado.raw import (
    get_build_details as get_build_details,
)
from pyado.raw import (
    get_classification_node as get_classification_node,
)
from pyado.raw import (
    get_commit_diff_page as get_commit_diff_page,
)
from pyado.raw import (
    get_connection_data as get_connection_data,
)
from pyado.raw import (
    get_job_api_call as get_job_api_call,
)
from pyado.raw import (
    get_log_api_call as get_log_api_call,
)
from pyado.raw import (
    get_my_profile as get_my_profile,
)
from pyado.raw import (
    get_pipeline as get_pipeline,
)
from pyado.raw import (
    get_pipeline_run as get_pipeline_run,
)
from pyado.raw import (
    get_plan_api_call as get_plan_api_call,
)
from pyado.raw import (
    get_pr_api_call as get_pr_api_call,
)
from pyado.raw import (
    get_pr_details as get_pr_details,
)
from pyado.raw import (
    get_pr_iteration_changes as get_pr_iteration_changes,
)
from pyado.raw import (
    get_pr_labels_details as get_pr_labels_details,
)
from pyado.raw import (
    get_pr_reviewers as get_pr_reviewers,
)
from pyado.raw import (
    get_profile_api_call as get_profile_api_call,
)
from pyado.raw import (
    get_repository_api_call as get_repository_api_call,
)
from pyado.raw import (
    get_repository_commits as get_repository_commits,
)
from pyado.raw import (
    get_repository_item_bytes as get_repository_item_bytes,
)
from pyado.raw import (
    get_session as get_session,
)
from pyado.raw import (
    get_team_field_values as get_team_field_values,
)
from pyado.raw import (
    get_test_api_call as get_test_api_call,
)
from pyado.raw import (
    get_timeline_api_call as get_timeline_api_call,
)
from pyado.raw import (
    get_variable_group_api_call as get_variable_group_api_call,
)
from pyado.raw import (
    get_work_item as get_work_item,
)
from pyado.raw import (
    get_work_item_api_call as get_work_item_api_call,
)
from pyado.raw import (
    iter_approvals as iter_approvals,
)
from pyado.raw import (
    iter_build_artifacts as iter_build_artifacts,
)
from pyado.raw import (
    iter_build_tags as iter_build_tags,
)
from pyado.raw import (
    iter_builds as iter_builds,
)
from pyado.raw import (
    iter_pipeline_definitions as iter_pipeline_definitions,
)
from pyado.raw import (
    iter_pipeline_runs as iter_pipeline_runs,
)
from pyado.raw import (
    iter_pipelines as iter_pipelines,
)
from pyado.raw import (
    iter_pr_commits as iter_pr_commits,
)
from pyado.raw import (
    iter_pr_iterations as iter_pr_iterations,
)
from pyado.raw import (
    iter_pr_threads as iter_pr_threads,
)
from pyado.raw import (
    iter_projects as iter_projects,
)
from pyado.raw import (
    iter_prs as iter_prs,
)
from pyado.raw import (
    iter_refs as iter_refs,
)
from pyado.raw import (
    iter_repository_details as iter_repository_details,
)
from pyado.raw import (
    iter_sprint_iterations as iter_sprint_iterations,
)
from pyado.raw import (
    iter_timeline_records as iter_timeline_records,
)
from pyado.raw import (
    iter_variable_group_details as iter_variable_group_details,
)
from pyado.raw import (
    iter_work_item_comments as iter_work_item_comments,
)
from pyado.raw import (
    iter_work_items_between_builds as iter_work_items_between_builds,
)
from pyado.raw import (
    make_ref_update as make_ref_update,
)
from pyado.raw import (
    patch_approvals as patch_approvals,
)
from pyado.raw import (
    patch_build as patch_build,
)
from pyado.raw import (
    patch_classification_node as patch_classification_node,
)
from pyado.raw import (
    patch_pipeline_run as patch_pipeline_run,
)
from pyado.raw import (
    patch_pr as patch_pr,
)
from pyado.raw import (
    patch_timeline_records as patch_timeline_records,
)
from pyado.raw import (
    patch_work_item as patch_work_item,
)
from pyado.raw import (
    post_build as post_build,
)
from pyado.raw import (
    post_build_tag as post_build_tag,
)
from pyado.raw import (
    post_job_event as post_job_event,
)
from pyado.raw import (
    post_job_feed as post_job_feed,
)
from pyado.raw import (
    post_job_logs as post_job_logs,
)
from pyado.raw import (
    post_pipeline_run as post_pipeline_run,
)
from pyado.raw import (
    post_pr_label as post_pr_label,
)
from pyado.raw import (
    post_pr_new_thread as post_pr_new_thread,
)
from pyado.raw import (
    post_pr_status as post_pr_status,
)
from pyado.raw import (
    post_pr_thread_comment as post_pr_thread_comment,
)
from pyado.raw import (
    post_pull_request as post_pull_request,
)
from pyado.raw import (
    post_push as post_push,
)
from pyado.raw import (
    post_repository_refs as post_repository_refs,
)
from pyado.raw import (
    post_wiql as post_wiql,
)
from pyado.raw import (
    post_work_item as post_work_item,
)
from pyado.raw import (
    post_work_item_attachment_upload as post_work_item_attachment_upload,
)
from pyado.raw import (
    post_work_item_comment as post_work_item_comment,
)
from pyado.raw import (
    post_work_items_batch as post_work_items_batch,
)
from pyado.raw import (
    put_pr_reviewer as put_pr_reviewer,
)
from pyado.raw import (
    put_pr_reviewer_vote as put_pr_reviewer_vote,
)
from pyado.raw import (
    put_variable_group as put_variable_group,
)
