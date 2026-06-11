# pyado Public API Reference

One-page signature summary of every public symbol.
For prose explanations and worked examples see [usage.md](usage.md).
For the complete agent reference (gotchas, type details, enums) see [AGENT.md](AGENT.md).

---

## Imports

```python
import pyado                              # raw layer + AzureDevOpsService
from pyado.oop import AzureDevOpsService  # preferred OOP entry point
```

---

## OOP Layer (`pyado.oop`)

The OOP layer is the recommended interface. All classes are importable from
`pyado.oop`. Objects form a hierarchy:

```
AzureDevOpsService → Organization → Project → Repository → PullRequest
                                             → WorkItem
                                             → Build  ←→  Pipeline
                                             → Pipeline → PipelineRun
                                             → VariableGroup
                                             → Team
                                             → Iteration / Area
```

Navigation up the hierarchy (`.project`, `.repo`, `.org`) is always zero-cost.

---

### `AzureDevOpsService`

Entry point and object cache. Resolves auth from explicit args or env vars.

```python
AzureDevOpsService(
    *,
    org: str | None = None,           # bare org name (or AZURE_DEVOPS_ORG / SYSTEM_TEAMFOUNDATIONCOLLECTIONURI)
    org_url: str | None = None,       # full URL, e.g. "https://dev.azure.com/myorg"
    pat: str | None = None,           # personal access token (or AZURE_DEVOPS_EXT_PAT)
    credential: TokenCredential | None = None,  # azure-identity credential
    session: requests.Session | None = None,    # custom SSL/trust-store session
)
```

| Member | Signature | Description |
|---|---|---|
| `.org` | `-> Organization` | Organisation singleton (zero-cost after first call) |
| `.api_call` | `-> ApiCall` | Org-level API call for direct `pyado.raw` use |
| `.refresh()` | `-> None` | Clear all cached objects |

---

### `Organization`

Obtained via `AzureDevOpsService.org`.

| Method | Signature | Description |
|---|---|---|
| `.api_call` | `-> ApiCall` | Org-level API call |
| `.get_project(name)` | `(str) -> Project` | Fetch project by name (cached) |
| `.iter_projects()` | `-> Iterator[Project]` | Iterate all projects in the org |
| `.get_connection_data()` | `-> ConnectionData` | Org metadata + authenticated user |
| `.get_my_profile()` | `-> UserProfile` | Profile of the authenticated user |
| `.get_identities(descriptors)` | `(list[str]) -> list[IdentityInfo]` | Resolve subject descriptors |
| `.iter_graph_groups()` | `-> Iterator[GraphGroup]` | All graph groups in the org |

---

### `Project`

Obtained via `Organization.get_project` / `Organization.iter_projects`.

**Properties** (lazy-fetched on first access unless noted):

| Property | Type | Description |
|---|---|---|
| `.name` | `str` | Project name — always known, no API call |
| `.id` | `ProjectId` | Project UUID (lazy-fetched if not supplied) |
| `.info` | `ProjectInfo` | Full project data (lazy-fetched) |
| `.api_call` | `ApiCall` | Project-level API call |
| `.org` | `Organization` | Parent org — zero-cost |

**Methods**:

| Method | Signature | Description |
|---|---|---|
| `.refresh()` | `-> None` | Discard cached info and child-scope caches |
| `.iter_repositories()` | `-> Iterator[Repository]` | All repos in the project |
| `.get_repository(name_or_id)` | `(str) -> Repository` | Repo by name or UUID string |
| `.iter_active_prs(*, expand)` | `-> Iterator[PullRequest]` | All active PRs across all repos |
| `.iter_pull_requests(status, *, criteria, expand)` | `-> Iterator[PullRequest]` | PRs with optional criteria/expand |
| `.get_pull_request(pr_id, repo_id)` | `(int, UUID\|None) -> PullRequest` | PR by ID, optionally scoped to repo |
| `.get_work_item(work_item_id)` | `(int) -> WorkItem` | Single work item with RELATIONS expand |
| `.iter_work_items(query)` | `(str) -> Iterator[WorkItem]` | Work items from a WIQL query |
| `.create_work_item(ticket_type, fields, relations, *, multiline_fields_format)` | `-> WorkItem` | Create new work item |
| `.get_work_items(ids, *, expand)` | `(list[int]) -> list[WorkItem]` | Batch-fetch multiple work items |
| `.get_build(build_id)` | `(int) -> Build` | Single build by ID |
| `.iter_builds(*, definition_id, status_filter, branch_name, top)` | `-> Iterator[Build]` | Builds with optional filters |
| `.start_build(definition_id, *, source_branch, source_version, parameters)` | `-> Build` | Queue a new build |
| `.iter_pipeline_definitions()` | `-> Iterator[PipelineDefinitionInfo]` | Classic build pipeline definitions |
| `.iter_pipelines()` | `-> Iterator[Pipeline]` | Pipelines v2 definitions |
| `.get_pipeline(pipeline_id)` | `(int) -> Pipeline` | Single Pipeline v2 definition |
| `.get_pipeline_by_name(name)` | `(str) -> Pipeline` | Pipeline v2 definition by name (case-sensitive) |
| `.iter_pending_approvals()` | `-> Iterator[PipelineApproval]` | Pending environment approvals |
| `.approve_pipeline(approval_id, *, comment)` | `(str) -> None` | Approve a pending gate |
| `.reject_pipeline(approval_id, *, comment)` | `(str) -> None` | Reject a pending gate |
| `.iter_variable_groups()` | `-> Iterator[VariableGroup]` | All variable groups |
| `.get_variable_group(name)` | `(str) -> VariableGroup` | Variable group by name |
| `.get_variable_group_by_id(group_id)` | `(int) -> VariableGroup` | Variable group by numeric ID |
| `.create_variable_group(name, variables, *, description, var_group_type)` | `-> VariableGroup` | Create a new variable group |
| `.get_query_tree(*, depth, expand)` | `-> list[WorkItemQuery]` | Root-level WIT query folders |
| `.get_query_folder(folder_id, *, depth, expand)` | `(str) -> WorkItemQuery` | Specific WIT query folder by UUID |
| `.get_iteration_node(path, *, depth)` | `(str\|None) -> Iteration` | Iteration classification tree node |
| `.create_iteration(name, parent_path, *, start_date, finish_date)` | `-> str` | Create iteration node; returns GUID |
| `.iter_sprint_iterations(team_name, *, timeframe_filter)` | `-> Iterator[SprintIterationInfo]` | Sprint iterations for a team |
| `.add_team_iteration(team_name, iteration_id)` | `-> None` | Assign iteration to a team |
| `.get_team_field_values(team_name)` | `(str) -> list[TeamFieldValue]` | Team area-path configuration |
| `.get_area_node(path, *, depth)` | `(str\|None) -> Area` | Area classification tree node |
| `.create_area(name, parent_path)` | `-> str` | Create area node; returns GUID |
| `.iter_teams()` | `-> Iterator[Team]` | All teams in the project |
| `.get_team(name_or_id)` | `(str) -> Team` | Team by name or UUID |

