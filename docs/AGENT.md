# pyado — Agent Reference

Complete reference for the pyado package. Everything needed to write correct
code without reading the source.

---

## Package overview

`pyado` provides two interfaces over the Azure DevOps REST API:

1. **OOP interface** (`pyado.oop`) — resource objects with methods; the
   recommended entry point. `AzureDevOpsService → Organization → Project →
   Repository / WorkItem / Build / Pipeline / VariableGroup / Team`. Pull
   requests live under `Repository`.
2. **Raw functional interface** (`pyado.raw`) — typed functions that each
   accept an `ApiCall` and return a Pydantic model (never a raw dict).
   Pagination is transparent. All raw symbols are also available from the
   top-level `pyado` package.

```python
import pyado                              # raw layer + AzureDevOpsService
from pyado.oop import AzureDevOpsService  # preferred OOP entry point
```

**See also:** [quick_reference.md](quick_reference.md) for a one-page
signature summary; [usage.md](usage.md) for worked examples.

---

## OOP interface

### Quick start

```python
import pyado

svc  = pyado.AzureDevOpsService(org="https://dev.azure.com/myorg", pat="<pat>")
# or: AzureDevOpsService()  →  reads AZURE_DEVOPS_ORG + AZURE_DEVOPS_EXT_PAT
proj = svc.org.get_project("MyProject")

repo = proj.get_repository("myrepo")
pr   = repo.create_pull_request("Update config", "feature/branch", "main")
wi   = proj.get_work_item(153)
pr.link_work_item(wi)

build    = proj.start_build(definition_id=42)
pipeline = proj.get_pipeline(99)
run      = pipeline.start_run(template_parameters={"env": "staging"})
```

### AzureDevOpsService

```python
pyado.AzureDevOpsService(
    org: str | None = None,         # falls back to AZURE_DEVOPS_ORG
    pat: str | None = None,         # falls back to AZURE_DEVOPS_EXT_PAT
    credential: TokenCredential | None = None,  # azure-identity; mutually exclusive with pat
)

.org         → Organization        # singleton, zero-cost
.api_call    → ApiCall             # org-level; for direct raw calls
.refresh()                         # clear all cached objects
```

### Organization

```python
org = svc.org

.api_call              → ApiCall
.get_project(name)     → Project
.iter_projects()       → Iterator[Project]
.get_connection_data() → ConnectionData
.get_my_profile()      → UserProfile
.get_identities(descriptors: list[str]) → list[IdentityInfo]
.iter_graph_groups()   → Iterator[GraphGroup]
```

### Project

```python
.name      → str           # always available, no API call
.id        → ProjectId     # lazy-fetched on first access
.info      → ProjectInfo
.api_call  → ApiCall
.org       → Organization  # zero-cost
.refresh()

# Repositories
.iter_repositories()         → Iterator[Repository]
.get_repository(name_or_id)  → Repository
.iter_active_prs()           → Iterator[PullRequest]

# Work items
.get_work_item(id)           → WorkItem
.iter_work_items(wiql)       → Iterator[WorkItem]
.get_work_items(ids)         → list[WorkItem]
.create_work_item(type, fields, relations?) → WorkItem

# Builds
.get_build(id)               → Build
.iter_builds(*, status_filter?) → Iterator[Build]
.start_build(definition_id, *, source_branch?, source_version?, parameters?) → Build

# Pipelines
.get_pipeline(id)            → Pipeline
.get_pipeline_by_name(name)  → Pipeline
.iter_pipelines()            → Iterator[Pipeline]
.iter_pipeline_definitions() → Iterator[PipelineDefinitionInfo]
.iter_pending_approvals()    → Iterator[PipelineApproval]
.approve_pipeline(approval_id, *, comment?) → None
.reject_pipeline(approval_id, *, comment?)  → None

# Variable groups
.get_variable_group(name)          → VariableGroup
.get_variable_group_by_id(id)      → VariableGroup
.iter_variable_groups()            → Iterator[VariableGroup]
.create_variable_group(name, variables, *, description?, var_group_type?) → VariableGroup

# Teams
.get_team(name_or_id)  → Team
.iter_teams()          → Iterator[Team]

# Iterations / areas / queries
.get_iteration_node(path?, *, depth?) → Iteration
.create_iteration(name, parent_path?, *, start_date?, finish_date?) → str (guid)
.iter_sprint_iterations(team_name, *, timeframe_filter?) → Iterator[SprintIterationInfo]
.add_team_iteration(team_name, iteration_id) → None
.get_team_field_values(team_name)  → list[TeamFieldValue]
.get_area_node(path?, *, depth?)   → Area
.create_area(name, parent_path?)   → str (guid)
.get_query_tree(*, depth?, expand?) → WorkItemQuery
.get_query_folder(folder_id, *, depth?, expand?) → WorkItemQuery
```

### Repository

