# pyado — Agent Reference

Complete reference for the pyado package. Everything needed to write correct
code without reading the source.

---

## Package overview

`pyado` provides two interfaces over the Azure DevOps REST API:

1. **OOP interface** (`pyado.oop`) — resource objects with methods; the
   recommended entry point. `AzureDevOpsService -> Organization -> Project ->
   Repository / WorkItem / Build / Pipeline / VariableGroup / Team`. Pull
   requests live under `Repository`.
2. **Raw functional interface** (`pyado.raw`) — typed functions that each
   accept an `ApiCall` and return a Pydantic model (never a raw dict).
   Pagination is transparent. All raw symbols are also available from the
   top-level `pyado` package.

```python
import pyado  # raw layer + AzureDevOpsService
from pyado.oop import AzureDevOpsService  # preferred OOP entry point
```

**See also:** [quick_reference.md](quick_reference.md) for a one-page
signature summary; [usage.md](usage.md) for worked examples.

---

## OOP interface

### Quick start

```python
import pyado

svc = pyado.AzureDevOpsService(org="https://dev.azure.com/myorg", pat="<pat>")
# or: AzureDevOpsService()  ->  reads AZURE_DEVOPS_ORG + AZURE_DEVOPS_EXT_PAT
proj = svc.org.get_project("MyProject")

repo = proj.get_repository("myrepo")
pr = repo.create_pull_request("Update config", "feature/branch", "main")
wi = proj.get_work_item(153)
pr.link_work_item(wi)

build = proj.start_build(definition_id=42)
pipeline = proj.get_pipeline(99)
run = pipeline.start_run(template_parameters={"env": "staging"})
```

### AzureDevOpsService

```python
pyado.AzureDevOpsService(
    org: str | None = None,         # falls back to AZURE_DEVOPS_ORG
    pat: str | None = None,         # falls back to AZURE_DEVOPS_EXT_PAT
    credential: TokenCredential | None = None,  # azure-identity; mutually exclusive with pat
)

.org         -> Organization        # singleton, zero-cost
.api_call    -> ApiCall             # org-level; for direct raw calls
.refresh()                         # clear all cached objects
```

### Organization

```python
org = svc.org

.api_call              -> ApiCall
.get_project(name)     -> Project
.iter_projects()       -> Iterator[Project]
.get_connection_data() -> ConnectionData
.get_my_profile()      -> UserProfile
.get_identities(descriptors: list[str]) -> list[IdentityInfo]
.iter_graph_groups()   -> Iterator[GraphGroup]
```

### Project

```text
.name      -> str           # always available, no API call
.id        -> ProjectId     # lazy-fetched on first access
.info      -> ProjectInfo
.api_call  -> ApiCall
.org       -> Organization  # zero-cost
.refresh()

# Repositories
.iter_repositories()         -> Iterator[Repository]
.get_repository(name_or_id)  -> Repository
.iter_active_prs()           -> Iterator[PullRequest]

# Work items
.get_work_item(id)           -> WorkItem
.iter_work_items(wiql)       -> Iterator[WorkItem]
.get_work_items(ids)         -> list[WorkItem]
.create_work_item(type, fields, relations?) -> WorkItem

# Builds
.get_build(id)               -> Build
.iter_builds(*, status_filter?) -> Iterator[Build]
.start_build(definition_id, *, source_branch?, source_version?, parameters?) -> Build

# Pipelines
.get_pipeline(id)            -> Pipeline
.get_pipeline_by_name(name)  -> Pipeline
.iter_pipelines()            -> Iterator[Pipeline]
.iter_pipeline_definitions() -> Iterator[PipelineDefinitionInfo]
.iter_pending_approvals()    -> Iterator[PipelineApproval]
.approve_pipeline(approval_id, *, comment?) -> None
.reject_pipeline(approval_id, *, comment?)  -> None

# Variable groups
.get_variable_group(name)          -> VariableGroup
.get_variable_group_by_id(id)      -> VariableGroup
.iter_variable_groups()            -> Iterator[VariableGroup]
.create_variable_group(name, variables, *, description?, var_group_type?) -> VariableGroup

# Teams
.get_team(name_or_id)  -> Team
.iter_teams()          -> Iterator[Team]

# Iterations / areas / queries
.get_iteration_node(path?, *, depth?) -> Iteration
.create_iteration(name, parent_path?, *, start_date?, finish_date?) -> str (guid)
.iter_sprint_iterations(team_name, *, timeframe_filter?) -> Iterator[SprintIterationInfo]
.add_team_iteration(team_name, iteration_id) -> None
.list_team_field_values(team_name) -> list[TeamFieldValue]
.get_team_field_settings(team_name)  -> TeamFieldSettings  # incl. default path
.get_area_node(path?, *, depth?)   -> Area
.create_area(name, parent_path?)   -> str (guid)
.get_query_tree(*, depth?, expand?) -> WorkItemQuery
.get_query_folder(folder_id, *, depth?, expand?) -> WorkItemQuery
```