---

### `Repository`

Obtained via `Project.get_repository` / `Project.iter_repositories`.

**Properties**:

| Property | Type | Description |
|---|---|---|
| `.id` | `RepositoryId` | Repository UUID |
| `.name` | `str` | Repository name |
| `.default_branch` | `str \| None` | Default branch ref (e.g. `"refs/heads/main"`) |
| `.web_url` | `ADOUrl` | Web URL in the ADO portal |
| `.info` | `RepositoryInfo` | Full repository data |
| `.api_call` | `ApiCall` | Repository-level API call |
| `.project` | `Project` | Parent project — zero-cost |
| `.org` | `Organization` | Parent org — zero-cost |

**Methods**:

| Method | Signature | Description |
|---|---|---|
| `.refresh()` | `-> None` | Re-fetch repository info |
| `.get_pull_request(pull_request_id)` | `(int) -> PullRequest` | Single PR by ID |
| `.iter_pull_requests(status, *, criteria)` | `-> Iterator[PullRequest]` | PRs with optional criteria |
| `.create_pull_request(title, source_branch, target_branch, *, description, completion_options)` | `-> PullRequest` | Create new PR |
| `.get_pr_for_commit(sha)` | `(str) -> PullRequest \| None` | First active PR whose source contains *sha* |
| `.get_pr_for_branch(source_branch)` | `(str) -> PullRequest \| None` | First active PR for a source branch |
| `.get_file_at_branch(path, branch)` | `(str, str) -> str` | File content at branch tip |
| `.get_file_at_commit(path, commit)` | `(str, str) -> str` | File content at commit SHA |
| `.get_file_bytes_at_branch(path, branch)` | `-> bytes \| None` | Raw file bytes at branch tip |
| `.get_file_bytes_at_commit(path, commit)` | `-> bytes \| None` | Raw file bytes at commit SHA |
| `.iter_refs(name_filter, name_contains)` | `-> Iterator[GitRef]` | Git refs with optional filters |
| `.create_branch(name, from_commit)` | `-> None` | Create new branch at commit SHA |
| `.delete_branch(name, current_commit)` | `-> None` | Delete branch (optimistic-concurrency check) |
| `.iter_commits(*, item_path, top, branch)` | `-> Iterator[Commit]` | Commits with optional filters |
| `.get_commit(sha)` | `(str) -> Commit` | Single commit by SHA |
| `.get_default_branch_commit()` | `-> Commit` | HEAD commit of the default branch |
| `.get_last_commit_touching_file(path, before_commit)` | `-> CommitId` | Most recent commit touching a file |
| `.iter_commit_diff(base_commit, target_commit)` | `-> Iterator[GitCommitChange]` | File changes between two commits (paginated) |
| `.get_statistics(branch)` | `(str) -> BranchStatistics` | Ahead/behind counts for a branch |
| `.get_acl()` | `-> list[AccessControlList]` | Repository access control lists |
| `.commit(branch, message, changes)` | `(str, str, list[AddFile\|EditFile\|DeleteFile\|RenameFile]) -> GitPushResult` | Push a single commit |
| `.delete_file(branch, path, message)` | `-> GitPushResult` | Delete a file in one commit |
| `.rename_file(branch, old_path, new_path, message)` | `-> GitPushResult` | Rename/move a file in one commit |
| `.push_commits(ref_updates, commits)` | `-> GitPushResult` | Low-level multi-commit push |
| `.make_ref_update(branch)` | `(str) -> GitPushRefUpdate` | Ref-update entry with current HEAD SHA |

---