```python
.id             → RepositoryId
.name           → str
.default_branch → BranchName | None
.web_url        → ADOUrl
.info           → RepositoryInfo
.api_call       → ApiCall
.project        → Project          # zero-cost
.org            → Organization     # zero-cost
.refresh()

# Pull requests
.get_pull_request(pull_request_id)         → PullRequest
.iter_pull_requests(status?)               → Iterator[PullRequest]
.get_pr_for_branch(source_branch)          → PullRequest | None
.create_pull_request(title, source_branch, target_branch, *, description?, completion_options?) → PullRequest

# File access
.get_file_at_branch(path, branch)          → str   # "" if absent
.get_file_at_commit(path, commit)          → str   # "" if absent
.get_file_bytes_at_branch(path, branch)    → bytes | None
.get_file_bytes_at_commit(path, commit)    → bytes | None

# Refs and branches
.iter_refs(name_filter?, name_contains?)   → Iterator[GitRef]
.create_branch(name, from_commit)          → None
.delete_branch(name, current_commit)       → None
.get_statistics(branch)                    → BranchStatistics

# Commits and diffs
.iter_commits(*, item_path?, top?, branch?) → Iterator[Commit]
.get_commit(sha)                            → Commit
.iter_commit_diff(base, target)             → Iterator[GitCommitChange]
.get_last_commit_touching_file(path, before_commit) → CommitId

# Pushes
.commit(branch, message, changes)          → GitPushResult
.make_ref_update(branch)                   → GitPushRefUpdate
.push_commits(ref_updates, commits)        → GitPushResult

# ACL
.get_acl()                                 → list[AccessControlList]
```

File change helpers (use with `repo.commit` or `pyado.make_commit`):

```python
pyado.AddFile(path, content)          # create a new file
pyado.EditFile(path, content)         # overwrite existing file
pyado.DeleteFile(path)                # delete a file
pyado.RenameFile(old_path, new_path)  # rename without changing content
```

### PullRequest

```python
.id            → PullRequestId
.title         → str | None
.status        → str | None    # "active"|"abandoned"|"completed"
.source_branch → str | None
.target_branch → str | None
.description   → str | None
.created_by    → str | None    # display name
.info          → PullRequestListItem | PullRequestCreated
.api_call      → ApiCall
.repo          → Repository    # zero-cost
.project       → Project       # zero-cost
.org           → Organization  # zero-cost
.refresh()

# Work items
.link_work_item(wi, *, comment?)      # ArtifactLink on the work item
.set_work_item_refs(ids)              # visible in ADO PR page
.iter_work_item_ids()                 → Iterator[int]

# Labels
.get_labels()           → list[str]
.add_label(name)
.remove_label(name)

# Threads
.iter_threads()          → Iterator[PullRequestThreadResponse]
.add_thread(content, *, file_path?, line?, status?) → PullRequestThreadResponse
.reply_to_thread(thread_id, content, *, parent_comment_id?) → PullRequestThreadCommentResponse
.update_thread_status(thread_id, status) → PullRequestThreadResponse

# Reviewers
.get_reviewers()                                  → list[PullRequestReviewer]
.add_reviewer(reviewer_id, *, is_required?, is_reapprove?)
.remove_reviewer(reviewer_id)
.vote(reviewer_id, vote: PullRequestVote, *, is_reapprove?)

# Status checks
.set_status(state, context_name, *, description?, iteration_id?, target_url?, genre?)
.iter_statuses()  → Iterator[PullRequestStatusInfo]

# Commits and iterations
.iter_commits()               → Iterator[GitCommitRef]
.iter_iterations()            → Iterator[PullRequestIterationRecord]
.get_iteration_changes(iter_id) → list[PrIterationChange]

# Lifecycle
.update(*, title?, description?, status?, is_draft?)
.enable_auto_complete(identity_id?, *, completion_options?)  # defaults to own identity
.disable_auto_complete()
.complete(last_merge_source_commit, *, completion_options?)
.abandon()
```

### WorkItem

```python
.id             → int
.title          → str | None    # System.Title
.state          → str | None    # System.State
.type           → str | None    # System.WorkItemType
.assigned_to    → Any           # System.AssignedTo (identity dict)
.area_path      → str | None    # System.AreaPath
.iteration_path → str | None    # System.IterationPath
.get_field(field) → Any
.info           → WorkItemInfo
.api_call       → ApiCall
.project        → Project       # zero-cost
.org            → Organization  # zero-cost
.refresh()

.update(fields, *, multiline_fields_format?)
.get_tags()        → list[str]
.add_tag(tag)      → list[str]
.remove_tag(tag)   → list[str]

.iter_comments()              → Iterator[WorkItemComment]
.add_comment(text, *, comment_format?) → WorkItemComment
.update_comment(id, text)     → WorkItemComment
.delete_comment(id)

.add_attachment(filename, content) → WorkItemAttachmentRef

.add_link(other, link_type, *, comment?)  # WI-to-WI relation
.link_pull_request(pr, *, comment?)
.link_build(build, *, comment?)
.link_commit(repo, commit_id, *, comment?)

.get_parent()      → WorkItem | None
.iter_children()   → Iterator[WorkItem]
.iter_linked_work_items(rel_type?) → Iterator[WorkItem]

.delete()          # soft-delete; restorable from Recycle Bin for 30 days
```

### Build