### Repository

```text
.id             -> RepositoryId
.name           -> str
.default_branch -> BranchName | None
.web_url        -> ADOUrl
.info           -> RepositoryInfo
.api_call       -> ApiCall
.project        -> Project          # zero-cost
.org            -> Organization     # zero-cost
.refresh()

# Pull requests
.get_pull_request(pull_request_id)         -> PullRequest
.iter_pull_requests(status?)               -> Iterator[PullRequest]
.get_pr_for_branch(source_branch)          -> PullRequest | None
.create_pull_request(title, source_branch, target_branch, *, description?, completion_options?) -> PullRequest

# File access
.get_file_at_branch(path, branch)          -> str   # "" if absent
.get_file_at_commit(path, commit)          -> str   # "" if absent
.get_file_bytes_at_branch(path, branch)    -> bytes | None
.get_file_bytes_at_commit(path, commit)    -> bytes | None

# Refs and branches
.iter_refs(name_filter?, name_contains?)   -> Iterator[GitRef]
.create_branch(name, from_commit)          -> None
.delete_branch(name, current_commit)       -> None
.get_statistics(branch)                    -> BranchStatistics

# Commits and diffs
.iter_commits(*, item_path?, top?, branch?) -> Iterator[Commit]
.get_commit(sha)                            -> Commit
.iter_commit_diff(base, target)             -> Iterator[GitCommitChange]
.get_last_commit_touching_file(path, before_commit) -> CommitId

# Pushes
.commit(branch, message, changes)          -> GitPushResult
.make_ref_update(branch)                   -> GitPushRefUpdate
.push_commits(ref_updates, commits)        -> GitPushResult

# ACL
.get_acl()                                 -> list[AccessControlList]
```

File change helpers (use with `repo.commit` or `pyado.make_commit`):

```python
pyado.AddFile(path, content)  # create a new file
pyado.EditFile(path, content)  # overwrite existing file
pyado.DeleteFile(path)  # delete a file
pyado.RenameFile(old_path, new_path)  # rename without changing content
```

### PullRequest