### `PullRequest`

Obtained via `Repository.get_pull_request`, `Repository.iter_pull_requests`,
`Repository.create_pull_request`, `Project.get_pull_request`,
`Project.iter_pull_requests`, etc.

**Properties**:

| Property | Type | Description |
|---|---|---|
| `.id` | `PullRequestId` | Numeric PR ID |
| `.title` | `str \| None` | PR title |
| `.status` | `str \| None` | Lifecycle status (`"active"`, `"completed"`, `"abandoned"`) |
| `.source_branch` | `str \| None` | Source ref name |
| `.target_branch` | `str \| None` | Target ref name |
| `.description` | `str \| None` | PR description body |
| `.created_by` | `str \| None` | Display name of the creator |
| `.info` | `PullRequestListItem \| PullRequestCreated` | Raw PR data |
| `.api_call` | `ApiCall` | PR-level API call |
| `.repo` | `Repository` | Parent repo — zero-cost |
| `.project` | `Project` | Parent project — zero-cost |
| `.org` | `Organization` | Parent org — zero-cost |

**Methods**:

| Method | Signature | Description |
|---|---|---|
| `.refresh(expand)` | `-> None` | Re-fetch PR info |
| `.update(*, title, description, status, is_draft)` | `-> None` | Update PR metadata |
| `.complete(last_merge_source_commit, *, completion_options)` | `-> None` | Complete (merge) the PR |
| `.abandon()` | `-> None` | Abandon the PR |
| `.enable_auto_complete(identity_id?, *, completion_options)` | `-> None` | Enable auto-complete (defaults to own identity) |
| `.disable_auto_complete()` | `-> None` | Clear auto-complete |
| `.link_work_item(work_item, *, comment)` | `-> None` | Link PR to a work item via ArtifactLink |
| `.set_work_item_refs(work_item_ids)` | `(list[int]) -> None` | Set work items shown on the PR page |
| `.get_labels()` | `-> list[str]` | Label name strings |
| `.get_label_details()` | `-> list[PullRequestLabel]` | Full label objects |
| `.add_label(name)` | `-> None` | Add a label |
| `.remove_label(name)` | `-> None` | Remove a label |
| `.sync_labels(desired)` | `(set[str]) -> None` | Set labels to exactly *desired* |
| `.get_reviewers()` | `-> list[PullRequestReviewer]` | All reviewers |
| `.add_reviewer(reviewer_id, *, is_required, is_reapprove)` | `-> None` | Add/update a reviewer |
| `.remove_reviewer(reviewer_id)` | `-> None` | Remove a reviewer |
| `.vote(reviewer_id, vote, *, is_reapprove)` | `-> None` | Cast a vote |
| `.iter_threads()` | `-> Iterator[PullRequestThreadResponse]` | All review threads |
| `.get_thread(thread_id)` | `(int) -> PullRequestThreadResponse` | Single thread by ID |
| `.add_thread(content, *, file_path, line, status)` | `-> PullRequestThreadResponse` | Create a review thread |
| `.reply_to_thread(thread_id, content, *, parent_comment_id)` | `-> PullRequestThreadCommentResponse` | Reply to a thread |
| `.update_thread_status(thread_id, status)` | `-> PullRequestThreadResponse` | Change thread status |
| `.iter_commits()` | `-> Iterator[GitCommitRef]` | Commits in the PR |
| `.iter_work_item_ids()` | `-> Iterator[int]` | Linked work item IDs |
| `.iter_work_items()` | `-> Iterator[WorkItem]` | Linked work items (batch-fetched) |
| `.iter_iterations()` | `-> Iterator[PullRequestIterationRecord]` | Push iterations |
| `.get_iteration_changes(iteration_id)` | `(int) -> list[PrIterationChange]` | File changes for an iteration |
| `.iter_files_changed()` | `-> Iterator[PrIterationChange]` | All files changed in the PR (latest iteration) |
| `.iter_statuses()` | `-> Iterator[PullRequestStatusInfo]` | Status checks on the PR |
| `.set_status(state, context_name, *, description, iteration_id, target_url, genre)` | `-> None` | Post a status check result |

---

### `WorkItem`

Obtained via `Project.get_work_item`, `Project.iter_work_items`, `Project.create_work_item`.

**Properties**:

| Property | Type | Description |
|---|---|---|
| `.id` | `WorkItemId` | Numeric work item ID |
| `.title` | `str \| None` | `System.Title` field |
| `.state` | `str \| None` | `System.State` field |
| `.type` | `str \| None` | `System.WorkItemType` field |
| `.assigned_to` | `Any` | `System.AssignedTo` identity dict |
| `.area_path` | `str \| None` | `System.AreaPath` field |
| `.iteration_path` | `str \| None` | `System.IterationPath` field |
| `.info` | `WorkItemInfo` | Full work item data |
| `.api_call` | `ApiCall` | Work-item-level API call |
| `.project` | `Project` | Parent project — zero-cost |
| `.org` | `Organization` | Parent org — zero-cost |

**Methods**:

| Method | Signature | Description |
|---|---|---|
| `.get_field(field)` | `(str) -> Any` | Value of any field by reference name |
| `.refresh(expand)` | `-> None` | Re-fetch work item info |
| `.update(fields, *, multiline_fields_format)` | `-> None` | Update fields |
| `.move(*, iteration_path, area_path)` | `-> None` | Move to different iteration/area |
| `.delete()` | `-> None` | Soft-delete the work item |
| `.get_tags()` | `-> list[str]` | Tags currently set |
| `.add_tag(tag)` | `(str) -> list[str]` | Add a tag; returns updated list |
| `.remove_tag(tag)` | `(str) -> list[str]` | Remove a tag; returns updated list |
| `.iter_comments()` | `-> Iterator[WorkItemComment]` | All comments |
| `.add_comment(text, *, comment_format)` | `-> WorkItemComment` | Add a comment |
| `.update_comment(comment_id, text)` | `-> WorkItemComment` | Edit an existing comment |
| `.delete_comment(comment_id)` | `-> None` | Delete a comment |
| `.add_attachment(filename, content)` | `(str, bytes) -> WorkItemAttachmentRef` | Upload and attach a file |
| `.download_attachment(ref)` | `(WorkItemAttachmentRef) -> bytes` | Download attachment bytes |
| `.add_link(other, link_type, *, comment)` | `-> None` | Link to another work item |
| `.link_pull_request(pr, *, comment)` | `-> None` | Link to a pull request (ArtifactLink) |
| `.link_build(build, *, comment)` | `-> None` | Link to a build (ArtifactLink) |
| `.link_commit(repo, commit_id, *, comment)` | `-> None` | Link to a commit (ArtifactLink) |
| `.remove_link(relation)` | `-> None` | Remove a specific relation |
| `.iter_relations(rel_type)` | `-> Iterator[WorkItemRelation]` | All (or filtered) relations |
| `.iter_artifact_links()` | `-> Iterator[WorkItemRelation]` | Artifact links (PRs, builds, commits) |
| `.iter_attachments()` | `-> Iterator[WorkItemAttachmentRef]` | Attached file references |
| `.iter_linked_work_items(rel_type)` | `-> Iterator[WorkItem]` | Linked work items (batch-fetched) |
| `.get_parent()` | `-> WorkItem \| None` | Parent work item, or None |
| `.iter_children()` | `-> Iterator[WorkItem]` | Direct child work items |
| `.get_child_ids()` | `-> list[int]` | Child IDs from cached relations (no API call) |

---

### `Build`

Obtained via `Project.get_build`, `Project.iter_builds`, `Project.start_build`.

**Properties**:

| Property | Type | Description |
|---|---|---|
| `.id` | `int` | Numeric build ID |
| `.status` | `BuildStatus` | Current build status |
| `.number` | `str` | Build number string |
| `.result` | `BuildResult \| None` | Outcome once completed |
| `.source_branch` | `str` | Source branch ref |
| `.start_time` | `datetime \| None` | UTC start time |
| `.finish_time` | `datetime \| None` | UTC finish time |
| `.queue_time` | `datetime \| None` | UTC time when the build was queued |
| `.source_version` | `str` | Commit SHA that triggered this build |
| `.requested_by` | `str` | Display name of the identity that queued the build |
| `.requested_for` | `str \| None` | Display name of the identity the build was requested for |
| `.info` | `BuildDetails` | Full build data |
| `.api_call` | `ApiCall` | Build-level API call |
| `.pipeline` | `Pipeline` | Owning pipeline — zero-cost (cache lookup) |
| `.project` | `Project` | Parent project — zero-cost |
| `.org` | `Organization` | Parent org — zero-cost |

**Methods**:

| Method | Signature | Description |
|---|---|---|
| `.refresh()` | `-> None` | Re-fetch build info |
| `.update(status)` | `(BuildStatus) -> None` | Update build status |
| `.cancel()` | `-> None` | Request cancellation (Build API) |
| `.cancel_run()` | `-> PipelineRunInfo` | Request cancellation (Pipelines v2 API) |
| `.retry()` | `-> Build` | Queue new build with same definition/branch |
| `.iter_artifacts()` | `-> Iterator[BuildArtifact]` | Published artifacts |
| `.iter_tags()` | `-> Iterator[str]` | Tags on the build |
| `.add_tag(tag)` | `(str) -> list[str]` | Add a tag |
| `.remove_tag(tag)` | `(str) -> list[str]` | Remove a tag |
| `.get_log_text(log_id)` | `(int) -> str` | Fetch plain-text log content |
| `.iter_logs()` | `-> Iterator[BuildLogInfo]` | All log containers for the build |
| `.get_all_log_text(*, separator)` | `-> str` | Fetch and concatenate all log text |
| `.iter_timeline_records()` | `-> Iterator[BuildRecordInfo]` | Raw timeline records |
| `.find_task(predicate)` | `(Callable) -> BuildRecordInfo \| None` | First record matching predicate |
| `.iter_stages()` | `-> Iterator[BuildStage]` | Build stages (with nested jobs/tasks) |
| `.iter_work_item_ids()` | `-> Iterator[int]` | Linked work item IDs |
| `.iter_work_items()` | `-> Iterator[WorkItem]` | Linked work items (batch-fetched) |
| `.iter_work_items_between(older_build, *, top)` | `-> Iterator[WorkItem]` | Work items in build range (exclusive lower bound) |
| `.iter_work_item_ids_between(older_build, *, top)` | `-> Iterator[int]` | Work item IDs in build range |
| `.get_distributed_task_session(*, hub_name, plan_id, timeline_id, job_id, task_instance_id)` | `-> DistributedTaskSession` | External/serverless task handle |