```python
.id           → int
.number       → str           # e.g. "20240101.1"
.status       → BuildStatus
.result       → BuildResult | None
.source_branch → str
.source_version → str         # commit SHA
.start_time   → datetime | None
.finish_time  → datetime | None
.queue_time   → datetime | None
.requested_by → str           # display name of the identity that queued the build
.requested_for → str | None   # display name of the build's target identity
.info         → BuildDetails
.api_call     → ApiCall
.pipeline     → Pipeline       # zero-cost, no API call
.project      → Project        # zero-cost
.org          → Organization   # zero-cost
.refresh()

.cancel()          → BuildDetails
.cancel_run()      → PipelineRunInfo   # via Pipelines v2
.retry()           → Build             # same definition and branch

.iter_artifacts()  → Iterator[BuildArtifact]
.iter_tags()       → Iterator[str]
.add_tag(tag)      → list[str]
.remove_tag(tag)   → list[str]

.iter_timeline_records()  → Iterator[BuildRecordInfo]
.iter_stages()            → Iterator[BuildStage]
.get_log_text(log_id)     → str
.iter_logs()              → Iterator[BuildLogInfo]
.get_all_log_text(*, separator?) → str

.iter_work_item_ids()                        → Iterator[int]
.iter_changes_between(older_build, *, top?)  → Iterator[WorkItem]
.iter_work_item_ids_between(older_build, *, top?) → Iterator[int]

.get_active_build_task(*, hub_name, plan_id, timeline_id, job_id, task_instance_id) → ActiveBuildTask
```

**BuildStage / BuildJob / BuildTask** (from `build.iter_stages()`):

```python
stage.name, stage.state, stage.result, stage.log
stage.iter_jobs()    → Iterator[BuildJob]

job.name, job.state, job.result, job.log
job.iter_tasks()     → Iterator[BuildTask]
job.iter_phases()    → Iterator[BuildPhase]

task.name, task.state, task.result, task.log
```

### Pipeline

```python
.id    → int        # always known, no API call
.name  → str        # always known, no API call
.info  → PipelineInfo   # lazy-fetched
.api_call → ApiCall
.project  → Project     # zero-cost
.org      → Organization # zero-cost
.refresh()

.iter_runs()              → Iterator[PipelineRunInfo]
.get_run(run_id)          → PipelineRunInfo
.get_latest_run()         → PipelineRunInfo | None
.start_run(*, resources?, variables?, template_parameters?, stages_to_skip?) → PipelineRunInfo
.authorize_resource(resource_type, resource_id, *, authorized?) → PipelineResourcePermissions
```

### VariableGroup

```python
.id        → int
.name      → str
.variables → dict[str, VariableInfo]
.info      → VariableGroupInfo
.api_call  → ApiCall
.project   → Project       # zero-cost
.org       → Organization  # zero-cost
.refresh()

.update(variables, *, name?, description?, var_group_type?, provider_data?)
.set_variable(var_name, value, *, is_secret?)  # read-modify-write
.delete_variable(var_name)                     # raises KeyError if absent
.delete()                                      # permanent deletion
```

### Team

```python
.id      → str   # UUID string
.name    → str
.info    → TeamInfo
.api_call → ApiCall   # team-level (for raw teamsettings functions)
.project → Project    # zero-cost
.org     → Organization # zero-cost

.iter_sprint_iterations(*, timeframe_filter?) → Iterator[SprintIterationInfo]
.get_field_values()     → list[TeamFieldValue]
.add_iteration(iteration_id) → None
.iter_members()  → Iterator[TeamMember]
.get_members()   → list[TeamMember]
```

### Iteration / Area

```python
# Iteration (from proj.get_iteration_node)
.name        → str
.id          → str   # GUID
.path        → str
.start_date  → date | None
.finish_date → date | None
.children    → list[Iteration]
.project     → Project

# Area (from proj.get_area_node)
.name     → str
.id       → str
.path     → str
.children → list[Area]
.project  → Project
```

### Commit

```python
# Obtained from repo.iter_commits() or repo.get_commit()
.id         → CommitId      # SHA string
.message    → str | None
.author     → ...           # .name, .email, .date
.info       → GitCommitRef
.repo       → Repository    # zero-cost
.project    → Project       # zero-cost
```

---

---

## The ApiCall object

`ApiCall` is the credential-and-URL object every function takes as its first
argument. It is an immutable Pydantic model.

```python
class ApiCall(BaseModel):
    access_token: str      # ADO personal access token
    url: HttpUrl           # must be https://
    parameters: dict = {}  # merged into every request as query params
    timeout: int = 10      # request timeout in seconds
```

### Construction

```python
# Project-level (required by most functions)
api = pyado.ApiCall(
    access_token="<pat>",
    url="https://dev.azure.com/<org>/<project>/_apis/",
)

# Organisation-level (iter_projects, iter_pull_requests across all repos)
org_api = pyado.ApiCall(
    access_token="<pat>",
    url="https://dev.azure.com/<org>/_apis/",
)
```

The **profile API** lives on a separate host; use the dedicated helper:

```python
profile_api = pyado.get_profile_api_call(access_token="<pat>")
# → ApiCall(url="https://app.vssps.visualstudio.com/_apis")
```

### build_call()

Appends path segments and merges query parameters to produce a new `ApiCall`:

```python
child = api.build_call("wit", "workitems", 42, version="7.0")
# url becomes: …/_apis/wit/workitems/42?api-version=7.0
```

---

## Scoped API call helpers

All `get_*_api_call` functions return a new `ApiCall` pointing at the given
resource. Construct them once and reuse.

