"""Tests using real API response shapes from the smoke test fixture.

These tests validate that pyado's Pydantic models correctly parse the
full, unabridged response bodies returned by a real Azure DevOps instance.
They complement the unit tests that use minimal hand-crafted dicts.
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch
from uuid import UUID

import requests

from pyado import (
    ApiCall,
    BuildDetails,
    BuildRecordInfo,
    GitRef,
    PipelineInfo,
    PipelineRunInfo,
    ProjectInfo,
    PullRequestIterationRecord,
    PullRequestListItem,
    PullRequestThreadResponse,
    RepositoryInfo,
    SprintIterationInfo,
    VariableGroupInfo,
    WorkItemComment,
    WorkItemInfo,
    WorkItemRef,
    get_build_api_call,
    get_build_details,
    get_pipeline,
    get_pipeline_run,
    get_repository_api_call,
    get_repository_commits,
    get_work_item,
    get_work_item_api_call,
    iter_builds,
    iter_pipeline_definitions,
    iter_pipeline_runs,
    iter_pipelines,
    iter_pr_iterations,
    iter_pr_threads,
    iter_projects,
    iter_prs,
    iter_refs,
    iter_repository_details,
    iter_sprint_iterations,
    iter_timeline_records,
    iter_variable_group_details,
    iter_work_item_comments,
    iter_work_item_details,
    post_wiql,
)
from tests.conftest import _make_mock_response

# ---------------------------------------------------------------------------
# Anonymised fixtures extracted from ado_smoke_seed*.json
# Personal names, email addresses, org names, and UUIDs have all been
# replaced with placeholder values; UUIDs are randomised but consistent
# (identical originals map to identical replacements).
# ---------------------------------------------------------------------------

_AUTHOR = {
    "displayName": "Test User",
    "url": (
        "https://spsprod00000.vssps.visualstudio.com/A95c5fb98-6980-481f-bc42-8d42fa882692"
        "/_apis/Identities/94820a06-c555-463f-a9ef-41d0deea959e"
    ),
    "_links": {
        "avatar": {
            "href": (
                "https://dev.azure.com/example-org/_apis/GraphProfile/MemberAvatars"
                "/aad.OTQ4MjBhMDYtYzU1NS00NjNmLWE5ZWYtNDFkMGRlZWE5NTll"
            )
        }
    },
    "id": "94820a06-c555-463f-a9ef-41d0deea959e",
    "uniqueName": "testuser@example.com",
    "imageUrl": (
        "https://dev.azure.com/example-org/_api/_common/identityImage"
        "?id=94820a06-c555-463f-a9ef-41d0deea959e"
    ),
    "descriptor": "aad.OTQ4MjBhMDYtYzU1NS00NjNmLWE5ZWYtNDFkMGRlZWE5NTll",
}

_PROJECT = {
    "id": "daea58ba-4c73-4942-8d87-78e7d340bbcd",
    "name": "main",
    "url": "https://dev.azure.com/example-org/_apis/projects/daea58ba-4c73-4942-8d87-78e7d340bbcd",
    "state": "wellFormed",
    "revision": 20,
    "visibility": "private",
    "lastUpdateTime": "2023-01-18T16:17:39.97Z",
}

_REPO_MAIN = {
    "id": "452ec40a-3193-4a54-ae89-71105e503a67",
    "name": "main",
    "url": (
        "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
        "/_apis/git/repositories/452ec40a-3193-4a54-ae89-71105e503a67"
    ),
    "project": _PROJECT,
    "defaultBranch": "refs/heads/main",
    "size": 201,
    "remoteUrl": "https://example-org@dev.azure.com/example-org/main/_git/main",
    "sshUrl": "git@ssh.dev.azure.com:v3/example-org/main/main",
    "webUrl": "https://dev.azure.com/example-org/main/_git/main",
    "isDisabled": False,
    "isInMaintenance": False,
}

# Smoke entry [2]: GET _apis/projects
_PROJECTS_RESPONSE = {
    "count": 1,
    "value": [
        {
            "id": "daea58ba-4c73-4942-8d87-78e7d340bbcd",
            "name": "main",
            "url": (
                "https://dev.azure.com/example-org/_apis/projects"
                "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
            ),
            "collection": {
                "id": "42d6cb5c-6ed4-494b-9fc9-e3b11fcff454",
                "name": "example-org",
                "url": (
                    "https://dev.azure.com/example-org/_apis/projectCollections"
                    "/42d6cb5c-6ed4-494b-9fc9-e3b11fcff454"
                ),
                "collectionUrl": "https://dev.azure.com/example-org/",
            },
            "state": "wellFormed",
            "defaultTeam": {
                "id": "d64a3ce0-30a1-46d5-93ed-748bb80e3b0d",
                "name": "main Team",
                "url": (
                    "https://dev.azure.com/example-org/_apis/projects"
                    "/daea58ba-4c73-4942-8d87-78e7d340bbcd/teams"
                    "/d64a3ce0-30a1-46d5-93ed-748bb80e3b0d"
                ),
            },
            "revision": 20,
            "visibility": "private",
            # Note: sentinel value "0001-01-01T00:00:00" with no timezone —
            # tests that datetime parsing is lenient enough to handle it.
            "lastUpdateTime": "0001-01-01T00:00:00",
        }
    ],
}

# Smoke entry [3]: GET _apis/git/repositories
_REPOSITORIES_RESPONSE = {
    "count": 2,
    "value": [_REPO_MAIN],
}

# Smoke entry [7]: GET commits (3 commits with changeCounts)
_COMMITS_RESPONSE = {
    "count": 3,
    "value": [
        {
            "commitId": "22f23cb2b634ebeff81a61b51c45db4736c581dc",
            "author": {
                "name": "Test User",
                "email": "testuser@example.com",
                "date": "2026-06-02T12:36:54Z",
            },
            "committer": {
                "name": "Test User",
                "email": "testuser@example.com",
                "date": "2026-06-02T12:36:54Z",
            },
            "comment": "Merge pull request 12 from branch into main",
            "changeCounts": {"Add": 1, "Edit": 0, "Delete": 0},
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/git/repositories/452ec40a-3193-4a54-ae89-71105e503a67"
                "/commits/22f23cb2b634ebeff81a61b51c45db4736c581dc"
            ),
            "remoteUrl": (
                "https://dev.azure.com/example-org/main/_git/main/commit"
                "/22f23cb2b634ebeff81a61b51c45db4736c581dc"
            ),
        },
        {
            "commitId": "92003447d253defc6365da9f9b164042cf28c9e3",
            "author": {
                "name": "Test User",
                "email": "testuser@example.com",
                "date": "2026-06-02T12:36:53Z",
            },
            "committer": {
                "name": "Test User",
                "email": "testuser@example.com",
                "date": "2026-06-02T12:36:53Z",
            },
            "comment": "[smoke-test] edit file",
            "changeCounts": {"Add": 0, "Edit": 1, "Delete": 0},
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/git/repositories/452ec40a-3193-4a54-ae89-71105e503a67"
                "/commits/92003447d253defc6365da9f9b164042cf28c9e3"
            ),
            "remoteUrl": (
                "https://dev.azure.com/example-org/main/_git/main/commit"
                "/92003447d253defc6365da9f9b164042cf28c9e3"
            ),
        },
    ],
}

# Smoke entry [26]: GET build/definitions (with authoredBy, queue, _links, etc.)
_BUILD_DEFINITIONS_RESPONSE = {
    "count": 1,
    "value": [
        {
            "_links": {
                "self": {
                    "href": (
                        "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_apis/build/Definitions/1?revision=1"
                    )
                },
                "web": {
                    "href": (
                        "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_build/definition?definitionId=1"
                    )
                },
            },
            "quality": "definition",
            "authoredBy": _AUTHOR,
            "drafts": [],
            "queue": {
                "_links": {
                    "self": {
                        "href": "https://dev.azure.com/example-org/_apis/build/Queues/18"
                    }
                },
                "id": 18,
                "name": "Azure Pipelines",
                "url": "https://dev.azure.com/example-org/_apis/build/Queues/18",
                "pool": {"id": 9, "name": "Azure Pipelines", "isHosted": True},
            },
            "id": 1,
            "name": "sample-repo",
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/build/Definitions/1?revision=1"
            ),
            "uri": "vstfs:///Build/Definition/1",
            "path": "\\",
            "type": "build",
            "queueStatus": "enabled",
            "revision": 1,
            "createdDate": "2022-07-21T14:32:00.057Z",
            "project": _PROJECT,
        }
    ],
}

# Smoke entry [28]: GET build/builds (3 builds, full response)
_BUILDS_RESPONSE = {
    "count": 3,
    "value": [
        {
            "_links": {
                "self": {
                    "href": (
                        "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_apis/build/Builds/4"
                    )
                },
                "web": {
                    "href": (
                        "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_build/results?buildId=4"
                    )
                },
            },
            "properties": {},
            "tags": [],
            "validationResults": [],
            "plans": [{"planId": "ae711399-e2b2-448b-9b1b-cf726a1eccda"}],
            "triggerInfo": {},
            "id": 4,
            "buildNumber": "20260602.3",
            "status": "completed",
            "result": "succeeded",
            "queueTime": "2026-06-02T12:36:49.6551905Z",
            "startTime": "2026-06-02T12:36:58.4032304Z",
            "finishTime": "2026-06-02T12:37:41.9070572Z",
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/build/Builds/4"
            ),
            "definition": {
                "drafts": [],
                "id": 1,
                "name": "sample-repo",
                "url": (
                    "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                    "/_apis/build/Definitions/1?revision=1"
                ),
                "uri": "vstfs:///Build/Definition/1",
                "path": "\\",
                "type": "build",
                "queueStatus": "enabled",
                "revision": 1,
                "project": _PROJECT,
            },
            "buildNumberRevision": 3,
            "project": _PROJECT,
            "uri": "vstfs:///Build/Build/4",
            "sourceBranch": "refs/heads/main",
            "sourceVersion": "793c58c9db362a9af594627883270b76c27526ad",
            "queue": {
                "id": 18,
                "name": "Azure Pipelines",
                "pool": {"id": 9, "name": "Azure Pipelines", "isHosted": True},
            },
            "priority": "normal",
            "reason": "manual",
            "requestedFor": _AUTHOR,
            "requestedBy": _AUTHOR,
            "lastChangedDate": "2026-06-02T12:37:42.37Z",
            "lastChangedBy": _AUTHOR,
            "orchestrationPlan": {"planId": "ae711399-e2b2-448b-9b1b-cf726a1eccda"},
            "logs": {
                "id": 0,
                "type": "Container",
                "url": (
                    "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                    "/_apis/build/builds/4/logs"
                ),
            },
            "repository": {
                "id": "6a5ccc2c-be99-454a-b0d2-6ee6fa928906",
                "type": "TfsGit",
                "name": "sample-repo",
                "url": "https://dev.azure.com/example-org/main/_git/sample-repo",
                "clean": None,
                "checkoutSubmodules": False,
            },
            "retainedByRelease": False,
            "triggeredByBuild": None,
            "appendCommitMessageToRunName": True,
        }
    ],
}

# Smoke entry [33]: GET build/builds/4/timeline
# Contains Stage, Phase, Job and Task record types; some tasks have null task field.
_TIMELINE_RESPONSE = {
    "records": [
        {
            "previousAttempts": [],
            "id": "5f811cb9-2964-4f8b-afac-aa5090e5e945",
            "parentId": "34a9af41-25ec-4845-aaa4-857e8101e89a",
            "type": "Job",
            "name": "Job",
            "refName": "__default",
            "startTime": "2026-06-02T12:37:12.2966667Z",
            "finishTime": "2026-06-02T12:37:34.6133333Z",
            "currentOperation": None,
            "percentComplete": None,
            "state": "completed",
            "result": "succeeded",
            "resultCode": None,
            "changeId": 17,
            "lastModified": "0001-01-01T00:00:00",
            "workerName": "Azure Pipelines 1",
            "queueId": 18,
            "order": 1,
            "details": None,
            "errorCount": 0,
            "warningCount": 0,
            "url": None,
            "log": {
                "id": 10,
                "type": "Container",
                "url": (
                    "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                    "/_apis/build/builds/4/logs/10"
                ),
            },
            "task": None,
            "attempt": 1,
            "identifier": "Job.__default",
        },
        {
            "previousAttempts": [],
            "id": "a70ce1b5-1978-4ec0-895c-fa4f2dcaabd5",
            "parentId": None,
            "type": "Stage",
            "name": "__default",
            "refName": "__default",
            "startTime": "2026-06-02T12:37:12.2966667Z",
            "finishTime": "2026-06-02T12:37:41.95Z",
            "currentOperation": None,
            "percentComplete": None,
            "state": "completed",
            "result": "succeeded",
            "resultCode": None,
            "changeId": 6,
            "lastModified": "0001-01-01T00:00:00",
            "workerName": None,
            "order": 1,
            "details": None,
            "errorCount": 0,
            "warningCount": 0,
            "url": None,
            "log": None,
            "task": None,
            "attempt": 1,
            "identifier": "__default",
        },
        {
            "previousAttempts": [],
            "id": "82bde024-f7ac-4e22-86e0-f45856eaa301",
            "parentId": "5f811cb9-2964-4f8b-afac-aa5090e5e945",
            "type": "Task",
            "name": "Checkout sample-repo@main to s",
            "refName": "__system_1",
            "startTime": "2026-06-02T12:37:12.98Z",
            "finishTime": "2026-06-02T12:37:14.01Z",
            "currentOperation": None,
            "percentComplete": None,
            "state": "completed",
            "result": "succeeded",
            "resultCode": None,
            "changeId": 11,
            "lastModified": "0001-01-01T00:00:00",
            "workerName": "Azure Pipelines 1",
            "order": 2,
            "details": None,
            "errorCount": 0,
            "warningCount": 0,
            "url": None,
            "log": {
                "id": 5,
                "type": "Container",
                "url": (
                    "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                    "/_apis/build/builds/4/logs/5"
                ),
            },
            "task": {
                "id": "a9f559fc-f0b3-4868-81b5-577d00e266d0",
                "name": "Checkout",
                "version": "1.0.0",
            },
            "attempt": 1,
            "identifier": None,
        },
        {
            "previousAttempts": [],
            "id": "7576714a-0605-4c82-9271-22dc57708107",
            "parentId": "5f811cb9-2964-4f8b-afac-aa5090e5e945",
            "type": "Task",
            "name": "Finalize Job",
            "refName": "JobExtension_Final",
            "startTime": "2026-06-02T12:37:34.5833333Z",
            "finishTime": "2026-06-02T12:37:34.61Z",
            "currentOperation": None,
            "percentComplete": 100,
            "state": "completed",
            "result": "succeeded",
            "resultCode": None,
            "changeId": 13,
            "lastModified": "0001-01-01T00:00:00",
            "workerName": "Azure Pipelines 1",
            "order": 6,
            "details": None,
            "errorCount": 0,
            "warningCount": 0,
            "url": None,
            "log": {
                "id": 9,
                "type": "Container",
                "url": (
                    "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                    "/_apis/build/builds/4/logs/9"
                ),
            },
            "task": None,
            "attempt": 1,
            "identifier": None,
        },
    ],
    "lastChangedBy": "d1f6f86c-029a-4245-bb91-433a6aa79987",
    "lastChangedOn": "2026-06-02T12:37:42.35Z",
    "id": "ae711399-e2b2-448b-9b1b-cf726a1eccda",
    "changeId": 17,
    "url": (
        "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
        "/_apis/build/builds/4/Timeline/ae711399-e2b2-448b-9b1b-cf726a1eccda"
    ),
}

# Smoke entry [41]: GET pullRequests/4/threads
# Contains a system-generated comment with commentType="system" and
# a properties dict with ADO-style {$type, $value} entries.
_PR_THREADS_RESPONSE = {
    "count": 1,
    "value": [
        {
            "pullRequestThreadContext": None,
            "id": 7,
            "publishedDate": "2026-06-02T11:56:05.68Z",
            "lastUpdatedDate": "2026-06-02T11:56:05.68Z",
            "comments": [
                {
                    "id": 1,
                    "parentCommentId": 0,
                    "author": _AUTHOR,
                    "content": "Test User updated the pull request status to Completed",
                    "publishedDate": "2026-06-02T11:56:05.68Z",
                    "lastUpdatedDate": "2026-06-02T11:56:05.68Z",
                    "lastContentUpdatedDate": "2026-06-02T11:56:05.68Z",
                    "commentType": "system",
                    "usersLiked": [],
                    "_links": {
                        "self": {
                            "href": (
                                "https://dev.azure.com/example-org/_apis/git/repositories"
                                "/6a5ccc2c-be99-454a-b0d2-6ee6fa928906"
                                "/pullRequests/4/threads/7/comments/1"
                            )
                        }
                    },
                }
            ],
            "threadContext": None,
            "properties": {
                "CodeReviewThreadType": {
                    "$type": "System.String",
                    "$value": "StatusUpdate",
                },
                "CodeReviewStatus": {
                    "$type": "System.String",
                    "$value": "Completed",
                },
                "BypassPolicy": {"$type": "System.String", "$value": "False"},
            },
            "identities": {"1": _AUTHOR},
            "isDeleted": False,
            "_links": {
                "self": {
                    "href": (
                        "https://dev.azure.com/example-org/_apis/git/repositories"
                        "/6a5ccc2c-be99-454a-b0d2-6ee6fa928906/pullRequests/4/threads/7"
                    )
                }
            },
        }
    ],
}

# Smoke entry [42]: GET pullRequests/4/iterations
# Contains commonRefCommit (not present in hand-crafted test data).
_PR_ITERATIONS_RESPONSE = {
    "count": 1,
    "value": [
        {
            "id": 1,
            "description": "Update azure-pipelines.yml for Azure Pipelines",
            "author": _AUTHOR,
            "createdDate": "2026-06-02T11:56:00.6300795Z",
            "updatedDate": "2026-06-02T11:56:00.6300795Z",
            "sourceRefCommit": {"commitId": "484abe3d12855809c2e1169557e0505fa179cedb"},
            "targetRefCommit": {"commitId": "b4a8a9c1a41cf98c882adef818f3d00e0eb76587"},
            "commonRefCommit": {"commitId": "b4a8a9c1a41cf98c882adef818f3d00e0eb76587"},
            "hasMoreCommits": False,
            "reason": "push",
        }
    ],
}

# Smoke entry [45]: POST wit/wiql (13 work item refs)
_WIQL_RESPONSE = {
    "queryType": "flat",
    "queryResultType": "workItem",
    "asOf": "2026-06-02T12:47:24.313Z",
    "columns": [
        {
            "referenceName": "System.Id",
            "name": "ID",
            "url": "https://dev.azure.com/example-org/_apis/wit/fields/System.Id",
        }
    ],
    "sortColumns": [
        {
            "field": {
                "referenceName": "System.ChangedDate",
                "name": "Changed Date",
                "url": (
                    "https://dev.azure.com/example-org/_apis/wit/fields/System.ChangedDate"
                ),
            },
            "descending": True,
        }
    ],
    "workItems": [
        {
            "id": idx,
            "url": (
                f"https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                f"/_apis/wit/workItems/{idx}"
            ),
        }
        for idx in [105, 104, 103, 102, 101, 100, 99, 98, 97, 96, 95, 94, 93]
    ],
}

# Smoke entry [47]: POST workitemsbatch (5 work items with nested AssignedTo field)
_WORK_ITEMS_BATCH_RESPONSE = {
    "count": 5,
    "value": [
        {
            "id": 101,
            "rev": 10,
            "fields": {
                "System.Id": 101,
                "System.AssignedTo": _AUTHOR,
                "System.Title": "[smoke-test] work item 101",
                "System.Description": "**Smoke test** description",
            },
            "multilineFieldsFormat": {},
            "url": "https://dev.azure.com/example-org/_apis/wit/workItems/101",
        },
        {
            "id": 102,
            "rev": 10,
            "fields": {
                "System.Id": 102,
                "System.AssignedTo": _AUTHOR,
                "System.Title": "[smoke-test] work item 102",
                "System.Description": "**Smoke test** description",
            },
            "multilineFieldsFormat": {},
            "url": "https://dev.azure.com/example-org/_apis/wit/workItems/102",
        },
    ],
}

# Smoke entry [50]: GET wit/workitems/97
# (full work item with relations + multilineFieldsFormat)
_WORK_ITEM_SINGLE_RESPONSE = {
    "id": 97,
    "rev": 4,
    "fields": {
        "System.AreaPath": "main",
        "System.TeamProject": "main",
        "System.IterationPath": "main",
        "System.WorkItemType": "Task",
        "System.State": "Proposed",
        "System.Reason": "New",
        "System.AssignedTo": _AUTHOR,
        "System.CreatedDate": "2026-06-02T04:13:13.043Z",
        "System.CreatedBy": _AUTHOR,
        "System.ChangedDate": "2026-06-02T04:13:13.433Z",
        "System.ChangedBy": _AUTHOR,
        "System.CommentCount": 1,
        "System.Title": "[smoke-test] work-item-title (updated)",
        "Microsoft.VSTS.Common.Priority": 2,
        "System.Description": "Auto-created by smoke_test.py",
    },
    "multilineFieldsFormat": {"System.Description": "html"},
    "relations": [
        {
            "rel": "AttachedFile",
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/wit/attachments/bcf74d7a-5ada-4121-afd2-b7a48d9fe5b9"
            ),
            "attributes": {
                "authorizedDate": "2026-06-02T04:13:13.433Z",
                "id": 31732840,
                "resourceSize": 35,
                "comment": "smoke_test.txt",
                "name": "smoke_test.txt",
            },
        }
    ],
    "_links": {
        "self": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/wit/workItems/97"
            )
        }
    },
    "url": (
        "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
        "/_apis/wit/workItems/97"
    ),
}

# Smoke entry [52]: GET wit/workitems/97/comments
# Contains full comment with mentions, format and renderedText fields.
_WORK_ITEM_COMMENTS_RESPONSE = {
    "totalCount": 1,
    "count": 1,
    "comments": [
        {
            "mentions": [],
            "workItemId": 97,
            "id": 24884249,
            "version": 1,
            "text": "<p>pyado smoke test comment</p>",
            "createdBy": _AUTHOR,
            "createdDate": "2026-06-02T04:13:13.227Z",
            "modifiedBy": _AUTHOR,
            "modifiedDate": "2026-06-02T04:13:13.227Z",
            "format": "html",
            "renderedText": "",
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/wit/workItems/97/comments/24884249"
            ),
        }
    ],
}

# Smoke entry [53]: GET work/teamsettings/iterations
# path field contains backslash separators.
_SPRINT_ITERATIONS_RESPONSE = {
    "count": 1,
    "value": [
        {
            "id": "9c9cea0c-2ca1-4789-a091-250e8fe46024",
            "name": "Iteration 0",
            "path": "main\\Iteration 0",
            "attributes": {
                "startDate": "2023-01-01T00:00:00Z",
                "finishDate": "2023-02-25T00:00:00Z",
                "timeFrame": "current",
            },
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/d64a3ce0-30a1-46d5-93ed-748bb80e3b0d/_apis/work/teamsettings"
                "/iterations/9c9cea0c-2ca1-4789-a091-250e8fe46024"
            ),
        }
    ],
}

# Smoke entry [32]: GET build/builds/14 (single build; extra _links entries)
# lastChangedBy is a system identity (Microsoft.VisualStudio.Services.TFS).
_SINGLE_BUILD_RESPONSE = {
    "_links": {
        "self": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/build/Builds/14"
            )
        },
        "web": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_build/results?buildId=14"
            )
        },
        "sourceVersionDisplayUri": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/build/builds/14/sources"
            )
        },
        "timeline": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/build/builds/14/Timeline"
            )
        },
        "badge": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/build/status/1"
            )
        },
    },
    "properties": {},
    "tags": [],
    "validationResults": [],
    "plans": [{"planId": "9893588c-860a-4da1-b5cd-b9413b8d0e76"}],
    "triggerInfo": {},
    "id": 14,
    "buildNumber": "20260602.13",
    "status": "completed",
    "result": "succeeded",
    "queueTime": "2026-06-02T14:40:57.7141572Z",
    "startTime": "2026-06-02T14:42:26.7479554Z",
    "finishTime": "2026-06-02T14:42:57.8337515Z",
    "url": (
        "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
        "/_apis/build/Builds/14"
    ),
    "definition": {
        "drafts": [],
        "id": 1,
        "name": "sample-repo",
        "url": (
            "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
            "/_apis/build/Definitions/1?revision=1"
        ),
        "uri": "vstfs:///Build/Definition/1",
        "path": "\\",
        "type": "build",
        "queueStatus": "enabled",
        "revision": 1,
        "project": _PROJECT,
    },
    "buildNumberRevision": 13,
    "project": _PROJECT,
    "uri": "vstfs:///Build/Build/14",
    "sourceBranch": "refs/heads/main",
    "sourceVersion": "793c58c9db362a9af594627883270b76c27526ad",
    "queue": {
        "id": 18,
        "name": "Azure Pipelines",
        "pool": {"id": 9, "name": "Azure Pipelines", "isHosted": True},
    },
    "priority": "normal",
    "reason": "manual",
    "requestedFor": _AUTHOR,
    "requestedBy": _AUTHOR,
    "lastChangedDate": "2026-06-02T14:42:58.12Z",
    "lastChangedBy": {
        "displayName": "Microsoft.VisualStudio.Services.TFS",
        "url": (
            "https://spsprod00000.vssps.visualstudio.com"
            "/A95c5fb98-6980-481f-bc42-8d42fa882692"
            "/_apis/Identities/d1f6f86c-029a-4245-bb91-433a6aa79987"
        ),
        "_links": {
            "avatar": {
                "href": (
                    "https://dev.azure.com/example-org/_apis/GraphProfile/MemberAvatars"
                    "/s2s.ZDFmNmY4NmMtMDI5YS00MjQ1LWJiOTEtNDMzYTZhYTc5OTg3"
                )
            }
        },
        "id": "d1f6f86c-029a-4245-bb91-433a6aa79987",
        "uniqueName": (
            "d1f6f86c-029a-4245-bb91-433a6aa79987@87f26aee-175f-4cd2-bb9d-58e4f543bbcf"
        ),
        "imageUrl": (
            "https://dev.azure.com/example-org/_apis/GraphProfile/MemberAvatars"
            "/s2s.ZDFmNmY4NmMtMDI5YS00MjQ1LWJiOTEtNDMzYTZhYTc5OTg3"
        ),
        "descriptor": ("s2s.ZDFmNmY4NmMtMDI5YS00MjQ1LWJiOTEtNDMzYTZhYTc5OTg3"),
    },
    "orchestrationPlan": {"planId": "9893588c-860a-4da1-b5cd-b9413b8d0e76"},
    "logs": {
        "id": 0,
        "type": "Container",
        "url": (
            "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
            "/_apis/build/builds/14/logs"
        ),
    },
    "repository": {
        "id": "6a5ccc2c-be99-454a-b0d2-6ee6fa928906",
        "type": "TfsGit",
        "name": "sample-repo",
        "url": "https://dev.azure.com/example-org/main/_git/sample-repo",
        "clean": None,
        "checkoutSubmodules": False,
    },
    "retainedByRelease": False,
    "triggeredByBuild": None,
    "appendCommitMessageToRunName": True,
}

# Smoke entry [44]: GET distributedtask/variablegroups
# variableGroupProjectReferences is null (must not error).
_VARIABLE_GROUPS_RESPONSE = {
    "count": 1,
    "value": [
        {
            "variables": {"test": {"value": "test"}},
            "id": 1,
            "type": "Vsts",
            "name": "smoke-test-group",
            "description": "",
            "createdBy": {
                "displayName": "Test User",
                "id": "94820a06-c555-463f-a9ef-41d0deea959e",
                "uniqueName": "testuser@example.com",
            },
            "createdOn": "2026-06-02T11:58:28.7633333Z",
            "modifiedBy": {
                "displayName": "Test User",
                "id": "94820a06-c555-463f-a9ef-41d0deea959e",
                "uniqueName": "testuser@example.com",
            },
            "modifiedOn": "2026-06-02T12:57:02.47Z",
            "isShared": False,
            "variableGroupProjectReferences": None,
        }
    ],
}

# Smoke entry [1]: GET git/pullrequests
# PR is in "completed" status with closedDate and completionOptions.
_PRS_RESPONSE = {
    "value": [
        {
            "repository": {
                "id": "6a5ccc2c-be99-454a-b0d2-6ee6fa928906",
                "name": "sample-repo",
                "url": (
                    "https://dev.azure.com/example-org"
                    "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                    "/_apis/git/repositories"
                    "/6a5ccc2c-be99-454a-b0d2-6ee6fa928906"
                ),
                "project": {
                    "id": "daea58ba-4c73-4942-8d87-78e7d340bbcd",
                    "name": "main",
                    "state": "unchanged",
                    "visibility": "unchanged",
                    "lastUpdateTime": "0001-01-01T00:00:00",
                },
            },
            "pullRequestId": 4,
            "codeReviewId": 4,
            "status": "completed",
            "createdBy": _AUTHOR,
            "creationDate": "2026-06-02T11:56:00.6261407Z",
            "closedDate": "2026-06-02T11:56:05.4597475Z",
            "title": "test",
            "sourceRefName": "refs/heads/azure-pipelines",
            "targetRefName": "refs/heads/main",
            "mergeStatus": "succeeded",
            "isDraft": False,
            "mergeId": "600027e8-bc90-46ec-ae80-dbd593fd7234",
            "lastMergeSourceCommit": {
                "commitId": "484abe3d12855809c2e1169557e0505fa179cedb",
                "url": (
                    "https://dev.azure.com/example-org"
                    "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                    "/_apis/git/repositories"
                    "/6a5ccc2c-be99-454a-b0d2-6ee6fa928906"
                    "/commits/484abe3d12855809c2e1169557e0505fa179cedb"
                ),
            },
            "lastMergeTargetCommit": {
                "commitId": "b4a8a9c1a41cf98c882adef818f3d00e0eb76587",
                "url": (
                    "https://dev.azure.com/example-org"
                    "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                    "/_apis/git/repositories"
                    "/6a5ccc2c-be99-454a-b0d2-6ee6fa928906"
                    "/commits/b4a8a9c1a41cf98c882adef818f3d00e0eb76587"
                ),
            },
            "lastMergeCommit": {
                "commitId": "793c58c9db362a9af594627883270b76c27526ad",
                "url": (
                    "https://dev.azure.com/example-org"
                    "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                    "/_apis/git/repositories"
                    "/6a5ccc2c-be99-454a-b0d2-6ee6fa928906"
                    "/commits/793c58c9db362a9af594627883270b76c27526ad"
                ),
            },
            "reviewers": [],
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/git/repositories/6a5ccc2c-be99-454a-b0d2-6ee6fa928906"
                "/pullRequests/4"
            ),
            "completionOptions": {
                "mergeCommitMessage": "Merged PR 4: test",
                "deleteSourceBranch": True,
                "mergeStrategy": "noFastForward",
                "transitionWorkItems": True,
                "autoCompleteIgnoreConfigIds": [],
            },
            "supportsIterations": True,
        }
    ],
    "count": 1,
}

# Smoke entry [4]: GET git/repositories/{id}/refs
# Includes a branch ref (user creator) and a PR merge ref (system creator).
_REFS_RESPONSE = {
    "value": [
        {
            "name": "refs/heads/main",
            "objectId": "a552f5aed0bc38f8c5fb75f3b4c615cc8889f748",
            "creator": _AUTHOR,
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/git/repositories/452ec40a-3193-4a54-ae89-71105e503a67"
                "/refs?filter=heads%2Fmain"
            ),
        },
        {
            "name": "refs/pull/2/merge",
            "objectId": "2e6ade2719c5756dc50c68c16e01519923b744c9",
            "creator": {
                "displayName": "Microsoft.VisualStudio.Services.TFS",
                "url": (
                    "https://spsprod00000.vssps.visualstudio.com"
                    "/A95c5fb98-6980-481f-bc42-8d42fa882692"
                    "/_apis/Identities/d1f6f86c-029a-4245-bb91-433a6aa79987"
                ),
                "_links": {
                    "avatar": {
                        "href": (
                            "https://dev.azure.com/example-org/_apis/GraphProfile"
                            "/MemberAvatars/s2s.MDAwMDAwMDItMDAwMC04ODg4LTgwMDA"
                        )
                    }
                },
                "id": "d1f6f86c-029a-4245-bb91-433a6aa79987",
                "uniqueName": (
                    "d1f6f86c-029a-4245-bb91-433a6aa79987"
                    "@87f26aee-175f-4cd2-bb9d-58e4f543bbcf"
                ),
                "imageUrl": (
                    "https://dev.azure.com/example-org/_api/_common/identityImage"
                    "?id=d1f6f86c-029a-4245-bb91-433a6aa79987"
                ),
                "descriptor": "s2s.MDAwMDAwMDItMDAwMC04ODg4LTgwMDA",
            },
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/git/repositories/452ec40a-3193-4a54-ae89-71105e503a67"
                "/refs?filter=pull%2F2%2Fmerge"
            ),
        },
    ],
    "count": 2,
}

# Smoke entry [65]: GET pipelines (list)
_PIPELINES_RESPONSE = {
    "count": 1,
    "value": [
        {
            "_links": {
                "self": {
                    "href": (
                        "https://dev.azure.com/example-org"
                        "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_apis/pipelines/1?revision=1"
                    )
                },
                "web": {
                    "href": (
                        "https://dev.azure.com/example-org"
                        "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_build/definition?definitionId=1"
                    )
                },
            },
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/pipelines/1?revision=1"
            ),
            "id": 1,
            "revision": 1,
            "name": "sample-repo",
            "folder": "\\",
        }
    ],
}

# Smoke entry [67]: GET pipelines/1 (single pipeline with configuration field)
_SINGLE_PIPELINE_RESPONSE = {
    "_links": {
        "self": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/pipelines/1?revision=1"
            )
        },
        "web": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_build/definition?definitionId=1"
            )
        },
    },
    "configuration": {
        "path": "azure-pipelines.yml",
        "repository": {
            "id": "6a5ccc2c-be99-454a-b0d2-6ee6fa928906",
            "type": "azureReposGit",
        },
        "type": "yaml",
    },
    "url": (
        "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
        "/_apis/pipelines/1?revision=1"
    ),
    "id": 1,
    "revision": 1,
    "name": "sample-repo",
    "folder": "\\",
}

# Smoke entry [69]: GET pipelines/1/runs (14 runs; first two shown)
_PIPELINE_RUNS_RESPONSE = {
    "count": 2,
    "value": [
        {
            "_links": {
                "self": {
                    "href": (
                        "https://dev.azure.com/example-org"
                        "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_apis/pipelines/1/runs/14"
                    )
                },
                "web": {
                    "href": (
                        "https://dev.azure.com/example-org"
                        "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_build/results?buildId=14"
                    )
                },
                "pipeline.web": {
                    "href": (
                        "https://dev.azure.com/example-org"
                        "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_build/definition?definitionId=1"
                    )
                },
                "pipeline": {
                    "href": (
                        "https://dev.azure.com/example-org"
                        "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_apis/pipelines/1?revision=1"
                    )
                },
            },
            "templateParameters": {},
            "pipeline": {
                "url": (
                    "https://dev.azure.com/example-org"
                    "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                    "/_apis/pipelines/1?revision=1"
                ),
                "id": 1,
                "revision": 1,
                "name": "sample-repo",
                "folder": "\\",
            },
            "state": "completed",
            "result": "succeeded",
            "createdDate": "2026-06-02T14:40:57.7141572Z",
            "finishedDate": "2026-06-02T14:42:57.8337515Z",
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/pipelines/1/runs/14"
            ),
            "id": 14,
            "name": "20260602.13",
        },
        {
            "_links": {
                "self": {
                    "href": (
                        "https://dev.azure.com/example-org"
                        "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_apis/pipelines/1/runs/13"
                    )
                },
                "web": {
                    "href": (
                        "https://dev.azure.com/example-org"
                        "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_build/results?buildId=13"
                    )
                },
                "pipeline.web": {
                    "href": (
                        "https://dev.azure.com/example-org"
                        "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_build/definition?definitionId=1"
                    )
                },
                "pipeline": {
                    "href": (
                        "https://dev.azure.com/example-org"
                        "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                        "/_apis/pipelines/1?revision=1"
                    )
                },
            },
            "templateParameters": {},
            "pipeline": {
                "url": (
                    "https://dev.azure.com/example-org"
                    "/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                    "/_apis/pipelines/1?revision=1"
                ),
                "id": 1,
                "revision": 1,
                "name": "sample-repo",
                "folder": "\\",
            },
            "state": "completed",
            "result": "failed",
            "createdDate": "2026-06-02T14:38:00.0000000Z",
            "finishedDate": "2026-06-02T14:39:30.0000000Z",
            "url": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/pipelines/1/runs/13"
            ),
            "id": 13,
            "name": "20260602.12",
        },
    ],
}

# Smoke entry [71]: GET pipelines/1/runs/14 (single run with yamlDetails extra field)
_SINGLE_PIPELINE_RUN_RESPONSE = {
    "yamlDetails": {
        "rootYamlFile": {
            "ref": "refs/heads/main",
            "yamlFile": "azure-pipelines.yml",
            "repoAlias": "self",
        },
        "expandedYamlUrl": (
            "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
            "/_apis/build/builds/14/logs/1"
        ),
    },
    "_links": {
        "self": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/pipelines/1/runs/14"
            )
        },
        "web": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_build/results?buildId=14"
            )
        },
        "pipeline.web": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_build/definition?definitionId=1"
            )
        },
        "pipeline": {
            "href": (
                "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
                "/_apis/pipelines/1?revision=1"
            )
        },
    },
    "templateParameters": {},
    "pipeline": {
        "url": (
            "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
            "/_apis/pipelines/1?revision=1"
        ),
        "id": 1,
        "revision": 1,
        "name": "sample-repo",
        "folder": "\\",
    },
    "state": "completed",
    "result": "succeeded",
    "createdDate": "2026-06-02T14:40:57.7141572Z",
    "finishedDate": "2026-06-02T14:42:57.8337515Z",
    "url": (
        "https://dev.azure.com/example-org/daea58ba-4c73-4942-8d87-78e7d340bbcd"
        "/_apis/pipelines/1/runs/14"
    ),
    "id": 14,
    "name": "20260602.13",
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSmokeIterProjects:
    """iter_projects parses real project response shapes."""

    @staticmethod
    def test_parses_project_with_collection_and_default_team(
        api_call: ApiCall,
    ) -> None:
        """Parses a project response including collection and defaultTeam fields."""
        mock_response = _make_mock_response(_PROJECTS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_projects(api_call))
        assert len(result) == 1
        assert isinstance(result[0], ProjectInfo)
        assert result[0].name == "main"
        assert result[0].state == "wellFormed"
        assert result[0].revision == 20

    @staticmethod
    def test_parses_sentinel_last_update_time(api_call: ApiCall) -> None:
        """Parses lastUpdateTime '0001-01-01T00:00:00' (ADO sentinel with no tz)."""
        mock_response = _make_mock_response(_PROJECTS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_projects(api_call))
        # The sentinel date-time must parse without error; year is 1.
        assert result[0].last_update_time.year == 1


class TestSmokeIterRepositoryDetails:
    """iter_repository_details parses real repository response shapes."""

    @staticmethod
    def test_parses_two_repositories(api_call: ApiCall) -> None:
        """Parses a response containing two fully-populated repository objects."""
        mock_response = _make_mock_response(_REPOSITORIES_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_repository_details(api_call))
        assert len(result) == 1  # fixture only has one entry
        assert isinstance(result[0], RepositoryInfo)
        assert result[0].name == "main"
        assert result[0].default_branch == "refs/heads/main"
        assert result[0].size == 201

    @staticmethod
    def test_project_fields_parsed_correctly(api_call: ApiCall) -> None:
        """Nested project fields are accessible on the repository object."""
        mock_response = _make_mock_response(_REPOSITORIES_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_repository_details(api_call))
        repo = result[0]
        assert repo.project.name == "main"
        assert repo.project.state == "wellFormed"


class TestSmokeGetRepositoryCommits:
    """get_repository_commits parses real commit response shapes."""

    @staticmethod
    def test_parses_three_commits(api_call: ApiCall) -> None:
        """Parses a commit list response with changeCounts and full author info."""
        mock_response = _make_mock_response(_COMMITS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_repository_commits(api_call)
        assert len(result) == 2  # fixture has 2 commits
        assert result[0].commit_id == "22f23cb2b634ebeff81a61b51c45db4736c581dc"
        assert result[1].commit_id == "92003447d253defc6365da9f9b164042cf28c9e3"

    @staticmethod
    def test_commit_comment_parsed(api_call: ApiCall) -> None:
        """The commit comment field is populated from the real response."""
        mock_response = _make_mock_response(_COMMITS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_repository_commits(api_call)
        assert result[0].comment is not None
        assert "merge pull request" in result[0].comment.lower()


class TestSmokeIterPipelineDefinitions:
    """iter_pipeline_definitions parses real build definition response shapes."""

    @staticmethod
    def test_parses_definition_with_extra_fields(api_call: ApiCall) -> None:
        """Parses definition with authoredBy, queue, _links and uri extra fields."""
        mock_response = _make_mock_response(_BUILD_DEFINITIONS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pipeline_definitions(api_call))
        assert len(result) == 1
        assert result[0].id == 1
        assert result[0].name == "sample-repo"
        assert result[0].queue_status == "enabled"
        assert result[0].path == "\\"


class TestSmokeIterBuilds:
    """iter_builds parses real build response shapes."""

    @staticmethod
    def test_parses_full_build_response(api_call: ApiCall) -> None:
        """Parses build with plans, tags, validationResults and triggerInfo fields."""
        mock_response = _make_mock_response(_BUILDS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_builds(api_call))
        assert len(result) == 1
        assert isinstance(result[0], BuildDetails)
        assert result[0].id == 4
        assert result[0].build_number == "20260602.3"
        assert result[0].status == "completed"
        assert result[0].result == "succeeded"

    @staticmethod
    def test_requested_by_parsed(api_call: ApiCall) -> None:
        """RequestedBy nested object is accessible on the build."""
        mock_response = _make_mock_response(_BUILDS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_builds(api_call))
        assert result[0].requested_by.display_name == "Test User"

    @staticmethod
    def test_definition_nested_object_parsed(api_call: ApiCall) -> None:
        """Definition nested object is accessible on the build."""
        mock_response = _make_mock_response(_BUILDS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_builds(api_call))
        assert result[0].definition.id == 1
        assert result[0].definition.name == "sample-repo"


class TestSmokeIterTimelineRecords:
    """iter_timeline_records parses real timeline containing mixed record types."""

    @staticmethod
    def test_parses_mixed_record_types(api_call: ApiCall) -> None:
        """Parses a timeline with Stage, Job, and Task record types."""
        mock_response = _make_mock_response(_TIMELINE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_timeline_records(api_call))
        types = {record.type_name for record in result}
        assert "Stage" in types
        assert "Job" in types
        assert "Task" in types

    @staticmethod
    def test_task_record_with_task_field_parsed(api_call: ApiCall) -> None:
        """Task record with a populated task field (name, id, version) parses ok."""
        mock_response = _make_mock_response(_TIMELINE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_timeline_records(api_call))
        task_records = [r for r in result if r.task is not None]
        assert len(task_records) == 1
        task = task_records[0].task
        assert task is not None
        assert task.name == "Checkout"

    @staticmethod
    def test_record_with_null_task_field_parses(api_call: ApiCall) -> None:
        """Records where task is null are parsed without error."""
        mock_response = _make_mock_response(_TIMELINE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_timeline_records(api_call))
        null_task_records = [r for r in result if r.task is None]
        assert len(null_task_records) == 3  # Job, Stage, and Finalize Job

    @staticmethod
    def test_percent_complete_int_parses(api_call: ApiCall) -> None:
        """A record with percentComplete=100 (integer) is parsed without error."""
        mock_response = _make_mock_response(_TIMELINE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_timeline_records(api_call))
        finalize = next(r for r in result if r.name == "Finalize Job")
        assert finalize.percent_complete == 100

    @staticmethod
    def test_record_count(api_call: ApiCall) -> None:
        """All four timeline records from the fixture are yielded."""
        mock_response = _make_mock_response(_TIMELINE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_timeline_records(api_call))
        assert len(result) == 4

    @staticmethod
    def test_stage_record_has_null_parent(api_call: ApiCall) -> None:
        """Stage record has null parentId and is parsed without error."""
        mock_response = _make_mock_response(_TIMELINE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_timeline_records(api_call))
        stage = next(r for r in result if r.type_name == "Stage")
        assert isinstance(stage, BuildRecordInfo)


class TestSmokeIterPrThreads:
    """iter_pr_threads parses real PR thread response shapes."""

    @staticmethod
    def test_parses_system_comment_type(api_call: ApiCall) -> None:
        """Thread comment with commentType='system' parses without error."""
        mock_response = _make_mock_response(_PR_THREADS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pr_threads(api_call))
        assert len(result) == 1
        assert isinstance(result[0], PullRequestThreadResponse)
        assert result[0].comments[0].comment_type == "system"

    @staticmethod
    def test_parses_thread_id_and_comment_count(api_call: ApiCall) -> None:
        """Thread ID and comment list are populated from the real response."""
        mock_response = _make_mock_response(_PR_THREADS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pr_threads(api_call))
        assert result[0].id == 7
        assert len(result[0].comments) == 1

    @staticmethod
    def test_parses_null_thread_context(api_call: ApiCall) -> None:
        """Thread with null threadContext is parsed without error."""
        mock_response = _make_mock_response(_PR_THREADS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pr_threads(api_call))
        assert result[0].thread_context is None


class TestSmokeIterPrIterations:
    """iter_pr_iterations parses real PR iteration response shapes."""

    @staticmethod
    def test_parses_iteration_with_common_ref_commit(api_call: ApiCall) -> None:
        """Iteration with commonRefCommit (extra field) parses without error."""
        mock_response = _make_mock_response(_PR_ITERATIONS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pr_iterations(api_call))
        assert len(result) == 1
        assert isinstance(result[0], PullRequestIterationRecord)
        assert result[0].id == 1

    @staticmethod
    def test_source_and_target_ref_commits_parsed(api_call: ApiCall) -> None:
        """SourceRefCommit and targetRefCommit are both accessible."""
        mock_response = _make_mock_response(_PR_ITERATIONS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pr_iterations(api_call))
        iteration = result[0]
        assert iteration.source_ref_commit is not None
        assert (
            iteration.source_ref_commit.commit_id
            == "484abe3d12855809c2e1169557e0505fa179cedb"
        )
        assert iteration.target_ref_commit is not None
        assert (
            iteration.target_ref_commit.commit_id
            == "b4a8a9c1a41cf98c882adef818f3d00e0eb76587"
        )


class TestSmokePostWiql:
    """post_wiql parses real WIQL response shapes."""

    @staticmethod
    def test_parses_thirteen_work_item_refs(api_call: ApiCall) -> None:
        """Returns all 13 work item refs from a real WIQL response."""
        mock_response = _make_mock_response(_WIQL_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = post_wiql(api_call, "SELECT [System.Id] FROM WorkItems")
        assert len(result) == 13
        assert all(isinstance(ref, WorkItemRef) for ref in result)

    @staticmethod
    def test_work_item_ids_in_descending_order(api_call: ApiCall) -> None:
        """Work item IDs match the order returned by the real WIQL response."""
        mock_response = _make_mock_response(_WIQL_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = post_wiql(api_call, "SELECT [System.Id] FROM WorkItems")
        ids = [ref.id for ref in result]
        assert ids == [105, 104, 103, 102, 101, 100, 99, 98, 97, 96, 95, 94, 93]


class TestSmokeIterWorkItemDetails:
    """iter_work_item_details parses real work item batch response shapes."""

    @staticmethod
    def test_parses_work_items_with_nested_assigned_to(api_call: ApiCall) -> None:
        """Work items with a nested identity in System.AssignedTo parse correctly."""
        mock_response = _make_mock_response(_WORK_ITEMS_BATCH_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_work_item_details(api_call, [101, 102]))
        assert len(result) == 2
        assert all(isinstance(item, WorkItemInfo) for item in result)
        assert result[0].id == 101
        assert result[1].id == 102

    @staticmethod
    def test_system_id_accessible_in_fields(api_call: ApiCall) -> None:
        """System.Id field value (integer) is accessible in the fields dict."""
        mock_response = _make_mock_response(_WORK_ITEMS_BATCH_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_work_item_details(api_call, [101, 102]))
        assert result[0].fields["System.Id"] == 101


class TestSmokeGetWorkItem:
    """get_work_item parses a real single work item response shape."""

    @staticmethod
    def test_parses_work_item_with_relations_and_multiline_format(
        api_call: ApiCall,
    ) -> None:
        """Work item with relations list and multilineFieldsFormat dict parses ok."""
        work_item_api_call = get_work_item_api_call(api_call, 97)
        mock_response = _make_mock_response(_WORK_ITEM_SINGLE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_work_item(work_item_api_call)
        assert isinstance(result, WorkItemInfo)
        assert result.id == 97

    @staticmethod
    def test_relations_list_parsed(api_call: ApiCall) -> None:
        """Relations list with AttachedFile entry is accessible."""
        work_item_api_call = get_work_item_api_call(api_call, 97)
        mock_response = _make_mock_response(_WORK_ITEM_SINGLE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_work_item(work_item_api_call)
        assert result.relations is not None
        assert len(result.relations) == 1
        assert result.relations[0].rel == "AttachedFile"

    @staticmethod
    def test_fields_with_nested_identity_object_parsed(api_call: ApiCall) -> None:
        """System.AssignedTo nested identity dict in fields is preserved as-is."""
        work_item_api_call = get_work_item_api_call(api_call, 97)
        mock_response = _make_mock_response(_WORK_ITEM_SINGLE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_work_item(work_item_api_call)
        assigned_to = result.fields["System.AssignedTo"]
        assert isinstance(assigned_to, dict)
        assert assigned_to["displayName"] == "Test User"


class TestSmokeIterWorkItemComments:
    """iter_work_item_comments parses real work item comment response shapes."""

    @staticmethod
    def test_parses_comment_with_html_format_and_rendered_text(
        api_call: ApiCall,
    ) -> None:
        """Comment with format='html' and renderedText fields parses without error."""
        work_item_api_call = get_work_item_api_call(api_call, 97)
        mock_response = _make_mock_response(_WORK_ITEM_COMMENTS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_work_item_comments(work_item_api_call))
        assert len(result) == 1
        assert isinstance(result[0], WorkItemComment)
        assert result[0].text == "<p>pyado smoke test comment</p>"

    @staticmethod
    def test_comment_id_parsed(api_call: ApiCall) -> None:
        """The large integer comment ID is parsed correctly."""
        work_item_api_call = get_work_item_api_call(api_call, 97)
        mock_response = _make_mock_response(_WORK_ITEM_COMMENTS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_work_item_comments(work_item_api_call))
        assert result[0].id == 24884249


class TestSmokeIterSprintIterations:
    """iter_sprint_iterations parses real sprint iteration response shapes."""

    @staticmethod
    def test_parses_iteration_with_backslash_path(api_call: ApiCall) -> None:
        """Sprint iteration with a backslash-delimited path parses correctly."""
        mock_response = _make_mock_response(_SPRINT_ITERATIONS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_sprint_iterations(api_call))
        assert len(result) == 1
        assert isinstance(result[0], SprintIterationInfo)
        assert result[0].name == "Iteration 0"
        assert result[0].path == "main\\Iteration 0"

    @staticmethod
    def test_sprint_attributes_parsed(api_call: ApiCall) -> None:
        """Sprint attributes (startDate, finishDate, timeFrame) are accessible."""
        mock_response = _make_mock_response(_SPRINT_ITERATIONS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_sprint_iterations(api_call))
        sprint = result[0]
        assert sprint.attributes.timeframe == "current"
        assert sprint.attributes.start_date is not None


class TestSmokeGetBuildDetails:
    """get_build_details parses a real single-build response shape."""

    @staticmethod
    def test_parses_single_build_with_extra_links(api_call: ApiCall) -> None:
        """Single build with sourceVersionDisplayUri, timeline, badge _links parses."""
        build_api_call = get_build_api_call(api_call, 14)
        mock_response = _make_mock_response(_SINGLE_BUILD_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_build_details(build_api_call)
        assert isinstance(result, BuildDetails)
        assert result.id == 14
        assert result.build_number == "20260602.13"

    @staticmethod
    def test_requested_by_and_source_branch_parsed(api_call: ApiCall) -> None:
        """RequestedBy identity and sourceBranch are accessible on the build."""
        build_api_call = get_build_api_call(api_call, 14)
        mock_response = _make_mock_response(_SINGLE_BUILD_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_build_details(build_api_call)
        assert result.requested_by.display_name == "Test User"
        assert result.source_branch == "refs/heads/main"

    @staticmethod
    def test_logs_field_parsed(api_call: ApiCall) -> None:
        """Logs field (BuildLogInfo) is accessible on the result."""
        build_api_call = get_build_api_call(api_call, 14)
        mock_response = _make_mock_response(_SINGLE_BUILD_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_build_details(build_api_call)
        assert result.logs is not None
        assert result.logs.id == 0


class TestSmokeIterVariableGroupDetails:
    """iter_variable_group_details parses real variable group response shapes."""

    @staticmethod
    def test_parses_group_with_null_project_references(
        api_call: ApiCall,
    ) -> None:
        """Variable group with variableGroupProjectReferences=null parses."""
        mock_response = _make_mock_response(_VARIABLE_GROUPS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_variable_group_details(api_call))
        assert len(result) == 1
        assert isinstance(result[0], VariableGroupInfo)
        assert result[0].id == 1
        assert result[0].name == "smoke-test-group"

    @staticmethod
    def test_variable_group_refs_is_none(api_call: ApiCall) -> None:
        """variable_group_refs field is None when API returns null."""
        mock_response = _make_mock_response(_VARIABLE_GROUPS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_variable_group_details(api_call))
        assert result[0].variable_group_refs is None

    @staticmethod
    def test_variables_dict_parsed(api_call: ApiCall) -> None:
        """Variables dict with a single key-value entry is accessible."""
        mock_response = _make_mock_response(_VARIABLE_GROUPS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_variable_group_details(api_call))
        assert "test" in result[0].variables
        assert result[0].variables["test"].value == "test"


class TestSmokeIterPrs:
    """iter_prs parses real pull request list response shapes."""

    @staticmethod
    def test_parses_completed_pr(api_call: ApiCall) -> None:
        """Completed PR with closedDate and completionOptions parses correctly."""
        mock_response = _make_mock_response(_PRS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_prs(api_call))
        assert len(result) == 1
        assert isinstance(result[0], PullRequestListItem)
        assert result[0].pr_id == 4
        assert result[0].status == "completed"

    @staticmethod
    def test_merge_id_and_last_merge_commits_parsed(api_call: ApiCall) -> None:
        """MergeId and lastMerge* commit refs are accessible on the PR."""
        mock_response = _make_mock_response(_PRS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_prs(api_call))
        pr = result[0]
        assert pr.merge_id is not None
        assert pr.last_merge_source_commit is not None
        assert (
            pr.last_merge_source_commit.commit_id
            == "484abe3d12855809c2e1169557e0505fa179cedb"
        )
        assert pr.last_merge_commit is not None

    @staticmethod
    def test_source_and_target_ref_names_parsed(api_call: ApiCall) -> None:
        """SourceRefName and targetRefName are populated from the real response."""
        mock_response = _make_mock_response(_PRS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_prs(api_call))
        assert result[0].source_ref_name == "refs/heads/azure-pipelines"
        assert result[0].target_ref_name == "refs/heads/main"


class TestSmokeIterRefs:
    """iter_refs parses real repository ref response shapes."""

    @staticmethod
    def test_parses_branch_and_pr_merge_refs(api_call: ApiCall) -> None:
        """Parses both a user-created branch ref and a system-created PR merge ref."""
        repo_id = UUID("452ec40a-3193-4a54-ae89-71105e503a67")
        repo_api_call = get_repository_api_call(api_call, repo_id)
        mock_response = _make_mock_response(_REFS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_refs(repo_api_call))
        assert len(result) == 2
        assert all(isinstance(ref, GitRef) for ref in result)

    @staticmethod
    def test_branch_ref_name_and_object_id_parsed(api_call: ApiCall) -> None:
        """Branch ref has name and objectId populated."""
        repo_id = UUID("452ec40a-3193-4a54-ae89-71105e503a67")
        repo_api_call = get_repository_api_call(api_call, repo_id)
        mock_response = _make_mock_response(_REFS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_refs(repo_api_call))
        branch = result[0]
        assert branch.name == "refs/heads/main"
        assert branch.object_id == "a552f5aed0bc38f8c5fb75f3b4c615cc8889f748"

    @staticmethod
    def test_pr_merge_ref_has_system_creator(api_call: ApiCall) -> None:
        """PR merge ref created by system TFS identity parses without error."""
        repo_id = UUID("452ec40a-3193-4a54-ae89-71105e503a67")
        repo_api_call = get_repository_api_call(api_call, repo_id)
        mock_response = _make_mock_response(_REFS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_refs(repo_api_call))
        pr_merge_ref = result[1]
        assert pr_merge_ref.name == "refs/pull/2/merge"


class TestSmokeIterPipelines:
    """iter_pipelines parses real pipeline list response shapes."""

    @staticmethod
    def test_parses_pipeline_list(api_call: ApiCall) -> None:
        """Parses a pipeline list response with _links and folder fields."""
        mock_response = _make_mock_response(_PIPELINES_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pipelines(api_call))
        assert len(result) == 1
        assert isinstance(result[0], PipelineInfo)
        assert result[0].id == 1
        assert result[0].name == "sample-repo"

    @staticmethod
    def test_pipeline_folder_and_revision_parsed(api_call: ApiCall) -> None:
        """Folder (backslash root) and revision are parsed correctly."""
        mock_response = _make_mock_response(_PIPELINES_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pipelines(api_call))
        assert result[0].folder == "\\"
        assert result[0].revision == 1


class TestSmokeGetPipeline:
    """get_pipeline parses a real single-pipeline response shape."""

    @staticmethod
    def test_parses_pipeline_with_configuration_field(api_call: ApiCall) -> None:
        """Single pipeline with extra configuration dict parses without error."""
        mock_response = _make_mock_response(_SINGLE_PIPELINE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_pipeline(api_call, 1)
        assert isinstance(result, PipelineInfo)
        assert result.id == 1
        assert result.name == "sample-repo"

    @staticmethod
    def test_pipeline_folder_is_backslash_root(api_call: ApiCall) -> None:
        """Folder field with backslash value parses correctly."""
        mock_response = _make_mock_response(_SINGLE_PIPELINE_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_pipeline(api_call, 1)
        assert result.folder == "\\"


class TestSmokeIterPipelineRuns:
    """iter_pipeline_runs parses real pipeline run list response shapes."""

    @staticmethod
    def test_parses_two_pipeline_runs(api_call: ApiCall) -> None:
        """Parses a run list with _links, pipeline, templateParameters fields."""
        mock_response = _make_mock_response(_PIPELINE_RUNS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pipeline_runs(api_call, 1))
        assert len(result) == 2
        assert all(isinstance(run, PipelineRunInfo) for run in result)

    @staticmethod
    def test_run_ids_in_descending_order(api_call: ApiCall) -> None:
        """Run IDs match the order returned by the real response."""
        mock_response = _make_mock_response(_PIPELINE_RUNS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pipeline_runs(api_call, 1))
        assert result[0].id == 14
        assert result[1].id == 13

    @staticmethod
    def test_run_with_failed_result_parses(api_call: ApiCall) -> None:
        """Run with result='failed' parses without error."""
        mock_response = _make_mock_response(_PIPELINE_RUNS_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = list(iter_pipeline_runs(api_call, 1))
        failed_run = next(r for r in result if r.id == 13)
        assert failed_run.result == "failed"


class TestSmokeGetPipelineRun:
    """get_pipeline_run parses a real single pipeline-run response shape."""

    @staticmethod
    def test_parses_run_with_yaml_details_extra_field(api_call: ApiCall) -> None:
        """Single run with yamlDetails (extra field) parses without error."""
        mock_response = _make_mock_response(_SINGLE_PIPELINE_RUN_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_pipeline_run(api_call, 1, 14)
        assert isinstance(result, PipelineRunInfo)
        assert result.id == 14
        assert result.name == "20260602.13"

    @staticmethod
    def test_pipeline_nested_object_parsed(api_call: ApiCall) -> None:
        """Pipeline nested object (id, name, folder) is accessible on the run."""
        mock_response = _make_mock_response(_SINGLE_PIPELINE_RUN_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_pipeline_run(api_call, 1, 14)
        assert result.pipeline.id == 1
        assert result.pipeline.name == "sample-repo"

    @staticmethod
    def test_run_state_and_result_parsed(api_call: ApiCall) -> None:
        """State and result fields are populated from the real response."""
        mock_response = _make_mock_response(_SINGLE_PIPELINE_RUN_RESPONSE)
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = get_pipeline_run(api_call, 1, 14)
        assert result.state == "completed"
        assert result.result == "succeeded"