---

### `Pipeline` / `PipelineRun`

Obtained via `Project.get_pipeline`, `Project.iter_pipelines`, or `Build.pipeline`.

**`Pipeline` properties**: `.id`, `.name`, `.info`, `.api_call`, `.project`, `.org`

| Method | Signature | Description |
|---|---|---|
| `.refresh()` | `-> None` | Discard cached pipeline info |
| `.iter_runs()` | `-> Iterator[PipelineRun]` | All runs |
| `.get_run(run_id)` | `(int) -> PipelineRun` | Single run by ID |
| `.get_latest_run()` | `-> PipelineRun \| None` | Most recent run |
| `.start_run(*, resources, variables, template_parameters, stages_to_skip)` | `-> PipelineRun` | Trigger new run |
| `.cancel_run(run_id)` | `(int) -> PipelineRunInfo` | Cancel an in-progress run |
| `.authorize_resource(resource_type, resource_id, *, authorized)` | `-> PipelineResourcePermissions` | Grant/revoke resource access |

**`PipelineRun` properties**: `.id`, `.status`, `.result`, `.info`, `.api_call`, `.pipeline`, `.project`, `.org`

| Method | Signature | Description |
|---|---|---|
| `.refresh()` | `-> None` | Re-fetch run info |
| `.cancel()` | `-> PipelineRun` | Request cancellation |
| `.iter_approvals(state)` | `-> Iterator[PipelineApproval]` | Environment approvals for this run |

---

### `VariableGroup`

Obtained via `Project.iter_variable_groups`, `Project.get_variable_group`.

**Properties**: `.id`, `.name`, `.variables`, `.info`, `.api_call`, `.project`, `.org`

| Method | Signature | Description |
|---|---|---|
| `.refresh()` | `-> None` | Re-fetch variable group info |
| `.update(variables, *, name, description, var_group_type, provider_data)` | `-> None` | Replace all variables (and optionally metadata) |
| `.set_variable(var_name, value, *, is_secret)` | `-> None` | Set or update a single variable |
| `.delete_variable(var_name)` | `-> None` | Remove a single variable |
| `.delete()` | `-> None` | Permanently delete the variable group |

---

### `Team`

Obtained via `Project.iter_teams`, `Project.get_team`.

**Properties**: `.id`, `.name`, `.info`, `.api_call`, `.project`, `.org`

**Methods**:

| Method | Signature | Description |
|---|---|---|
| `.iter_sprint_iterations(*, timeframe_filter)` | `-> Iterator[SprintIterationInfo]` | Sprint iterations for the team |
| `.get_field_values()` | `-> list[TeamFieldValue]` | Team area-path configuration |
| `.add_iteration(iteration_id)` | `-> None` | Assign an iteration to the team |
| `.iter_members()` | `-> Iterator[TeamMember]` | Iterate team members |
| `.get_members()` | `-> list[TeamMember]` | All team members as a list |

---

### `Iteration` / `Area`

Obtained via `Project.get_iteration_node`, `Project.get_area_node`.

**Properties**: `.id`, `.name`, `.path`, `.info` (`ClassificationNode`), `.project`

**Methods**:

| Method | Signature | Description |
|---|---|---|
| `.iter_children()` | `-> Iterator[Iteration\|Area]` | Child nodes at next depth level |
| `.refresh(depth)` | `-> None` | Re-fetch with optional depth |

---

### `Commit`

Obtained via `Repository.iter_commits`, `Repository.get_commit`, etc.

**Properties**: `.sha` (`CommitId`), `.message`, `.author`, `.committer`, `.parents`, `.info` (`GitCommitRef`), `.repo`

---

### File change types (for `Repository.commit`)

| Class | Constructor | Description |
|---|---|---|
| `AddFile(path, content)` | `(str, str)` | Add a new file |
| `EditFile(path, content)` | `(str, str)` | Edit an existing file |
| `DeleteFile(path)` | `(str)` | Delete a file |
| `RenameFile(old_path, new_path)` | `(str, str)` | Rename/move a file |

---

## Raw Layer (`pyado.raw` / `import pyado`)

Lower-level functions — one per ADO REST endpoint. Each takes an `ApiCall` as
its first argument and returns a Pydantic model. Use when the OOP layer does
not cover an endpoint.

### `ApiCall`

```python
ApiCall(
    url: ADOUrl,
    session: requests.Session = requests.Session(),  # default: unauthenticated
    parameters: dict[str, int | str | bool] = {},
    timeout: int = 10,
)
```

| Method | Signature | Description |
|---|---|---|
| `.build_call(*args, parameters, version)` | `-> ApiCall` | Extend URL path and merge query params |
| `.get(*args, parameters, version)` | `-> Any` | HTTP GET |
| `.get_raw(*args, parameters, version)` | `-> bytes` | HTTP GET, returns raw bytes |
| `.post(*args, parameters, version, json, data)` | `-> Any` | HTTP POST |
| `.put(*args, parameters, version, json, data)` | `-> Any` | HTTP PUT |
| `.patch(*args, parameters, version, json)` | `-> Any` | HTTP PATCH |
| `.delete(*args, parameters, version)` | `-> Any` | HTTP DELETE |

**Helpers**:

```python
get_session(
    pat: str | None = None,
    bearer_token: str | None = None,
    azure_credentials: TokenCredential | None = None,
) -> requests.Session
    # Return the cached session for the given credentials.
    # Exactly one argument must be provided.

get_test_api_call() -> tuple[ApiCall, dict]
    # Build an ApiCall from src/pyado/raw/test.json (for manual testing).
```

---

### Profile / Connection

```python
get_profile_api_call(session: requests.Session) -> ApiCall
    # ApiCall for https://app.vssps.visualstudio.com/_apis

get_my_profile(profile_api_call) -> UserProfile
    # Profile of the authenticated user.

get_connection_data(org_api_call) -> ConnectionData
    # Org connection metadata including authenticated user identity.
```

---

### Projects

```python
get_project(org_api_call, name: str) -> ProjectInfo
    # Fetch a single project by name or UUID string.

iter_projects(org_api_call) -> Iterator[ProjectInfo]
    # All projects in the org (paginated).
```

---

### Repositories

```python
iter_repository_details(project_api_call) -> Iterator[RepositoryInfo]
    # All repos in the project.

get_repository_api_call(project_api_call, repository_id: UUID) -> ApiCall
    # Repo-level ApiCall.

get_repository_info(repository_api_call) -> RepositoryInfo
    # Fetch repo details.

get_repository_item_bytes(repository_api_call, path, version_descriptor_version,
                          version_descriptor_type) -> bytes | None
    # Raw file bytes at a version.

get_repository_commits(repository_api_call, search_criteria) -> list[GitCommitRef]
    # Search commits with optional criteria.

get_commit_by_id(repository_api_call, commit_id) -> GitCommitRef
    # Single commit by SHA.

get_commit_diff_page(repository_api_call, base_commit, target_commit, *,
                     skip, top) -> CommitDiffPage
    # One page of file changes between two commits.

get_repository_statistics(repository_api_call, branch) -> BranchStatistics
    # Ahead/behind counts for a branch.

iter_refs(repository_api_call, ref_filter) -> Iterator[GitRef]
    # Git refs with optional filter.

post_repository_refs(repository_api_call, ref_updates: list[GitRefUpdate]) -> None
    # Create/update/delete branches or tags.

post_push(repository_api_call, request: GitPushRequest) -> GitPushResult
    # Push one or more commits.

make_ref_update(branch, old_commit) -> GitPushRefUpdate
    # Build a ref-update entry; adds refs/heads/ prefix automatically.

make_git_acl_token(project_id, repo_id, branch) -> str
    # Build a git ACL token for the security API.

get_git_acl(org_api_call, project_id, repo_id) -> list[AccessControlList]
    # ACLs for a repository or all repos in a project.
```

---

### Pull Requests

```python
get_pr_api_call(project_api_call, repository_id, pr_id) -> ApiCall
    # PR-level ApiCall.

get_pr_details(pr_api_call, *, expand) -> PullRequestCreated
    # Full PR details.

iter_prs(project_api_call, search_criteria, *, expand) -> Iterator[PullRequestListItem]
    # PRs matching criteria (paginated).

post_pull_request(repository_api_call, request: PullRequestCreateRequest) -> PullRequestCreated
    # Create a new PR.

patch_pr(pr_api_call, update: PullRequestUpdateRequest) -> PullRequestCreated
    # Update PR fields.

post_pr_status(pr_api_call, request: PullRequestStatusRequest) -> None
    # Post a status item.

iter_pr_statuses(pr_api_call) -> Iterator[PullRequestStatusInfo]
    # Status items on the PR.

iter_pr_threads(pr_api_call) -> Iterator[PullRequestThreadResponse]
    # Review threads.

get_pr_thread(pr_api_call, thread_id) -> PullRequestThreadResponse
    # Single thread by ID.

post_pr_new_thread(pr_api_call, request: PullRequestThreadRequest) -> PullRequestThreadResponse
    # Create a review thread.

post_pr_thread_comment(pr_api_call, thread_id, comment) -> PullRequestThreadCommentResponse
    # Reply to a thread.

patch_pr_thread(pr_api_call, thread_id, status) -> PullRequestThreadResponse
    # Update thread status.

get_pr_labels_details(pr_api_call) -> list[PullRequestLabel]
    # All labels.

post_pr_label(pr_api_call, label_name) -> None
    # Add a label.

delete_pr_label(pr_api_call, label_name) -> None
    # Remove a label.

get_pr_reviewers(pr_api_call) -> list[PullRequestReviewer]
    # All reviewers.

put_pr_reviewer(pr_api_call, reviewer_id, request: PullRequestReviewerRequest) -> None
    # Add/update a reviewer.

put_pr_reviewer_vote(pr_api_call, reviewer_id, request: PullRequestReviewerVoteRequest) -> None
    # Set reviewer vote.

delete_pr_reviewer(pr_api_call, reviewer_id) -> None
    # Remove a reviewer.

iter_pr_commits(pr_api_call) -> Iterator[GitCommitRef]
    # Commits in the PR.

iter_pr_work_item_ids(pr_api_call) -> Iterator[WorkItemRef]
    # Linked work items.

iter_pr_iterations(pr_api_call) -> Iterator[PullRequestIterationRecord]
    # Push iterations.

get_pr_iteration_changes(pr_api_call, iteration_id) -> list[PrIterationChange]
    # File changes for an iteration.
```