| Function | Args | Returns | Notes |
|---|---|---|---|
| `get_work_item_api_call(project_api, work_item_id)` | `ApiCall, int` | `ApiCall` | |
| `get_build_api_call(project_api, build_id)` | `ApiCall, int` | `ApiCall` | |
| `get_pr_api_call(project_api, repo_id, pr_id)` | `ApiCall, UUID, int` | `ApiCall` | |
| `get_repository_api_call(project_api, repo_id)` | `ApiCall, UUID` | `ApiCall` | |
| `get_variable_group_api_call(project_api, var_group_id)` | `ApiCall, int` | `ApiCall` | |
| `get_plan_api_call(project_api, hub_name, plan_id)` | `ApiCall, str, UUID` | `ApiCall` | task callbacks |
| `get_job_api_call(project_api, hub_name, plan_id, timeline_id, job_id)` | `ApiCall, str, UUID, UUID, UUID` | `ApiCall` | task callbacks |
| `get_log_api_call(project_api, hub_name, plan_id, log_id)` | `ApiCall, str, int` | `ApiCall` | task callbacks |
| `get_timeline_api_call(project_api, hub_name, plan_id, timeline_id)` | `ApiCall, str, UUID, UUID` | `ApiCall` | task callbacks |
| `get_profile_api_call(access_token)` | `str` | `ApiCall` | different host |
| `get_test_api_call()` | — | `tuple[ApiCall, dict]` | test use only |

---

## Constants

| Name | Type | Value | Use |
|---|---|---|---|
| `ZERO_SHA` | `CommitId` | `"0000000000000000000000000000000000000000"` | `old_object_id` when creating a new branch |

---

## Function reference

### Work items

| Function | Signature | Returns |
|---|---|---|
| `iter_work_item_details` | `(project_api, ids: list[int], work_item_field_list: list[str] \| None = None)` | `Iterator[WorkItemInfo]` |
| `get_work_item` | `(wi_api, *, expand_relations: bool = False)` | `WorkItemInfo` |
| `create_work_item` | `(project_api, fields: dict[str, Any], relations: list[WorkItemRelation] \| None = None)` | `WorkItemInfo` |
| `update_work_item` | `(wi_api, fields: dict[str, Any], *, multiline_fields_format: dict[str, str] \| None = None)` | `WorkItemInfo` |
| `add_artifact_link` | `(wi_api, artifact_url: str, *, comment: str \| None = None)` | `WorkItemInfo` |
| `get_work_item_tags` | `(wi_api)` | `list[str]` |
| `add_work_item_tag` | `(wi_api, tag: str)` | `list[str]` |
| `remove_work_item_tag` | `(wi_api, tag: str)` | `list[str]` |
| `iter_work_item_comments` | `(wi_api)` | `Iterator[WorkItemComment]` |
| `post_work_item_comment` | `(wi_api, text: str, *, comment_format: str = "html")` | `WorkItemComment` |
| `add_work_item_attachment` | `(project_api, work_item_id: int, filename: str, content: bytes)` | `WorkItemAttachmentRef` |
| `post_wiql` | `(project_api, query: str)` | `list[WorkItemRef]` |
| `iter_sprint_iterations` | `(team_api, timeframe_filter: str \| None = None)` | `Iterator[SprintIterationInfo]` |

**Notes:**
- `create_work_item`: `fields` must include `"System.WorkItemType"`. All other ADO
  field reference names are optional (e.g. `"System.Title"`, `"System.State"`).
- `update_work_item`: `multiline_fields_format` values are `"html"` or `"markdown"`.
  A format entry without a matching key in `fields` will be rejected by ADO.
- `add_work_item_tag` / `remove_work_item_tag`: comparison is case-insensitive.
  No-op if tag already present / already absent.
- `post_work_item_comment`: `comment_format` is `"html"` (default) or `"markdown"`.
- `add_work_item_attachment`: two-step (upload + link) in a single call.
- `add_artifact_link`: artifact URL for ADO PRs has the form
  `vstfs:///Git/PullRequestId/{project_id}%2F{repo_id}%2F{pr_id}`.
- `iter_sprint_iterations`: `timeframe_filter` common values: `"current"`,
  `"past"`, `"future"`.

---

### Pull requests

| Function | Signature | Returns |
|---|---|---|
| `iter_open_prs` | `(project_api)` | `Iterator[PullRequestListItem]` |
| `iter_prs` | `(project_api, search_criteria: dict[str, Any] \| None = None)` | `Iterator[PullRequestListItem]` |
| `get_pr_details` | `(pr_api)` | `PullRequestCreated` |
| `create_pr` | `(repo_api, title: str, source_branch: str, target_branch: str, *, description: str \| None = None, completion_options: PullRequestCompletionOptions \| None = None, work_item_ids: list[int] \| None = None)` | `PullRequestCreated` |
| `patch_pr` | `(pr_api, update: PullRequestUpdateRequest)` | `None` |
| `iter_pr_commits` | `(pr_api)` | `Iterator[GitCommitRef]` |
| `iter_pr_iterations` | `(pr_api)` | `Iterator[PullRequestIterationRecord]` |
| `iter_pr_threads` | `(pr_api)` | `Iterator[PullRequestThreadResponse]` |
| `create_pr_thread` | `(pr_api, content: str, *, file_path: str \| None = None, line: int \| None = None, status: PullRequestThreadStatus = "active")` | `PullRequestThreadResponse` |
| `reply_to_pr_thread` | `(pr_api, thread_id: int, content: str, *, parent_comment_id: int = 1)` | `PullRequestThreadCommentResponse` |
| `iter_pr_work_item_ids` | `(pr_api)` | `Iterator[int]` |
| `get_pr_labels` | `(pr_api)` | `list[str]` |
| `post_pr_label` | `(pr_api, label_name: str)` | `None` |
| `delete_pr_label` | `(pr_api, label_name: str)` | `None` |
| `get_pr_reviewers` | `(pr_api)` | `list[PullRequestReviewer]` |
| `add_pr_reviewer` | `(pr_api, reviewer_id: str, *, is_required: bool = False, is_reapprove: bool = False)` | `None` |
| `set_pr_reviewer_vote` | `(pr_api, reviewer_id: str, vote: PullRequestVote, *, is_reapprove: bool = False)` | `None` |
| `delete_pr_reviewer` | `(pr_api, reviewer_id: str)` | `None` |
| `post_pr_status` | `(pr_api, request: PullRequestStatusRequest)` | `None` |