```text
.id            -> PullRequestId
.title         -> str | None
.status        -> str | None    # "active"|"abandoned"|"completed"
.source_branch -> str | None
.target_branch -> str | None
.description   -> str | None
.created_by    -> str | None    # display name
.info          -> PullRequestListItem | PullRequestCreated
.api_call      -> ApiCall
.repo          -> Repository    # zero-cost
.project       -> Project       # zero-cost
.org           -> Organization  # zero-cost
.refresh()

# Work items
.link_work_item(wi, *, comment?)      # ArtifactLink on the work item
.set_work_item_refs(ids)              # visible in ADO PR page
.iter_work_item_ids()                 -> Iterator[int]

# Labels
.get_labels()           -> list[str]
.add_label(name)
.remove_label(name)

# Threads
.iter_threads()          -> Iterator[PullRequestThreadResponse]
.add_thread(content, *, file_path?, line?, status?) -> PullRequestThreadResponse
.reply_to_thread(thread_id, content, *, parent_comment_id?) -> PullRequestThreadCommentResponse
.update_thread_status(thread_id, status) -> PullRequestThreadResponse

# Reviewers
.get_reviewers()                                  -> list[PullRequestReviewer]
.add_reviewer(reviewer_id, *, is_required?, is_reapprove?)
.remove_reviewer(reviewer_id)
.vote(reviewer_id, vote: PullRequestVote, *, is_reapprove?)

# Status checks
.set_status(state, context_name, *, description?, iteration_id?, target_url?, genre?)
.iter_statuses()  -> Iterator[PullRequestStatusInfo]

# Commits and iterations
.iter_commits()               -> Iterator[GitCommitRef]
.iter_iterations()            -> Iterator[PullRequestIterationRecord]
.get_iteration_changes(iter_id) -> list[PrIterationChange]

# Lifecycle
.update(*, title?, description?, status?, is_draft?)
.enable_auto_complete(identity_id?, *, completion_options?)  # defaults to own identity
.disable_auto_complete()
.complete(last_merge_source_commit, *, completion_options?)
.abandon()
.restart_merge()  # queue new merge attempt; .refresh() later, read .info.merge_status
```

### WorkItem

```text
.id             -> int
.title          -> str | None    # System.Title
.state          -> str | None    # System.State
.type           -> str | None    # System.WorkItemType
.assigned_to    -> Any           # System.AssignedTo (identity dict)
.area_path      -> str | None    # System.AreaPath
.iteration_path -> str | None    # System.IterationPath
.get_field(field) -> Any
.info           -> WorkItemInfo
.api_call       -> ApiCall
.project        -> Project       # zero-cost
.org            -> Organization  # zero-cost
.refresh()

.update(fields, *, multiline_fields_format?)
.get_tags()        -> list[str]
.add_tag(tag)      -> list[str]
.remove_tag(tag)   -> list[str]

.iter_comments()              -> Iterator[WorkItemComment]
.add_comment(text, *, comment_format?) -> WorkItemComment
.update_comment(id, text)     -> WorkItemComment
.delete_comment(id)

.add_attachment(filename, content) -> WorkItemAttachmentRef
.download_attachment(ref)          -> bytes
.iter_attachments()                -> Iterator[WorkItemAttachmentRef]

.add_link(other, link_type, *, comment?)  # WI-to-WI relation
.link_pull_request(pr, *, comment?)
.link_build(build, *, comment?)
.link_commit(repo, commit_id, *, comment?)

.get_parent()      -> WorkItem | None
.iter_children()   -> Iterator[WorkItem]
.iter_linked_work_items(rel_type?) -> Iterator[WorkItem]

.delete()          # soft-delete; restorable from Recycle Bin for 30 days
```

### Build

```text
.id           -> int
.number       -> str           # e.g. "20240101.1"
.status       -> BuildStatus
.result       -> BuildResult | None
.source_branch -> str
.source_version -> str         # commit SHA
.start_time   -> datetime | None
.finish_time  -> datetime | None
.queue_time   -> datetime | None
.requested_by -> str           # display name of the identity that queued the build
.requested_for -> str | None   # display name of the build's target identity
.info         -> BuildDetails
.api_call     -> ApiCall
.pipeline     -> Pipeline       # zero-cost, no API call
.project      -> Project        # zero-cost
.org          -> Organization   # zero-cost
.refresh()

.update(status)    -> None              # set build status directly
.cancel()          -> None
.cancel_run()      -> PipelineRunInfo   # via Pipelines v2
.retry()           -> Build             # same definition and branch

.iter_artifacts()  -> Iterator[BuildArtifact]
.iter_tags()       -> Iterator[str]
.add_tag(tag)      -> list[str]
.remove_tag(tag)   -> list[str]

.iter_timeline_records()  -> Iterator[BuildRecordInfo]
.get_log_text(log_id)     -> str
.iter_logs()              -> Iterator[BuildLogInfo]
.get_all_log_text(*, separator?) -> str

.iter_work_item_ids()                             -> Iterator[int]
.iter_work_items()                                -> Iterator[WorkItem]
.iter_work_items_between(older_build, *, top?)    -> Iterator[WorkItem]
.iter_work_item_ids_between(older_build, *, top?) -> Iterator[int]

```