---

### Work Items

```python
get_work_item_api_call(project_api_call, work_item_id) -> ApiCall
    # Work-item-level ApiCall.

get_work_item(work_item_api_call, *, expand) -> WorkItemInfo
    # Fetch a single work item.

post_work_items_batch(project_api_call, request: WorkItemsBatchRequest) -> list[WorkItemInfo]
    # Batch-fetch up to 200 work items.

post_work_item(project_api_call, ticket_type, json_patches) -> WorkItemInfo
    # Create a work item (JSON Patch operations).

patch_work_item(work_item_api_call, json_patches) -> WorkItemInfo
    # Update a work item (JSON Patch operations).

delete_work_item(work_item_api_call) -> None
    # Soft-delete a work item.

post_wiql(project_api_call, query: str) -> list[WorkItemRef]
    # Execute WIQL query; returns work item refs.

iter_work_item_comments(work_item_api_call) -> Iterator[WorkItemComment]
    # All comments (paginated via continuation token).

post_work_item_comment(work_item_api_call, text, *, comment_format) -> WorkItemComment
    # Add a comment.

patch_work_item_comment(work_item_api_call, comment_id, text) -> WorkItemComment
    # Edit a comment.

delete_work_item_comment(work_item_api_call, comment_id) -> None
    # Delete a comment.

post_work_item_attachment_upload(project_api_call, filename, content) -> WorkItemAttachmentRef
    # Upload a file attachment.

get_classification_node(project_call, path, *, node_type, depth) -> ClassificationNode
    # Iteration or area classification tree node.

create_classification_node(project_call, request, parent_path, *, node_type) -> str
    # Create a classification node; returns GUID.

patch_classification_node(project_call, path, request, *, node_type) -> ClassificationNode
    # Rename or update dates of a classification node.

iter_sprint_iterations(team_api_call, timeframe_filter) -> Iterator[SprintIterationInfo]
    # Sprint iterations for a team.

add_team_iteration(team_call, iteration_id) -> None
    # Assign an iteration to a team.

get_team_field_values(team_call) -> list[TeamFieldValue]
    # Team area-path configuration.

get_query_tree(project_call, *, depth, expand) -> list[WorkItemQuery]
    # Root WIT query folders.

get_query_folder(project_call, folder_id, *, depth, expand) -> WorkItemQuery
    # Specific WIT query folder by GUID.
```

---

### Builds

```python
get_build_api_call(project_api_call, build_id) -> ApiCall
    # Build-level ApiCall.

get_build_details(build_api_call) -> BuildDetails
    # Full build details.

iter_builds(project_api_call, search_criteria) -> Iterator[BuildDetails]
    # Builds matching criteria.

post_build(project_api_call, request: BuildQueueRequest) -> BuildDetails
    # Queue a new build.

patch_build(build_api_call, status: BuildStatus) -> BuildDetails
    # Update build status.

get_build_log(build_api_call, log_id) -> str
    # Plain-text content of a build log.

iter_build_artifacts(build_api_call) -> Iterator[BuildArtifact]
    # Artifacts published by the build.

iter_build_tags(build_api_call) -> Iterator[str]
    # Tags on the build.

post_build_tag(build_api_call, tag) -> list[str]
    # Add a tag.

delete_build_tag(build_api_call, tag) -> list[str]
    # Remove a tag.

iter_timeline_records(build_api_call) -> Iterator[BuildRecordInfo]
    # Timeline records (stages, jobs, tasks).

iter_build_work_item_ids(build_api_call) -> Iterator[WorkItemRef]
    # Work items linked to the build.

iter_work_items_between_builds(project_api_call, from_build_id, to_build_id,
                               *, top) -> Iterator[WorkItemRef]
    # Work items in build range (from_build_id exclusive, to_build_id inclusive).

iter_pipeline_definitions(project_api_call, *, name_filter) -> Iterator[PipelineDefinitionInfo]
    # Classic build pipeline definitions.
```

---

### Pipelines v2

```python
iter_pipelines(project_api_call, *, order_by) -> Iterator[PipelineInfo]
    # All Pipelines v2 definitions.

get_pipeline(project_api_call, pipeline_id, *, pipeline_version) -> PipelineInfo
    # Single pipeline definition.

iter_pipeline_runs(project_api_call, pipeline_id) -> Iterator[PipelineRunInfo]
    # All runs of a pipeline.

get_pipeline_run(project_api_call, pipeline_id, run_id) -> PipelineRunInfo
    # Single pipeline run.

post_pipeline_run(project_api_call, pipeline_id, request) -> PipelineRunInfo
    # Trigger a new pipeline run.

post_pipeline_permission(project_api_call, resource_type, resource_id,
                         pipeline_id, *, authorized) -> PipelineResourcePermissions
    # Authorize/de-authorize a resource for a pipeline (additive only).
```

---

### Distributed Task / Active Task