**Notes:**
- `iter_prs` `search_criteria` keys are ADO `searchCriteria.*` parameter names
  without the prefix, e.g. `{"status": "active", "creatorId": "<uuid>",
  "repositoryId": "<uuid>", "targetRefName": "refs/heads/main"}`.
- `create_pr`: branch names are normalised — `"main"` and `"refs/heads/main"`
  are both accepted. Default `completion_options` is squash-merge + delete
  source branch.
- `create_pr_thread`: `line` requires `file_path`. Raises `ValueError` otherwise.
- `reviewer_id` is the identity object UUID (e.g. from `PullRequestReviewer.id`).

---

### Repository

| Function | Signature | Returns |
|---|---|---|
| `iter_repository_details` | `(project_api)` | `Iterator[RepositoryInfo]` |
| `get_file_content_at_commit` | `(repo_api, path: str, commit_sha: str)` | `str` |
| `get_file_content_at_branch` | `(repo_api, path: str, branch_name: str)` | `str` |
| `iter_commit_diff` | `(repo_api, base_commit: str, target_commit: str)` | `Iterator[GitCommitChange]` |
| `get_last_commit_touching_file` | `(repo_api, path: str, before_commit: str)` | `str` |
| `iter_refs` | `(repo_api, name_filter: str \| None = None)` | `Iterator[GitRef]` |
| `create_branch` | `(repo_api, branch_name: str, from_commit: str)` | `None` |
| `delete_branch` | `(repo_api, branch_name: str, current_commit: str)` | `None` |

**Notes:**
- `get_file_content_at_*`: returns `""` (empty string) when the file does not
  exist at that ref — never raises an exception for a missing file.
- `iter_commit_diff`: skips folder entries; yields only file-level changes.
  Paginates automatically.
- `get_last_commit_touching_file`: falls back to `before_commit` if no match.
- `iter_refs`: `name_filter` is a prefix, e.g. `"heads/main"`,
  `"heads/release/"`. Branch refs have the form `"refs/heads/<name>"`.
- `create_branch` / `delete_branch`: branch name is normalised — short names
  like `"main"` are accepted.
- `delete_branch`: `current_commit` is the current HEAD SHA (optimistic
  concurrency; ADO rejects the delete if the branch has moved).

---

### Git push

| Function | Signature | Returns |
|---|---|---|
| `make_ref_update` | `(branch: str, old_commit: str)` | `GitPushRefUpdate` |
| `add_file` | `(path: str, content: str)` | `GitPushChange` |
| `edit_file` | `(path: str, content: str)` | `GitPushChange` |
| `delete_file` | `(path: str)` | `GitPushChange` |
| `rename_file` | `(old_path: str, new_path: str)` | `GitPushChange` |
| `make_commit` | `(message: str, changes: list[GitPushChange])` | `GitPushCommit` |
| `push_commits` | `(repo_api, ref_updates: list[GitPushRefUpdate], commits: list[GitPushCommit])` | `GitPushResult` |

**Notes:**
- `make_ref_update`: pass `pyado.ZERO_SHA` as `old_commit` when pushing to a
  branch that does not yet exist.
- `push_commits`: multiple commits can be batched in a single call.
- File content is UTF-8 text. For binary content, base64-encode and construct
  a `GitPushNewContent(content=b64, content_type="base64encoded")` manually.

---

### Builds

| Function | Signature | Returns |
|---|---|---|
| `get_build_details` | `(build_api)` | `BuildDetails` |
| `iter_builds` | `(project_api, *, definition_id: int \| None = None, status_filter: BuildStatus \| None = None, branch_name: str \| None = None, top: int \| None = None)` | `Iterator[BuildDetails]` |
| `start_build` | `(project_api, definition_id: int, *, source_branch: str \| None = None, source_version: str \| None = None, parameters: dict[str, str] \| None = None)` | `BuildDetails` |
| `iter_timeline_records` | `(build_api)` | `Iterator[BuildRecordInfo]` |
| `iter_build_work_item_ids` | `(build_api)` | `Iterator[int]` |
| `iter_work_items_between_builds` | `(project_api, from_build_id: int, to_build_id: int, *, top: int \| None = None)` | `Iterator[WorkItemRef]` |
| `iter_build_artifacts` | `(build_api)` | `Iterator[BuildArtifact]` |
| `iter_build_tags` | `(build_api)` | `Iterator[str]` |
| `post_build_tag` | `(build_api, tag: str)` | `list[str]` |
| `delete_build_tag` | `(build_api, tag: str)` | `list[str]` |
| `iter_pipeline_definitions` | `(project_api, *, name_filter: str \| None = None)` | `Iterator[PipelineDefinitionInfo]` |