### TimelineSession

Report progress into one build's timeline from outside the pipeline, for
example from an AWS Lambda or Step Functions execution that fulfils an
agentless `InvokeRESTAPI` step.  Lives in `pyado.oop` (also `pyado`).

```python
from pyado import TimelineSession, LogLines

session = TimelineSession.from_tokens(
    org_name="myorg",
    project_id=project_uuid,  # the UUID: writes reject the project name
    build_id=123,
    admin_token=pat,  # records, feed and logs
    system_token=system_token,  # only needed for complete()
)
step = session.resolve_task("Run workflow")  # find the step by display name
session.feed(step, "execution started")  # live console (job record)

lines = LogLines()
lines.section("Deploy")
with lines.group("Details"):
    lines.add("image: app:1.2")
session.append_log(step, lines.text())  # persistent log

job = session.create_job("Branch A", under=session.native_phase(step))
task = session.create_task("Validate", under=job)
session.append_log(task, "input ok", create=True)
session.finish(task)
session.complete(step)  # System token, before it expires
```

```text
TimelineSession.from_tokens(*, org_name, project_id, build_id, admin_token, system_token=None)

.resolve_task(display_name) -> TimelineTarget     # exactly one Task with that name
.find(name, *, under=None)  -> TimelineTarget     # stateless re-attachment by name
.native_phase(step)         -> TimelineTarget     # the Phase above the step's Job
.plan_id()                  -> UUID
.record_id(key, *, attempt=1) -> UUID             # stable uuid5; changes per build

.create_job(name, *, under, key=None, attempt=1, state=IN_PROGRESS)   # under a Phase
.create_task(name, *, under, key=None, attempt=1, state=IN_PROGRESS)  # under a Job/Task
.set_state(target, *, state=None, result=None, percent=None)
.finish(target, result=SUCCEEDED)
.report_issues(target, issues)        # replaces; the Errors/Warnings tabs read this
.batch()                              # context manager: one PATCH for all writes inside

.feed(step, *lines)                   # live only, job record, never stored
.append_log(target, text, *, create=False, wait=60)
.attach_log(target) -> int
.complete(step, *, succeeded=True)    # System token; raises if it expired
.seconds_until_system_token_expires() -> float | None
```

What the session decides for you (each measured, see quirks 17-27):

* **Hierarchy:** the portal draws Stage -> Job -> Task only, and a dynamic Job
  only under a native Phase.  `create_job` rejects any other parent and
  `create_task` rejects a Phase or Stage parent.
* **Ids:** `record_id(key)` is deterministic, so a retrying Lambda updates the
  same record.  Creating an existing id overwrites it; a rerun of a record that
  already completed needs a new `attempt`, because `result` cannot be cleared.
  An id that belongs to a native record is refused (it would rename it).
  The id comes from the key only: `create_job` / `create_task` default the key
  to the parent id plus the name, but an **explicit key is the whole identity**,
  so the same key under two parents is one record (ADO keeps the first parent
  and nothing appears under the second).