```python
get_plan_api_call(project_api_call, hub_name, plan_id) -> ApiCall
get_timeline_api_call(project_api_call, hub_name, plan_id, timeline_id) -> ApiCall
get_job_api_call(project_api_call, hub_name, plan_id, timeline_id, job_id) -> ApiCall
get_log_api_call(project_api_call, hub_name, plan_id, log_id) -> ApiCall

post_job_feed(job_api_call, payload: JobFeedPayload) -> None
    # Append messages to the task timeline feed.

post_job_logs(log_api_call, message: str) -> None
    # Append a log message to the task log.

post_job_event(plan_api_call, payload: JobEventPayload) -> None
    # Notify ADO that the task has completed.

patch_timeline_records(timeline_api_call, payload: TimelineRecordsUpdatePayload) -> None
    # Update timeline records.

iter_approvals(project_api_call, state) -> Iterator[PipelineApproval]
    # Pipeline environment approvals.

patch_approvals(project_api_call, updates: list[PipelineApprovalUpdateRequest]) -> None
    # Patch one or more approvals.
```

---

### Variable Groups

```python
get_variable_group_api_call(project_api_call, var_group_id) -> ApiCall
    # Variable-group-level ApiCall.

iter_variable_group_details(project_api_call) -> Iterator[VariableGroupInfo]
    # All variable groups in the project.

get_variable_group_details(variable_group_api_call) -> VariableGroupInfo
    # Single variable group.

put_variable_group(variable_group_api_call, request: VariableGroupUpdateRequest) -> VariableGroupInfo
    # Replace a variable group's content.

post_variable_group(project_api_call, request: VariableGroupCreateRequest) -> VariableGroupInfo
    # Create a new variable group.

delete_variable_group(variable_group_api_call) -> None
    # Permanently delete a variable group.
```

---

### Teams

```python
iter_teams(org_api_call, project_name: str) -> Iterator[TeamInfo]
    # All teams in a project.

get_team(org_api_call, project_name, team_name_or_id) -> TeamInfo
    # Single team by name or UUID.
```

---

### Identity / Graph

```python
get_vssps_api_call(session: requests.Session, org_name) -> ApiCall
    # ApiCall for https://vssps.dev.azure.com/{org}.

get_identities(vssps_call, descriptors: list[str]) -> list[IdentityInfo]
    # Resolve subject descriptors to identity records.

iter_graph_groups(vssps_call) -> Iterator[GraphGroup]
    # All graph groups in the org.
```

---

## Key Enums and Types

| Name | Module | Description |
|---|---|---|
| `WorkItemFieldName` | `raw` | Well-known field reference names (`TITLE`, `STATE`, etc.) |
| `WorkItemState` | `raw` | Standard work item state values |
| `WorkItemType` | `raw` | Standard work item type names |
| `WorkItemRelationType` | `raw` | Relation type strings (`PARENT`, `CHILD`, `ARTIFACT_LINK`, etc.) |
| `WorkItemArtifactUrlPrefix` | `raw` | `vstfs:///` URL prefixes for artifact links |
| `WorkItemExpand` | `raw` | Expand options: `NONE`, `RELATIONS`, `FIELDS`, `LINKS`, `ALL` |
| `BuildStatus` | `raw` | `ALL`, `COMPLETED`, `IN_PROGRESS`, `NOT_STARTED`, etc. |
| `BuildResult` | `raw` | `SUCCEEDED`, `FAILED`, `CANCELED`, `PARTIALLY_SUCCEEDED` |
| `PullRequestStatus` | `raw` | `ACTIVE`, `ABANDONED`, `COMPLETED` |
| `PullRequestVote` | `raw` | `APPROVED` (10), `NO_VOTE` (0), `REJECTED` (-10), etc. |
| `PullRequestThreadStatus` | `raw` | `ACTIVE`, `FIXED`, `CLOSED`, `WONT_FIX`, etc. |
| `PullRequestStatusState` | `raw` | `SUCCEEDED`, `FAILED`, `PENDING`, `ERROR`, etc. |
| `GitPullRequestMergeStrategy` | `raw` | `NO_FAST_FORWARD`, `SQUASH`, `REBASE`, `REBASE_MERGE` |
| `PipelineRunState` | `raw` | `IN_PROGRESS`, `COMPLETED`, `CANCELING`, `UNKNOWN` |
| `PipelineRunResult` | `raw` | `SUCCEEDED`, `FAILED`, `CANCELED`, `UNKNOWN` |
| `PipelineApprovalStatus` | `raw` | `APPROVED`, `REJECTED`, `PENDING`, `CANCELED`, etc. |
| `PipelineResourceType` | `raw` | `ENDPOINT`, `ENVIRONMENT`, `QUEUE`, `VARIABLE_GROUP`, etc. |
| `ClassificationNodeUrlType` | `raw` | `ITERATIONS`, `AREAS` |
| `SprintIterationTimeframe` | `raw` | `PAST`, `CURRENT`, `FUTURE` |
| `GitChangeType` | `raw` | `ADD`, `EDIT`, `DELETE`, `RENAME` |
| `GitStatusState` | `raw` | `SUCCEEDED`, `FAILED`, `PENDING`, `ERROR`, etc. |
| `VersionDescriptorType` | `raw` | `BRANCH`, `TAG`, `COMMIT`, `TIP` |
| `TextFormat` | `raw` | `HTML`, `MARKDOWN` (for work item comments) |
| `WorkItemQueryExpand` | `raw` | `NONE`, `MINIMAL`, `CLAUSES`, `ALL` |
| `ZERO_SHA` | `raw` | All-zeros SHA; use as `old_object_id` for a new branch |
| `GIT_SECURITY_NAMESPACE_ID` | `raw` | Security namespace GUID for git ACL lookups |