**Notes:**
- `iter_builds`: `status_filter` values from `BuildStatus` literal (see enums).
- `iter_work_items_between_builds`: range is exclusive lower bound, inclusive
  upper bound: `(from_build_id, to_build_id]`.

---

### Pipeline task callbacks

Used by scripts running inside ADO agent jobs to communicate back to the pipeline.

| Function | Signature | Returns |
|---|---|---|
| `send_job_feed` | `(job_api, messages: list[str])` | `None` |
| `post_job_logs` | `(log_api, content: str)` | `None` |
| `send_job_event` | `(plan_api, task_id: UUID, job_id: UUID, job_event_name: JobEventName, job_event_result: JobEventResult)` | `None` |
| `update_timeline_records` | `(timeline_api, records: list[BuildRecordInfo])` | `None` |
| `iter_pending_approvals` | `(project_api)` | `Iterator[PipelineApproval]` |
| `approve_pipeline` | `(project_api, approval_id: str, *, comment: str = "")` | `None` |

**Notes:**
- `job_event_name`: `Literal["TaskCompleted"]`
- `job_event_result`: `Literal["succeeded", "failed"]`
- `send_job_event` signals that a task has completed. Call after all log/feed output.

---

### Pipeline runs (YAML pipelines)

These use the `/pipelines` REST API, which is distinct from the `/build` API.
A run ID equals the corresponding build ID.

| Function | Signature | Returns |
|---|---|---|
| `iter_pipelines` | `(project_api, *, order_by: str \| None = None)` | `Iterator[PipelineInfo]` |
| `get_pipeline` | `(project_api, pipeline_id: int, *, pipeline_version: int \| None = None)` | `PipelineInfo` |
| `iter_pipeline_runs` | `(project_api, pipeline_id: int)` | `Iterator[PipelineRunInfo]` |
| `get_pipeline_run` | `(project_api, pipeline_id: int, run_id: int)` | `PipelineRunInfo` |
| `post_pipeline_run` | `(project_api, pipeline_id: int, request: PipelineRunRequest)` | `PipelineRunInfo` |

---

### Projects

Requires an **organisation-level** `ApiCall`.

| Function | Signature | Returns |
|---|---|---|
| `iter_projects` | `(org_api)` | `Iterator[ProjectInfo]` |

---

### Variable groups

| Function | Signature | Returns |
|---|---|---|
| `iter_variable_group_details` | `(project_api)` | `Iterator[VariableGroupInfo]` |
| `update_variable_group` | `(vg_api, name: str, variables: dict[str, VariableInfo], variable_group_project_references: Any, *, description: str \| None = None, var_group_type: str \| None = None, provider_data: Any = None)` | `VariableGroupInfo` |

**Notes:**
- `update_variable_group`: `variable_group_project_references` must be passed
  through from the existing group's `variable_group_refs` field. The ADO PUT
  API requires it to identify the target project.
- Secret variables (`is_secret=True`) can be written but never read back —
  ADO returns `value=None` for secrets.

---

### Profile

Requires a **profile `ApiCall`** (`get_profile_api_call`), not a project API call.

| Function | Signature | Returns |
|---|---|---|
| `get_my_profile` | `(profile_api)` | `UserProfile` |

---

## Type reference

### Core

```
ApiCall
  access_token: str
  url: HttpUrl
  parameters: dict[str, int | str | bool]
  timeout: int
  .build_call(*args, parameters?, version?) → ApiCall
```

### Work items

```
WorkItemInfo
  id: int
  rev: int | None
  url: AnyUrl | None
  fields: dict[str, Any]       # keys are ADO field reference names
  relations: list[WorkItemRelation]

WorkItemRelation
  rel: str                     # e.g. "System.LinkTypes.Hierarchy-Reverse", "ArtifactLink"
  url: AnyUrl
  attributes: dict[str, Any] | None

WorkItemRef
  id: int
  url: AnyUrl | None

WorkItemComment
  id: int
  text: str
  created_by: _IdentityRef | None
  modified_by: _IdentityRef | None
  created_date: datetime
  modified_date: datetime
  is_deleted: bool
  format: str | None

WorkItemAttachmentRef
  id: str
  url: AnyUrl                  # permanent download URL

SprintIterationInfo
  id: UUID
  name: str
  path: str
  attributes: SprintIterationAttributes

SprintIterationAttributes
  start_date: datetime | None
  finish_date: datetime | None
  timeframe: str               # "current" | "past" | "future"
```

### Pull requests