* **Retries:** after a stage retry the old job id is gone, so ids are always
  read from the current timeline and never cached; `resolve_task` and `find`
  re-read it on every call.  Records written under the old attempt move into
  that attempt's sub-timeline (readable with
  `raw.iter_timeline_records(call, timeline_id)`) and are **not drawn**.  A key
  that does not change still names the old record.  You
  normally do **not** have to care: without `key=` the default key holds the parent
  id, which changes with the retried job.  Only an explicit `key=` (or a rerun of a
  completed record) needs the attempt.  Then use
  `session.for_current_attempt(step)` (reads the attempt of the native job) or, in
  a running job, `session.for_attempt(int(os.environ["SYSTEM_JOBATTEMPT"]))`.  Both
  mix the attempt into every id; attempt 1 derives the same ids as a plain session.
* **Credentials:** the admin token does everything except `complete`, which
  only works with the System token (a PAT gets HTTP 500).  The System token
  stops working at issue time + the `timeoutInMinutes` of the job it was issued
  to + 15 minutes (measured on agent jobs, whose script prints the token), so
  `complete` refuses a token with less than 30 seconds left.  Make sure that
  job outlives the workflow; whether the agentless job's own timeout governs a
  token used against it was not measured.  The same job-level timeout is what
  ends an agentless task that is never completed (task `canceled`, job
  `failed`); a *task*-level timeout gives a `failed` task.
* **Logs:** a native task's log may take a few seconds to appear, so
  `append_log` waits; a record you created has none, so pass `create=True`.
* **Issues vs console lines:** `##[error]` lines colour a line and create no
  issue; `report_issues` does.

#### Log formatting helpers

`pyado.oop.pipelines.log_format` builds lines that render the way the portal
documents them: `error`, `warning`, `debug`, `info`, `section`, `command`,
`group(title, lines)`, `ansi(text, Ansi.RED)`, `sanitize`, and the `LogLines`
collector with a `group()` context manager that always writes `##[endgroup]`.
`sanitize` removes carriage returns (they split the line), control characters
and any `##[` marker in user text (rewritten to `##[ `, which renders as plain
text), so a message cannot start, repeat or cut a marker line.  See quirk 26.

Raised on a refused operation: `AzureDevOpsSessionError` (no HTTP request was
made).

---

### Pipeline

```text
.id    -> int        # always known, no API call
.name  -> str        # always known, no API call
.info  -> PipelineInfo   # lazy-fetched
.api_call -> ApiCall
.project  -> Project     # zero-cost
.org      -> Organization # zero-cost
.refresh()

.iter_runs()              -> Iterator[PipelineRun]
.get_run(run_id)          -> PipelineRun
.get_latest_run()         -> PipelineRun | None
.start_run(*, resources?, variables?, template_parameters?, stages_to_skip?) -> PipelineRun
.cancel_run(run_id)       -> PipelineRunInfo
.authorize_resource(resource_type, resource_id, *, authorized?) -> PipelineResourcePermissions
```

### VariableGroup

```text
.id        -> int
.name      -> str
.variables -> dict[str, VariableInfo]
.info      -> VariableGroupInfo
.api_call  -> ApiCall
.project   -> Project       # zero-cost
.org       -> Organization  # zero-cost
.refresh()

.update(variables, *, name?, description?, var_group_type?, provider_data?)
.set_variable(var_name, value, *, is_secret?)  # read-modify-write
.delete_variable(var_name)                     # raises KeyError if absent
.delete()                                      # permanent deletion
```

### Team

```text
.id      -> str   # UUID string
.name    -> str
.info    -> TeamInfo
.api_call -> ApiCall   # team-level (for raw teamsettings functions)
.project -> Project    # zero-cost
.org     -> Organization # zero-cost

.iter_sprint_iterations(*, timeframe_filter?) -> Iterator[SprintIterationInfo]
.list_field_values()    -> list[TeamFieldValue]
.get_field_settings()    -> TeamFieldSettings  # incl. default path
.set_field_settings(settings) -> TeamFieldSettings
.add_iteration(iteration_id) -> None
.iter_members()  -> Iterator[TeamMember]
.get_members()   -> list[TeamMember]
```