```
PullRequestListItem
  pr_id: int
  repository: RepositoryRef   # .id: UUID
  title: str | None
  description: str | None
  source_ref_name: str | None  # "refs/heads/..."
  target_ref_name: str | None
  created_by: _IdentityRef | None
  creation_date: datetime | None
  status: str | None           # "active" | "abandoned" | "completed"
  is_draft: bool
  merge_status: PullRequestMergeStatus | None
  reviewers: list[PullRequestReviewer]
  labels: list[PullRequestLabel]

PullRequestCreated            # returned by create_pr and get_pr_details
  pr_id: int
  repository: RepositoryRef
  status: str
  url: str
  title: str
  source_ref_name: str
  target_ref_name: str
  is_draft: bool
  created_by: _IdentityRef | None
  creation_date: datetime | None
  reviewers: list[PullRequestReviewer]
  merge_status: str | None
  merge_id: str | None
  last_merge_source_commit: GitCommitRef | None
  last_merge_target_commit: GitCommitRef | None
  last_merge_commit: GitCommitRef | None
  completion_options: PullRequestCompletionOptions | None
  labels: list[PullRequestLabel]
  description: str | None
  artifact_id: str | None
  supports_iterations: bool

PullRequestUpdateRequest      # all fields optional; only non-None are sent
  title: str | None
  description: str | None
  status: PullRequestStatus | None   # "active"|"abandoned"|"completed"
  is_draft: bool | None
  completion_options: PullRequestCompletionOptions | None
  last_merge_source_commit: dict[str, str] | None  # {"commitId": "..."}

PullRequestCompletionOptions
  squash_merge: bool = True
  delete_source_branch: bool = True
  merge_strategy: GitPullRequestMergeStrategy | None
  merge_commit_message: str | None
  transition_work_items: bool = False

PullRequestThreadResponse
  id: int | None
  status: PullRequestThreadStatus | None
  comments: list[PullRequestThreadCommentResponse]
  thread_context: PullRequestThreadContext | None  # file/line anchor
  published_date: datetime | None
  is_deleted: bool

PullRequestThreadCommentResponse
  id: int | None
  content: str | None
  comment_type: str | None
  parent_comment_id: int
  author: _IdentityRef | None
  published_date: datetime | None
  is_deleted: bool

PullRequestIterationRecord
  id: int
  source_ref_commit: GitCommitRef | None
  target_ref_commit: GitCommitRef | None

PullRequestReviewer
  id: str                      # identity object UUID
  display_name: str
  vote: int                    # use PullRequestVote enum values
  is_required: bool
  has_declined: bool
  is_flagged: bool

PullRequestStatusRequest
  context: PullRequestStatusContext
  description: str | None
  iteration_id: int
  state: PullRequestStatusState
  target_url: AnyUrl | None

PullRequestStatusContext
  name: str
  genre: str | None
```

### Repository

```
RepositoryInfo
  id: UUID
  name: str
  project: ProjectInfo
  default_branch: str | None
  size: int
  remote_url: HttpUrl
  ssh_url: str
  web_url: HttpUrl
  is_disabled: bool
  is_in_maintenance: bool
  is_fork: bool
  parent_repository: _GitRepositoryRef | None  # .id, .name

GitRef
  name: str                    # "refs/heads/main"
  object_id: str               # commit SHA

GitCommitRef
  commit_id: str
  comment: str | None
  author: _GitUserDate | None  # .name, .email, .date
  committer: _GitUserDate | None
  parents: list[str]
  change_counts: dict[str, int] | None
  statuses: list[GitStatus]
  work_items: list[WorkItemRef]

GitCommitChange
  change_type: str             # "add"|"edit"|"delete"|"rename"|...
  item: GitCommitChangeItem    # .path, .is_folder
```

### Git push

```
GitPushResult
  push_id: int
  commits: list[GitCommitRef]

GitPushRefUpdate              # produced by make_ref_update()
  name: str
  old_object_id: str

GitPushChange                 # produced by add_file/edit_file/delete_file/rename_file
  change_type: GitPushChangeType
  item: GitPushChangeItem     # .path
  new_content: GitPushNewContent | None  # .content, .content_type
  source_server_item: str | None        # rename source path
```

### Builds

```
BuildDetails
  id: int
  build_number: str
  status: BuildStatus
  result: BuildResult | None
  queue_time: datetime | None
  start_time: datetime | None
  finish_time: datetime | None
  source_branch: str
  source_version: str
  definition: _BuildDefinitionRef  # .id, .name
  requested_by: _IdentityRef
  tags: list[str]
  parameters: str | None           # JSON string
  orchestration_plan: _BuildOrchestrationPlan | None  # .plan_id: UUID
  logs: BuildLogInfo | None
  deleted: bool

BuildRecordInfo               # one record in the build timeline
  id: UUID                    # task / job / stage UUID
  name: str
  type_name: BuildRecordType  # "Stage"|"Job"|"Task"|...
  state: "completed"|"pending"|"inProgress"
  result: "failed"|"succeeded"|"skipped"|"canceled" | None
  start_time: datetime | None
  finish_time: datetime | None
  log: BuildLogInfo | None
  parent_id: UUID | None
  issues: list[BuildIssue] | None  # .type, .message, .category

BuildArtifact
  id: int
  name: str
  resource: BuildArtifactResource  # .type, .url, .download_url

PipelineDefinitionInfo
  id: int
  name: str
  path: str
  queue_status: str
  revision: int
```

### Pipeline runs (YAML)

```
PipelineInfo
  id: int
  revision: int
  name: str
  folder: str
  url: AnyUrl

PipelineRunInfo
  id: int
  name: str
  state: PipelineRunState
  result: PipelineRunResult | None
  pipeline: PipelineInfo
  created_date: datetime
  finished_date: datetime | None
  template_parameters: dict[str, Any] | None
  variables: dict[str, VariableInfo] | None

PipelineRunRequest
  resources: dict | None
  variables: dict | None
  template_parameters: dict[str, str] | None
  stages_to_skip: list[str] | None
```

### Variable groups

```
VariableGroupInfo
  id: int
  name: str
  description: str | None
  type: str
  variables: dict[str, VariableInfo]
  variable_group_refs: Any         # pass back to update_variable_group unchanged
  created_by: VariableGroupUserInfo
  created_on: datetime
  modified_by: VariableGroupUserInfo
  modified_on: datetime
  is_shared: bool

VariableInfo
  value: str | None                # None for secret variables
  is_secret: bool = False
```

### Pipeline approvals

```
PipelineApproval
  id: str                          # UUID string
  status: PipelineApprovalStatus
  steps: list[PipelineApprovalStep]
  instructions: str | None
  min_required_approvers: int
  created_on: datetime | None
```

### Profile

```
UserProfile
  id: str
  display_name: str
  email_address: str
  public_alias: str
```

### Projects

```
ProjectInfo
  id: UUID
  name: str
  state: str | None
```

---

## Enums and literal types

```python
# Work item
WorkItemField = str          # ADO field reference name, e.g. "System.Title"
WorkItemId = int
WorkItemRelationType = str   # e.g. "System.LinkTypes.Hierarchy-Reverse"

# Git
CommitId = str               # SHA hex string
BranchName = str
RepositoryId = UUID
GitPushChangeType = Literal["add", "edit", "delete", "rename"]

# Builds
BuildStatus = Literal[
    "all", "cancelling", "completed", "inProgress",
    "none", "notStarted", "postponed",
]
BuildResult = Literal[
    "canceled", "failed", "none", "partiallySucceeded", "succeeded",
]
BuildRecordType = Literal[
    "Checkpoint", "Checkpoint.Approval", "Checkpoint.Authorization",
    "Checkpoint.ExtendsCheck", "Phase", "Stage", "Job", "Task",
]

# Pull requests
PullRequestStatus = Literal["active", "abandoned", "completed"]
PullRequestMergeStatus = Literal[
    "notSet", "queued", "conflicts", "succeeded",
    "rejectedByPolicy", "failure",
]
PullRequestThreadStatus = Literal[
    "active", "byDesign", "closed", "fixed", "pending", "unknown", "wontFix",
]
PullRequestStatusState = Literal[
    "error", "failed", "notApplicable", "notSet", "pending", "succeeded",
]
GitPullRequestMergeStrategy = Literal[
    "noFastForward", "squash", "rebase", "rebaseMerge",
]

class PullRequestVote(IntEnum):
    APPROVED = 10
    APPROVED_WITH_SUGGESTIONS = 5
    NO_VOTE = 0
    WAITING_FOR_AUTHOR = -5
    REJECTED = -10

class PullRequestThreadCommentType(IntEnum):
    UNKNOWN = 0
    TEXT = 1
    CODE_CHANGE = 2
    SYSTEM = 3

# Pipelines
PipelineRunState = Literal["unknown", "inProgress", "canceling", "completed"]
PipelineRunResult = Literal["unknown", "succeeded", "failed", "canceled"]
PipelineApprovalStatus = Literal[
    "approved", "canceled", "failed", "pending",
    "rejected", "skipped", "timedOut", "undefined",
]

# Pipeline task callbacks
JobEventName = Literal["TaskCompleted"]
JobEventResult = Literal["succeeded", "failed"]
```

---

## Error handling

All HTTP errors are raised as `RuntimeError` with the ADO error message text
extracted from the response body. JSON parse failures raise `ValueError`.
Connection resets are retried up to 3 times before re-raising
`ConnectionResetError`.

```python
try:
    item = pyado.get_work_item(wi_api)
except RuntimeError as exc:
    print(f"ADO error: {exc}")
```

Pydantic validation errors (`ValidationError`) are raised on construction of
`ApiCall` or any model if the input is structurally invalid.

---

## Gotchas

1. **`VariableGroupInfo.variable_group_refs`** must be passed unchanged to
   `update_variable_group` — it is required by the ADO PUT API to identify the
   project. Do not construct it manually; always read it from the GET response.

2. **Secret variable values** come back as `None` from `iter_variable_group_details`.
   You can write a new secret value but never read it back.

3. **`get_file_content_at_*`** returns `""` for a missing file rather than raising.
   Check for an empty string to detect absence.

4. **Profile API** is on `app.vssps.visualstudio.com`, not `dev.azure.com`.
   You must use `get_profile_api_call(access_token)`, not construct the
   `ApiCall` manually.

5. **`iter_work_item_details`** with `work_item_field_list` does *not* expand
   relations regardless of what fields are requested. To get relations, omit the
   field list and use `get_work_item(wi_api, expand_relations=True)` instead.

6. **`push_commits` and `ZERO_SHA`**: always read the current HEAD SHA via
   `iter_refs` immediately before pushing. If the branch has been updated
   between your read and your push, ADO will reject the push with a conflict.

7. **`create_pr_thread`**: passing `line` without `file_path` raises `ValueError`
   immediately (client-side validation).

8. **`iter_prs` `search_criteria`**: keys are the bare parameter name without
   the `searchCriteria.` prefix. The function adds the prefix automatically.

9. **`post_pipeline_run` vs `start_build`**: both queue a pipeline run, but
   they use different ADO API endpoints with different models. Use
   `post_pipeline_run` + `PipelineRunRequest` for YAML pipelines; use
   `start_build` + `definition_id` for classic (Build Definition) pipelines.

10. **`patch_pr` to complete a PR** requires both `status="completed"` and
    `last_merge_source_commit={"commitId": "<sha>"}` in the
    `PullRequestUpdateRequest` — without the commit SHA, ADO rejects the
    completion request.