### Iteration / Area

```python
# Iteration (from proj.get_iteration_node)
.name        -> str
.id          -> str   # GUID
.path        -> str
.start_date  -> date | None
.finish_date -> date | None
.children    -> list[Iteration]
.project     -> Project

# Area (from proj.get_area_node)
.name     -> str
.id       -> str
.path     -> str
.children -> list[Area]
.project  -> Project
```

### Commit

```python
# Obtained from repo.iter_commits() or repo.get_commit()
.id         -> CommitId      # SHA string
.message    -> str | None
.author     -> ...           # .name, .email, .date
.info       -> GitCommitRef
.repo       -> Repository    # zero-cost
.project    -> Project       # zero-cost
```

---

## The ApiCall object

`ApiCall` is the credential-and-URL object every function takes as its first
argument. It is an immutable Pydantic model.

```python
class ApiCall(BaseModel):
    url: HttpUrl  # must be https://
    session: requests.Session = ...  # default: unauthenticated session
    parameters: dict = {}  # merged into every request as query params
    timeout: int = 10  # request timeout in seconds
```

### Construction

Use `get_session` to create an authenticated session, then pass it to `ApiCall`:

```python
session = pyado.get_session(pat="<pat>")

# Project-level (required by most functions)
api = pyado.ApiCall(
    session=session,
    url="https://dev.azure.com/<org>/<project>/_apis/",
)

# Organisation-level (iter_projects, iter_pull_requests across all repos)
org_api = pyado.ApiCall(
    session=session,
    url="https://dev.azure.com/<org>/_apis/",
)
```

`get_session` accepts one of three mutually-exclusive auth arguments:

```python
pyado.get_session(pat="<personal-access-token>")
pyado.get_session(bearer_token="<oauth-token>")
pyado.get_session(azure_credentials=DefaultAzureCredential())
```

The **profile API** lives on a separate host; use the dedicated helper:

```python
profile_api = pyado.get_profile_api_call(session)
# -> ApiCall(url="https://app.vssps.visualstudio.com/_apis")
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
| `get_profile_api_call(session)` | `requests.Session` | `ApiCall` | different host |
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
| `put_build_tag` | `(build_api, tag: str)` | `list[str]` |
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
  url: HttpUrl
  session: requests.Session   (default: unauthenticated)
  parameters: dict[str, int | str | bool]
  timeout: int
  .build_call(*args, parameters?, version?) -> ApiCall
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
WorkItemField = str  # ADO field reference name, e.g. "System.Title"
WorkItemId = int
WorkItemRelationType = str  # e.g. "System.LinkTypes.Hierarchy-Reverse"

# Git
CommitId = str  # SHA hex string
BranchName = str
RepositoryId = UUID
GitPushChangeType = Literal["add", "edit", "delete", "rename"]

# Builds
BuildStatus = Literal[
    "all",
    "cancelling",
    "completed",
    "inProgress",
    "none",
    "notStarted",
    "postponed",
]
BuildResult = Literal[
    "canceled",
    "failed",
    "none",
    "partiallySucceeded",
    "succeeded",
]
BuildRecordType = Literal[
    "Checkpoint",
    "Checkpoint.Approval",
    "Checkpoint.Authorization",
    "Checkpoint.ExtendsCheck",
    "Phase",
    "Stage",
    "Job",
    "Task",
]

# Pull requests
PullRequestStatus = Literal["active", "abandoned", "completed"]
PullRequestMergeStatus = Literal[
    "notSet",
    "queued",
    "conflicts",
    "succeeded",
    "rejectedByPolicy",
    "failure",
]
PullRequestThreadStatus = Literal[
    "active",
    "byDesign",
    "closed",
    "fixed",
    "pending",
    "unknown",
    "wontFix",
]
PullRequestStatusState = Literal[
    "error",
    "failed",
    "notApplicable",
    "notSet",
    "pending",
    "succeeded",
]
GitPullRequestMergeStrategy = Literal[
    "noFastForward",
    "squash",
    "rebase",
    "rebaseMerge",
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
    "approved",
    "canceled",
    "failed",
    "pending",
    "rejected",
    "skipped",
    "timedOut",
    "undefined",
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
   You must use `get_profile_api_call(session)`, not construct the
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

11. **`issues` is replace-in-full on dynamic records, and `[]` does not clear.**
    Sending a non-empty `issues` list replaces the whole list while the
    record is `inProgress`.  Omitting the field preserves the issues, and
    sending `issues=[]` is silently ignored (it does *not* clear them) — in
    particular on completed dynamic records and on native records.  To add a
    single issue without losing others, read the record's current `issues`,
    append, and PATCH the whole list.

12. **`hub_name` is a plain string `"build"`** for YAML pipelines —
    **lowercase**.  Use the value of `SYSTEM_HOSTTYPE` directly, or
    hard-code `"build"`.  Release Management pipelines use `"rm"`.

13. **`plan_id` equals `timeline_id`** in standard YAML pipelines — they
    share the same UUID.  Pass the value of `SYSTEM_PLANID` (or equivalently
    `SYSTEM_TIMELINEID`) for both constructor parameters.

14. **`SYSTEM_COLLECTIONID` ≠ `SYSTEM_TEAMPROJECTID`.** The distributed-task
    URL must be scoped to the project UUID (`SYSTEM_TEAMPROJECTID`).  Using
    `SYSTEM_COLLECTIONID` (the organisation UUID) silently targets the wrong
    resource and returns HTTP 400 or 404.

15. **Dynamic records have no log attached.**  A record you create has no
    log; a native task already has one.  To write output for your own record:
    POST `plans/{plan_id}/logs` to allocate a log id, PATCH the record's `log`
    field to attach it, then POST to `plans/{plan_id}/logs/{log_id}` to append
    (`TimelineSession.append_log(..., create=True)` does all three).  Feed
    lines never go into a log.

16. **Completing the step does not finish child records.**  `TaskCompleted`
    only unblocks the pipeline.  Records you created and left `inProgress` end
    with the **build's** result when the build ends (`completed`, `failed` in a
    failed build even under a job that succeeded; `pending` ones become
    `abandoned`), so a crashed writer looks successful in a successful build.
    Call `TimelineSession.finish` on each child first.

17. **The `System.AccessToken` expires at issue time + the issuing job's
    `timeoutInMinutes` + 15 minutes** (measured on agent jobs), not after a
    fixed ~20 minutes.  The
    token is a JWT with two expiries: the top-level `exp` (about 24 h 5 min)
    and a nested `xms_attr.<id>.ado_exp`; the nested one governs.  Measured
    for timeouts of 1/2/5/10/20/40/60 minutes: 16/17/20/25/35/55/75 minutes.
    The default 60-minute timeout therefore gives about 75 minutes.  Decode
    the nested claim (recursively) to read it; a top-level-only decode misses
    it.

18. **Past the nested expiry every call returns HTTP 401**, reads included,
    while the PAT keeps working.  The token is not tied to the build: it kept
    working for about 10 minutes after its build had ended.  A long-running
    external workflow must therefore send everything that needs the System
    token (see 19) before the expiry, or obtain a fresh token.

19. **`TaskCompleted` needs the System token.**  With a PAT it fails with
    HTTP 500 ("session not found"); with the System token it returns 204 and
    the pipeline continues.  Use `task_id=record.id` and
    `job_id=record.parent_id` of the step's own timeline record.  For an
    `InvokeRESTAPI` step on a `server` job, find that record by its display
    name: `SYSTEM_TASKINSTANCEID` is not reliably set and `SYSTEM_JOBID` is not
    that step's job.

20. **Feed goes to the Job record, not the Task record.**  Post to
    `.../records/{job_id}/feed`.  It renders live in the open pipeline view
    within ~0.2 s and is never stored: a reload or navigation discards it.
    Posting to the task record is accepted (204) but shows up late and in
    batches.

21. **A native task already has its log attached** when it first shows
    `inProgress`; a record you create has none.  For your own records, the
    allocate / attach / append order is not enforced: an append before the
    attach is accepted and kept.  Parallel appends are all kept but their
    order is not preserved.  Appended text renders in the portal after a
    reload, not live.

22. **Log appends must use `Content-Type: application/octet-stream` to work
    with a PAT.**  `text/plain` and `application/json` return HTTP 400 for a
    PAT, while the System token accepts all three.  `post_job_logs` already
    sends `octet-stream`.

23. **Writes are last-writer-wins.**  Parallel PATCHes of one record all
    return 200 and the last one stands (no merge of `issues`); the same `id`
    twice in one batch returns HTTP 500; `parent_id` cannot be changed (the
    PATCH returns 200 and is ignored).  A non-empty `issues` list replaces the
    existing list on native records too; `[]` is ignored.  One PATCH accepted
    2000 records.

24. **Which dynamic records the portal draws** (Stage -> Job -> Task only):
    a Task under any Job (also a finished or another job) is shown; a Job
    under a *native Phase* is shown with its tasks (parallel jobs work); a Job
    under a Stage or under another Job gets no row and its tasks appear one
    level up; a Phase, a Task under a Phase or Stage, and Job > Job > Job > Job
    are not drawn.  **A dynamic Stage record is stored, has no row and makes
    the build's results page show "Build not found"** (no summary, tabs or
    Errors/Warnings), also after the build ends; never write one.  A Job under
    a native Phase is also listed on the stage card and in the Jobs tab.  Task
    nesting is drawn two levels deep.  Status changes repaint within ~0.5 s with
    no reload, in any direction.


25. **Records are addressed by id and creating an existing id overwrites it.**
    A PATCH that carries an existing `id` updates that record's name and state
    (no duplicate, also under parallel calls, and regardless of upper/lower
    case); `type` and `parent_id` stay as first created.  A partial PATCH for
    an id that does not exist returns HTTP 400, so a new record needs a full
    body (`name`, `type`, `parent_id`, `state`).  A re-created record keeps its
    old `result` (`null` does not clear it), so give a rerun a new id.  A
    native record's id is not protected **by ADO**: writing it renames the
    native record (`TimelineSession` refuses such an id).

26. **Console lines are formatting only.**  `##[error]` / `##[warning]` colour a
    line (red / orange; `##[debug]` purple, `##[info]` grey), `##[group]` folds
    the lines up to `##[endgroup]`, and ANSI colour codes work.  The log and the
    feed use the same renderer.  None of this creates an issue: `##[error]`,
    `##[warning]` and `##vso[task.logissue ...]` leave the error and warning
    counts and the Errors/Warnings tabs unchanged, and other `##vso[...]`
    commands are shown as plain text.  Only the record's `issues` field
    reports problems.  Keep `##[section]`, `##[command]` and `##[group]` at the very start of the
    line and use each at most once per line: they hide their marker and keep
    the rest, but anything before the marker makes the viewer cut about nine
    characters, and a second marker of the same type later in the line cuts
    the text before it.  `##[error]`, `##[warning]`, `##[debug]` and
    `##[info]` can appear anywhere.  Carriage returns split the line and
    256-colour ANSI codes are ignored.

27. **After a stage retry the old job and its records are gone from the
    current timeline.**  The retried stage gets new job and task ids; the old
    ones move into a sub-timeline listed in `previous_attempts`.  A writer
    that cached the old job id still gets HTTP 200 but the record lands under
    the swept job and is never shown, so re-resolve the job id for every call.
    Chosen record ids from the earlier attempt can be created again under the
    new job.
