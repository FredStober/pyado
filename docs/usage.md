# Usage Guide

This guide covers every part of the pyado public API. It is organised by domain.
Each section explains what the functions do and why you would use them before
showing the code.

**See also:**
[API reference](reference.md) ·
[Quick reference](quick_reference.md) ·
[Alternatives](alternatives.md) ·
[Contributor guide](contributing.md)

> **Why not the official `azure-devops` package?**
> Microsoft's auto-generated client surfaces models typed as `object`, omits
> pagination handling on many endpoints, and requires a separate
> `azure-identity` or `azure-devops` connection object for authentication.
> pyado replaces all of that with one `ApiCall` model, Pydantic-validated inputs
> and outputs on every function, and transparent pagination built into every
> iterator. See the [alternatives comparison](alternatives.md) for a full
> side-by-side overview.

**Contents:**
[Quick start](#quick-start) ·
[OOP interface](#oop-interface) ·
[ApiCall](#the-apicall-object) ·
[Work items](#work-items) ·
[Pull requests](#pull-requests) ·
[Repository](#repository) ·
[Git push](#git-push) ·
[Builds](#builds) ·
[Pipeline task callbacks](#pipeline-task-callbacks) ·
[Pipeline runs (YAML)](#pipeline-runs-yaml-pipelines) ·
[Projects](#projects) ·
[Variable groups](#variable-groups) ·
[Profile](#profile)

---

## Quick start

Install pyado and run the five most common operations in under a minute.

```console
$ pip install pyado
```

Set your credentials in the environment — every ADO personal access token
(PAT) works:

```console
$ export AZURE_DEVOPS_ORG=https://dev.azure.com/myorg
$ export AZURE_DEVOPS_EXT_PAT=<your-pat>
```

```python
import pyado

svc  = pyado.AzureDevOpsService()              # reads env vars
proj = svc.org.get_project("MyProject")

# 1. Read a work item
wi = proj.get_work_item(42)
print(wi.title, wi.state)

# 2. Update a work item
wi.update({"System.State": "Resolved"})

# 3. List active pull requests
for pr in proj.iter_active_prs():
    print(pr.repo.name, pr.title, pr.status)

# 4. Queue a build
build = proj.start_build(definition_id=10)
print(build.id, build.number)

# 5. Read a file from a repository
repo = proj.get_repository("backend")
content = repo.get_file_at_branch("/pyproject.toml", "main")
print(content[:200])
```

All five examples above work identically in CI/CD pipelines — the
`SYSTEM_TEAMFOUNDATIONCOLLECTIONURI` and `SYSTEM_ACCESSTOKEN` variables that
ADO injects into agent jobs are recognised automatically.

---

## OOP interface

The OOP layer (`pyado.oop`, re-exported from the top-level `pyado` package)
wraps every ADO resource as a Python object. Instead of constructing `ApiCall`
objects yourself, you navigate a hierarchy: `AzureDevOpsService →
Organization → Project → Repository / WorkItem / Build / Pipeline /
VariableGroup / Team`. Pull requests live under `Repository`. Back-navigation
(`build.project`, `pr.repo.org`, etc.) is always zero-cost.

Objects obtained from different factory paths share identity when they
represent the same ADO resource: `build.project is wi.project` is guaranteed.

Enum types and Pydantic models used as arguments to OOP methods come from
`pyado.raw`:

```python
from pyado.raw import (
    PullRequestVote,
    PullRequestStatusState,
    PullRequestStatusContext,
    PullRequestThreadStatus,
    WorkItemRelationType,
    PipelineResourceType,
    SprintIterationTimeframe,
    VariableInfo,
)
```

### Authentication and construction

```python
import pyado

# Explicit credentials
svc = pyado.AzureDevOpsService(
    org="https://dev.azure.com/myorg",
    pat="<personal-access-token>",
)

# From environment variables (AZURE_DEVOPS_ORG or SYSTEM_TEAMFOUNDATIONCOLLECTIONURI,
# plus AZURE_DEVOPS_EXT_PAT)
svc = pyado.AzureDevOpsService()

# Azure identity / managed identity (any azure-identity TokenCredential)
from azure.identity import DefaultAzureCredential
svc = pyado.AzureDevOpsService(
    org="https://dev.azure.com/myorg",
    credential=DefaultAzureCredential(),
)

# Navigate to a project
org  = svc.org
proj = org.get_project("MyProject")
```

### Organization

```python
org = svc.org

# List all projects
for project in org.iter_projects():
    print(project.name, project.id)

# Connection metadata (confirms auth, returns org info)
data = org.get_connection_data()
print(data.authenticated_user.provider_display_name)

# Authenticated user's profile
me = org.get_my_profile()
print(me.display_name, me.email_address)

# Identity lookups
groups = list(org.iter_graph_groups())
identities = org.get_identities([g.descriptor for g in groups[:3]])
```

### Project

```python
proj = org.get_project("MyProject")
print(proj.name, proj.id)

# Force a fresh fetch
proj.refresh()

# Access the owning org — zero API calls
assert proj.org is org
```

### Repository

```python
repo = proj.get_repository("myrepo")     # by name or UUID string
print(repo.name, repo.default_branch, repo.web_url)

# List all repos
for repo in proj.iter_repositories():
    print(repo.name)

# File content
text = repo.get_file_at_branch("/config.json", "main")
text = repo.get_file_at_commit("/config.json", "abc123")
raw_bytes = repo.get_file_bytes_at_branch("/image.png", "main")

# Git refs
for ref in repo.iter_refs(name_filter="heads/release/"):
    print(ref.name, ref.object_id)

# Branch management
repo.create_branch("feature/new-branch", from_commit="abc123")
repo.delete_branch("feature/old-branch", current_commit="def456")

# Single-file commit helpers
repo.delete_file("main", "/old_config.json", "chore: remove old config")
repo.rename_file("main", "/a.json", "/b.json", "refactor: rename config")

# Ahead/behind statistics
stats = repo.get_statistics("feature/my-branch")
print(stats.ahead_count, stats.behind_count)

# Commits
for commit in repo.iter_commits(branch="main", top=10):
    print(commit.id, commit.message)
commit = repo.get_commit("abc123")

# Diff between two commits
for change in repo.iter_commit_diff("abc123", "def456"):
    print(change.change_type, change.item.path)

# ACL
acl = repo.get_acl()
```

### Committing files

```python
from pyado import AddFile, EditFile, DeleteFile, RenameFile

# Push a single commit (fetches current HEAD automatically)
result = repo.commit("main", "chore: update config", [
    EditFile("/config.json", '{"key": "value"}'),
    DeleteFile("/old_config.json"),
    AddFile("/new_file.txt", "hello"),
    RenameFile("/a.json", "/b.json"),
])
print(result.commits[0].commit_id)

# Advanced: build ref updates and commits manually
ref_update = repo.make_ref_update("main")   # fetches current HEAD
result = repo.push_commits([ref_update], [pyado.make_commit("msg", [...])])
```

### Pull Request

```python
# Create
pr = repo.create_pull_request(
    title="Update config",
    source_branch="feature/update-config",
    target_branch="main",
    description="Fixes #123.",
)

# Fetch existing
pr = repo.get_pull_request(42)

# List
for pr in repo.iter_pull_requests():    # active by default
    print(pr.id, pr.title, pr.status)

for pr in proj.iter_active_prs():       # across all repos in the project
    print(pr.repo.name, pr.title)

# Find PR by source branch
pr = repo.get_pr_for_branch("feature/my-branch")   # None if not found

# Properties (no API call)
print(pr.id, pr.title, pr.status, pr.source_branch, pr.target_branch)
print(pr.created_by, pr.description)

# Re-fetch
pr.refresh()

# Back-navigation — zero API calls
assert pr.repo is repo
assert pr.project is proj

# Labels
pr.add_label("ready-to-merge")
pr.remove_label("do-not-merge")
labels = pr.get_labels()

# Reviewers
pr.add_reviewer("<identity-id>", is_required=True)
pr.remove_reviewer("<identity-id>")
pr.vote("<identity-id>", PullRequestVote.APPROVED)
reviewers = pr.get_reviewers()

# Threads (review comments)
thread = pr.add_thread(
    "This import is unused.",
    file_path="/src/foo.py",
    line=42,
)
pr.reply_to_thread(thread.id, "Fixed in the latest push.")
pr.update_thread_status(thread.id, PullRequestThreadStatus.FIXED)
thread = pr.get_thread(thread.id)        # fetch a single thread by ID
for thread in pr.iter_threads():
    print(thread.status, thread.comments[0].content)

# Work item association
pr.link_work_item(wi)                         # artifact link on the work item
pr.set_work_item_refs([wi.id])                # visible in the ADO PR page
for wi_id in pr.iter_work_item_ids():
    print(wi_id)

# Status checks
pr.set_status(
    PullRequestStatusState.SUCCEEDED,
    "ci/integration-tests",
    description="All 142 tests passed",
)
for status in pr.iter_statuses():
    print(status.context.name, status.state)

# Commits and iterations
for commit in pr.iter_commits():
    print(commit.commit_id, commit.comment)
for iteration in pr.iter_iterations():
    changes = pr.get_iteration_changes(iteration.id)

# Lifecycle
pr.update(title="New title", is_draft=False)
pr.enable_auto_complete()                 # uses own identity automatically
pr.enable_auto_complete("<identity-id>")  # or pass an explicit identity
pr.disable_auto_complete()
pr.complete(last_merge_source_commit="<sha>")
pr.abandon()
```

### WorkItem

```python
wi = proj.get_work_item(153)

# Properties (no API call after construction)
print(wi.id, wi.title, wi.state, wi.type)
print(wi.area_path, wi.iteration_path, wi.assigned_to)
print(wi.get_field("Microsoft.VSTS.Common.Priority"))

# Iterate by WIQL
for wi in proj.iter_work_items(
    "SELECT [System.Id] FROM WorkItems WHERE [System.State] = 'Active'"
):
    print(wi.title)

# Batch fetch (efficient when you have IDs already)
items = proj.get_work_items([123, 456, 789])

# Create
wi = proj.create_work_item(
    "Task",
    fields={
        "System.Title": "Investigate memory leak",
        "System.AssignedTo": "jane@example.com",
    },
)

# Update
wi.update({"System.State": "Resolved"})
wi.update(
    {"System.Description": "## Fix\nSee PR #42."},
    multiline_fields_format={"System.Description": "markdown"},
)
wi.refresh()

# Tags
wi.add_tag("reviewed")
wi.remove_tag("needs-work")
tags = wi.get_tags()

# Comments
comment = wi.add_comment("Confirmed in staging.", comment_format="markdown")
wi.update_comment(comment.id, "Confirmed — closing.")
wi.delete_comment(comment.id)
for comment in wi.iter_comments():
    print(comment.created_by.display_name, comment.text)

# Attachments
ref = wi.add_attachment("report.html", open("report.html", "rb").read())
print(ref.url)

# Links between work items
parent = wi.get_parent()
for child in wi.iter_children():
    print(child.title)
wi.add_link(other_wi, WorkItemRelationType.CHILD)
for rel in wi.iter_relations():
    print(rel.rel, rel.url)
wi.remove_link(rel)   # remove by matching rel + url

# Artifact links
wi.link_pull_request(pr)
wi.link_build(build)
wi.link_commit(repo, "abc123")

# Move to a different iteration or area
wi.move(iteration_path="MyProject\\Sprint 42")
wi.move(area_path="MyProject\\Team A")
wi.move(iteration_path="MyProject\\Sprint 42", area_path="MyProject\\Team A")

# Delete (soft — restorable from Recycle Bin for 30 days)
wi.delete()
```

### Build

```python
build = proj.get_build(456)

# Properties
print(build.id, build.number, build.status, build.result)
print(build.source_branch, build.source_version)
print(build.start_time, build.finish_time, build.queue_time)
print(build.requested_by, build.requested_for)

# Pipeline definition back-reference — zero API calls
print(build.pipeline.name)

# List builds
for build in proj.iter_builds(status_filter="completed"):
    print(build.id, build.result)

# Queue a new build
build = proj.start_build(
    definition_id=42,
    source_branch="refs/heads/main",
    parameters={"env": "staging"},
)

# Retry with the same definition and branch
new_build = build.retry()

# Re-fetch
build.refresh()

# Lifecycle
build.update(BuildStatus.CANCELLING)   # set build status directly
build.cancel()
build.cancel_run()   # cancel via Pipelines v2; returns PipelineRunInfo

# Tags
build.add_tag("release-candidate")
build.remove_tag("release-candidate")
for tag in build.iter_tags():
    print(tag)

# Artifacts
for artifact in build.iter_artifacts():
    print(artifact.name, artifact.resource.download_url)

# Timeline — stages, jobs, tasks
for stage in build.iter_stages():
    print(stage.name, stage.result)
    for job in stage.iter_jobs():
        for task in job.iter_tasks():
            print(task.name, task.result)
            log = build.get_log_text(task.log.id)

# Logs
for log_info in build.iter_logs():
    print(log_info.id)
all_text = build.get_all_log_text()          # concatenates every log with "\n"
all_text = build.get_all_log_text(separator="\n---\n")

# Work items
for wi_id in build.iter_work_item_ids():
    print(wi_id)
for wi_id in build.iter_work_item_ids_between(older_build):   # returns IDs
    print(wi_id)
for wi in build.iter_changes_between(older_build, top=50):    # returns WorkItem objects
    print(wi.title)

# Serverless / external task integration
active_task = build.get_active_build_task(
    hub_name="build",
    plan_id=plan_uuid,
    timeline_id=timeline_uuid,
    job_id=job_uuid,
    task_instance_id=task_uuid,
)
```

### Pipeline

```python
pipeline = proj.get_pipeline(99)
pipeline = proj.get_pipeline_by_name("deploy-prod")   # by name
print(pipeline.id, pipeline.name)

# List
for pipeline in proj.iter_pipelines():
    print(pipeline.id, pipeline.name)

# Runs
run = pipeline.start_run(
    template_parameters={"env": "staging", "run_smoke_tests": "true"},
    stages_to_skip=["deploy-prod"],
)
run = pipeline.get_run(run_id=1)
for run in pipeline.iter_runs():
    print(run.id, run.state, run.result)
latest = pipeline.get_latest_run()

# Resource permissions
pipeline.authorize_resource(
    PipelineResourceType.VARIABLE_GROUP,
    resource_id="42",
)

# Approvals (project-level)
for approval in proj.iter_pending_approvals():
    print(approval.id, approval.status)
proj.approve_pipeline(approval.id, comment="LGTM")
proj.reject_pipeline(approval.id, comment="Not ready")
```

### VariableGroup

```python
vg = proj.get_variable_group("my-group")
print(vg.id, vg.name)
for name, info in vg.variables.items():
    print(f"  {name} = {info.value!r}  (secret: {info.is_secret})")

# Set a single variable (read-modify-write)
vg.set_variable("MY_VAR", "new-value")
vg.set_variable("SECRET_VAR", "secret", is_secret=True)

# Delete a variable
vg.delete_variable("OLD_VAR")

# Replace the whole variable map
vg.update({
    **vg.variables,
    "MY_VAR": VariableInfo(value="updated"),
})
vg.refresh()

# Create a new variable group
new_vg = proj.create_variable_group(
    "my-new-group",
    {"ENV": VariableInfo(value="prod")},
    description="Production settings",
)

# Permanently delete a variable group
vg.delete()
```

### Team

```python
team = proj.get_team("Backend Team")
print(team.id, team.name)
for team in proj.iter_teams():
    print(team.name)

# Sprint iterations
for sprint in team.iter_sprint_iterations():
    print(sprint.name, sprint.attributes.start_date)
for sprint in team.iter_sprint_iterations(
    timeframe_filter=SprintIterationTimeframe.CURRENT
):
    print(sprint.name)

# Area path configuration
field_values = team.get_field_values()

# Assign iteration to team
team.add_iteration(iteration_id)

# Members
for member in team.iter_members():
    print(member.identity.display_name)
members = team.get_members()   # returns a list
```

### Iteration and Area nodes

```python
# Iteration tree
root = proj.get_iteration_node(depth=2)
for child in root.children:
    print(child.name, child.start_date, child.finish_date)

# Create an iteration
guid = proj.create_iteration(
    "Sprint 42",
    parent_path=None,
    start_date=date(2025, 1, 1),
    finish_date=date(2025, 1, 14),
)
proj.add_team_iteration("Backend Team", guid)

# Area tree
root = proj.get_area_node(depth=2)
for child in root.children:
    print(child.name)

guid = proj.create_area("New Area", parent_path=None)

# Assign an iteration node to a team (convenience — equivalent to team.add_iteration)
iteration = proj.get_iteration_node()
iteration.add_to_team(team)
```

### WIT query folders

```python
tree = proj.get_query_tree(depth=2)
folder = proj.get_query_folder(folder_id="<uuid>", depth=1)
```

---

## The ApiCall object

> **Raw API:** All functions in this section and below live in `pyado.raw`.
> Import with `from pyado.raw import ApiCall, ...` or `import pyado.raw`.

`ApiCall` is the single credential and URL object that every raw function
accepts as its first argument. It is an immutable [Pydantic] `BaseModel`, so
bad inputs (wrong URL scheme, missing token) are caught immediately on
construction rather than when the first API call fires.

[Pydantic]: https://docs.pydantic.dev/

```python
from pyado.raw import ApiCall

# Project-level — used by the vast majority of functions
api = ApiCall(
    access_token="<your-pat>",
    url="https://dev.azure.com/<organisation>/<project>/_apis/",
)

# Organisation-level — needed for iter_projects and cross-project PR listing
org_api = ApiCall(
    access_token="<your-pat>",
    url="https://dev.azure.com/<organisation>/_apis/",
)
```

### Scoped API calls

Most `get_*_api_call` helpers derive a scoped `ApiCall` that points at a
specific resource (a repository, a work item, a build, …). Under the hood they
call `build_call()`, which appends path segments and merges query parameters
while keeping the same token.

`ApiCall` is an immutable Pydantic model — `build_call` always returns a *new*
`ApiCall` and never modifies the original.  This makes it safe to derive
multiple scoped calls from a single parent and use them concurrently.

```python
from pyado.raw import (
    get_repository_api_call,
    get_work_item_api_call,
    get_build_api_call,
    get_pr_api_call,
)

repo_api  = get_repository_api_call(api, repo_id)   # → …/git/repositories/{id}
wi_api    = get_work_item_api_call(api, 123)         # → …/wit/workitems/123
build_api = get_build_api_call(api, build_id=1234)   # → …/build/builds/1234
pr_api    = get_pr_api_call(api, repo_id, pr_id=42)  # → …/git/pullrequests/42
```

You can also call `build_call()` yourself if you need a custom scoped call:

```python
custom = api.build_call("wit", "workitems", 42, version="7.0")
```

### Personal access tokens

pyado uses [HTTP Basic auth][pat] with an empty username and the PAT as the
password, which is what ADO expects. The session is cached per token so
connection overhead is shared across multiple calls.

> **Session reuse.** `ApiCall` holds no HTTP state itself — state lives in the
> cached `requests.Session` keyed on the access token.  Constructing a new
> `ApiCall` with the same token reuses the same underlying TCP connection pool,
> so there is no penalty for building derived `ApiCall` objects via `build_call`
> or the `get_*_api_call` helpers.

[pat]: https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate

### Profile API call

The user-profile endpoint lives on a completely different host
(`app.vssps.visualstudio.com`) and cannot be derived from a project-level
`ApiCall`. Use the dedicated helper:

```python
from pyado.raw import get_profile_api_call

profile_api = get_profile_api_call(access_token="<your-pat>")
```

---

## Work items

### Fetching work items

`post_work_items_batch` fetches full work item data in one request (up to 200
IDs per call, the ADO API limit):

```python
from pyado.raw import ApiCall, get_work_item_api_call, get_work_item, post_work_items_batch

items = post_work_items_batch(api, ids=[123, 456, 789])
for item in items:
    print(item.id, item.fields["System.Title"], item.fields.get("System.State"))
```

To fetch a single item and include its relations (parent links, attached files, …):

```python
wi_api = get_work_item_api_call(api, 123)
item = get_work_item(wi_api, expand_relations=True)

for relation in item.relations or []:
    print(relation.rel, relation.url)
```

To limit which fields come back (useful for large batches where you only need
a few columns):

```python
items = post_work_items_batch(api, ids=ids, fields=["System.Id", "System.Title"])
for item in items:
    print(item.id, item.fields["System.Title"])
```

### Querying with WIQL

WIQL (Work Item Query Language) is ADO's SQL-like query language. Use
`post_wiql` to run a query and get back a list of `WorkItemRef` objects. The
refs only contain IDs; pass them to `post_work_items_batch` to get full data:

```python
from pyado.raw import post_wiql, post_work_items_batch

refs = post_wiql(
    api,
    "SELECT [System.Id] FROM WorkItems "
    "WHERE [System.TeamProject] = @project "
    "  AND [System.State] = 'Active' "
    "ORDER BY [System.CreatedDate] DESC",
)
ids = [ref.id for ref in refs]
for item in post_work_items_batch(api, ids=ids):
    print(item.id, item.fields["System.Title"])
```

### Creating work items

`post_work_item` requires at minimum `"System.WorkItemType"` in the `fields`
dict. Every other ADO field reference name is optional. Optionally attach
relations (parent links, artifact links, …) at creation time:

```python
from pyado.raw import post_work_item, WorkItemRelation

task = post_work_item(
    api,
    work_item_type="Task",
    fields={
        "System.Title": "Investigate memory leak",
        "System.Description": "Heap grows unbounded under load.",
        "System.AreaPath": "MyProject\\Backend",
        "System.AssignedTo": "jane@example.com",
    },
    relations=[
        WorkItemRelation(
            rel="System.LinkTypes.Hierarchy-Reverse",   # parent link
            url="https://dev.azure.com/org/project/_workitems/edit/100",
        )
    ],
)
print(f"Created #{task.id}")
```

### Updating work items

`patch_work_item` takes a dict of field reference names to new values. Use
`multiline_fields_format` to tell ADO to render a text field as markdown.

> **Why the unusual API shape?** ADO's Work Item Tracking API uses [JSON Patch]
> (RFC 6902) for all mutations — not a regular JSON body.  Every field value and
> every relation is expressed as an `{"op": "add", "path": "/fields/…", "value": …}`
> operation.  pyado constructs the patch document from the plain `fields` dict so
> callers never have to think about the protocol.  The `multiline_fields_format`
> parameter adds additional patch operations of the form
> `/multilineFieldsFormat/<field>` that tell ADO which format to use when
> rendering multiline text in the UI.

[JSON Patch]: https://jsonpatch.com/

```python
from pyado.raw import get_work_item_api_call, patch_work_item

wi_api = get_work_item_api_call(api, 123)

patch_work_item(
    wi_api,
    fields={
        "System.State": "Resolved",
        "System.Description": "## Fix\nReverted the offending commit.",
    },
    multiline_fields_format={"System.Description": "markdown"},
)
```

### Tags

Tags on a work item are stored internally as a semicolon-and-space-separated
string in the `System.Tags` field (e.g. `"bug; hotfix; reviewed"`). Read the
current tags from `item.fields["System.Tags"]` and write them back with
`patch_work_item`:

```python
from pyado.raw import get_work_item_api_call, get_work_item, patch_work_item

wi_api = get_work_item_api_call(api, 123)

# Read
item = get_work_item(wi_api)
current_tags = [t.strip() for t in (item.fields.get("System.Tags") or "").split(";") if t.strip()]

# Add a tag (case-insensitive dedup)
if "reviewed" not in [t.lower() for t in current_tags]:
    current_tags.append("reviewed")
patch_work_item(wi_api, fields={"System.Tags": "; ".join(current_tags)})
```

> **OOP shortcut:** `wi.add_tag("reviewed")` and `wi.remove_tag("hotfix")` on
> a `WorkItem` object do this automatically.

### Comments

Comments support plain text and markdown:

```python
from pyado.raw import get_work_item_api_call, iter_work_item_comments, post_work_item_comment

wi_api = get_work_item_api_call(api, 123)

# Read all comments
for comment in iter_work_item_comments(wi_api):
    print(comment.created_by.display_name, comment.text)

# Post a new comment
post_work_item_comment(
    wi_api,
    "Confirmed in staging. Closing.",
    comment_format="markdown",
)
```

### Attaching files

Attachment is a two-step operation. First, upload the file bytes to ADO's
attachment store (returns a permanent URL). Then add an `AttachedFile` relation
to the work item via a patch.

> **Partial failure.** If the second step fails after the file has already been
> uploaded, the file exists in the attachment store but is not linked to any work
> item.  Retrying the call uploads a second copy — ADO does not de-duplicate by
> content.  The orphaned upload does no harm; it is simply inaccessible.

```python
import pathlib
from pyado.raw import get_work_item_api_call, post_work_item_attachment_upload, patch_work_item, WorkItemRelation

wi_api = get_work_item_api_call(api, 123)
report = pathlib.Path("report.html").read_bytes()

# Step 1 — upload
ref = post_work_item_attachment_upload(api, filename="report.html", content=report)
print(ref.url)  # permanent download URL

# Step 2 — link to the work item
patch_work_item(
    wi_api,
    relations=[WorkItemRelation(rel="AttachedFile", url=ref.url, attributes={"comment": "Test report"})],
)
```

> **OOP shortcut:** `wi.add_attachment("report.html", content)` does both steps atomically.

### Linking a pull request to a work item

ADO's artifact URL format for a pull request is
`vstfs:///Git/PullRequestId/{project_id}%2F{repo_id}%2F{pr_id}`.
Add an `ArtifactLink` relation via `patch_work_item`:

```python
from pyado.raw import get_work_item_api_call, patch_work_item, WorkItemRelation

artifact_url = (
    f"vstfs:///Git/PullRequestId/"
    f"{project_id}%2F{repo_id}%2F{pr_id}"
)
wi_api = get_work_item_api_call(api, work_item_id)
patch_work_item(
    wi_api,
    relations=[WorkItemRelation(rel="ArtifactLink", url=artifact_url, attributes={"comment": "PR that fixes this"})],
)
```

> **OOP shortcut:** `wi.link_pull_request(pr)` constructs the artifact URL and
> patches the relation automatically.

### Sprint iterations

```python
from pyado.raw import iter_sprint_iterations

# All sprints for the default team
for sprint in iter_sprint_iterations(api):
    print(sprint.name, sprint.attributes.start_date, sprint.attributes.finish_date)

# Only the current sprint
for sprint in iter_sprint_iterations(api, timeframe_filter="current"):
    print(sprint.name)
```

---

## Pull requests

### Scoped API calls

Most PR functions take either a project-level `ApiCall` or a PR-level one.
Derive the PR-level call once and reuse it:

```python
import uuid
from pyado.raw import RepositoryId, get_repository_api_call, get_pr_api_call

repo_id: RepositoryId = uuid.UUID("<repository-uuid>")
repo_api = get_repository_api_call(api, repo_id)
pr_api   = get_pr_api_call(api, repo_id, pr_id=42)
```

### Listing PRs

```python
from pyado.raw import iter_prs, iter_pr_commits

# All active PRs (filtered by status)
for pr in iter_prs(api, {"status": "active"}):
    print(pr.pr_id, pr.repository.name, pr.title)

# Filtered listing — any query parameter the ADO API accepts
for pr in iter_prs(api, {"status": "active", "creatorId": "<identity-uuid>"}):
    print(pr.pr_id, pr.title)

# Commits on a PR
for commit in iter_pr_commits(pr_api):
    print(commit.commit_id, commit.comment)
```

### Creating and updating PRs

`post_pull_request` creates a PR from a `PullRequestCreateRequest` model.
Branch names must use the full `"refs/heads/..."` format:

```python
from pyado.raw import post_pull_request, patch_pr, PullRequestCreateRequest, PullRequestUpdateRequest

pr = post_pull_request(
    repo_api,
    PullRequestCreateRequest(
        title="Add telemetry to the data pipeline",
        source_ref_name="refs/heads/feature/telemetry",
        target_ref_name="refs/heads/main",
        description="Implements #123 — adds structured logging throughout.",
    ),
)
print(f"PR #{pr.pull_request_id}: {pr.url}")

# Update title or description after creation
patch_pr(pr_api, PullRequestUpdateRequest(title="Updated title"))
```

> **OOP shortcut:** `repo.create_pull_request(title=..., source_branch="feature/telemetry", target_branch="main")`
> normalises branch names automatically and accepts plain `"feature/telemetry"` syntax.

### Work items linked to a PR

```python
from pyado.raw import iter_pr_work_item_ids

for wi_id in iter_pr_work_item_ids(pr_api):
    print(wi_id)
```

### Labels

Labels are free-form strings attached to a PR. They are commonly used to
signal state (e.g. `"ready-to-merge"`, `"do-not-merge"`, `"needs-review"`):

```python
from pyado.raw import get_pr_labels_details, post_pr_label, delete_pr_label

# Read
labels = get_pr_labels_details(pr_api)    # → list[PullRequestLabel]

# Add
post_pr_label(pr_api, "ready-to-merge")

# Remove
delete_pr_label(pr_api, "needs-review")
```

### Review threads

A review thread anchors a conversation to an optional file and line. Threads
without a file path are PR-level comments:

```python
from pyado.raw import (
    iter_pr_threads,
    post_pr_new_thread,
    post_pr_thread_comment,
    PullRequestThreadRequest,
    PullRequestThreadContext,
    PullRequestThreadPosition,
    PullRequestThreadCommentRequest,
)

# Read all threads
for thread in iter_pr_threads(pr_api):
    print(f"Thread {thread.id} ({thread.status})")
    for comment in thread.comments:
        print(f"  {comment.author.display_name}: {comment.content}")

# Create a file-level thread
thread = post_pr_new_thread(
    pr_api,
    PullRequestThreadRequest(
        comments=[PullRequestThreadCommentRequest(content="This import is unused.")],
        thread_context=PullRequestThreadContext(
            file_path="/src/pyado/raw/git.py",
            right_file_start=PullRequestThreadPosition(line=42, offset=1),
            right_file_end=PullRequestThreadPosition(line=42, offset=1),
        ),
    ),
)

# Create a PR-level thread (no file)
thread = post_pr_new_thread(
    pr_api,
    PullRequestThreadRequest(
        comments=[PullRequestThreadCommentRequest(content="Please add a CHANGELOG entry.")],
    ),
)

# Fetch a single thread by ID
from pyado.raw import get_pr_thread

thread = get_pr_thread(pr_api, thread.id)

# Reply to an existing thread
post_pr_thread_comment(pr_api, thread.id, "Good catch, fixed in the latest push.")
```

### Iterations

An iteration is created every time commits are pushed to the PR source branch.
Iterations are useful for diffing exactly what changed since the last review:

```python
from pyado.raw import iter_pr_iterations

for iteration in iter_pr_iterations(pr_api):
    print(iteration.id, iteration.source_ref_commit)
```

### Reviewers

```python
from pyado.raw import (
    put_pr_reviewer_vote,
    put_pr_reviewer,
    delete_pr_reviewer,
    get_pr_reviewers,
    PullRequestVote,
    PullRequestReviewerRequest,
    PullRequestReviewerVoteRequest,
)

# Cast a vote (approved / approved with suggestions / waiting / rejected / no vote)
put_pr_reviewer_vote(
    pr_api,
    "<reviewer-identity-id>",
    PullRequestReviewerVoteRequest(vote=PullRequestVote.APPROVED),
)

# Add or update a reviewer
put_pr_reviewer(
    pr_api,
    "<reviewer-identity-id>",
    PullRequestReviewerRequest(is_required=True),
)

# Remove a reviewer
delete_pr_reviewer(pr_api, "<reviewer-identity-id>")

# Read current reviewers
reviewers = get_pr_reviewers(pr_api)
for reviewer in reviewers:
    print(reviewer.display_name, reviewer.vote)
```

### Status checks

Status checks let external systems (CI, custom tools) post a pass/fail
indicator to a PR that appears in the PR status section:

```python
from pyado.raw import post_pr_status, PullRequestStatusRequest, PullRequestStatusContext

post_pr_status(
    pr_api,
    PullRequestStatusRequest(
        context=PullRequestStatusContext(genre="ci", name="integration-tests"),
        description="All 142 tests passed",
        iteration_id=1,
        state="succeeded",
    ),
)
```

### Fetching full PR details

`get_pr_details` returns the complete `PullRequestCreated` model for an
existing PR, including merge status, completion options, and linked commits:

```python
from pyado.raw import get_pr_details

pr = get_pr_details(pr_api)
print(pr.merge_status, pr.last_merge_source_commit)
```

---

## Repository

### Listing repositories

```python
from pyado.raw import iter_repository_details

for repo in iter_repository_details(api):
    print(repo.id, repo.name, repo.default_branch)
    if repo.parent_repository:
        print(f"  forked from {repo.parent_repository.name}")
```

### Reading file content

```python
from pyado.raw import get_repository_api_call, get_repository_item_bytes

repo_api = get_repository_api_call(api, repo_id)

# File at a specific commit SHA or branch
content = get_repository_item_bytes(repo_api, path="/src/config.json", version="abc123")

# Returns bytes; decode as needed
print(content.decode())
```

### Commit diff

`iter_commit_diff` paginates automatically and skips folder entries, yielding
only file-level changes.

> **How pagination stops.** The ADO diff endpoint does not return a total count.
> Instead it sets an `allChangesIncluded` flag in the response when the current
> page is the last one.  `iter_commit_diff` inspects this flag after each page
> and stops without issuing a redundant empty request.  Each page request passes
> a `$skip` offset equal to the total number of entries (including folder entries)
> seen so far, because ADO counts folders in the offset even though pyado filters
> them out of the results.

```python
from pyado.raw import get_commit_diff_page

# ADO returns one page at a time; iterate until allChangesIncluded is True
skip = 0
while True:
    page = get_commit_diff_page(repo_api, base_commit="abc123", target_commit="def456", skip=skip)
    for change in page.changes:
        if change.item and not change.item.is_folder:
            print(change.change_type, change.item.path)
    skip += len(page.changes)
    if page.all_changes_included:
        break
```

> **OOP shortcut:** `repo.iter_commit_diff("abc123", "def456")` handles
> pagination and folder filtering automatically.

### Last commit touching a file

Useful for cache invalidation or audit trails — find the most recent commit
that modified a specific file via `get_repository_commits`:

```python
from pyado.raw import get_repository_commits, GitCommitSearchCriteria

commits = get_repository_commits(
    repo_api,
    GitCommitSearchCriteria(
        item_path="/config/pipeline.json",
        to_commit_id="def456",
        top=1,
    ),
)
sha = commits[0].commit_id if commits else None
```

### Refs (branches and tags)

```python
from pyado.raw import iter_refs

# All refs
for ref in iter_refs(repo_api):
    print(ref.name, ref.object_id)

# Only branches matching a prefix
for ref in iter_refs(repo_api, name_filter="heads/release/"):
    print(ref.name)
```

### Branch management

```python
from pyado.raw import iter_refs, post_repository_refs, GitRefUpdate

# Create a new branch from an existing commit
post_repository_refs(repo_api, [GitRefUpdate(
    name="refs/heads/feature/new-branch",
    old_object_id="0000000000000000000000000000000000000000",
    new_object_id="abc123",
)])

# Delete a branch (requires the current HEAD SHA for optimistic concurrency)
current_sha = next(
    ref.object_id for ref in iter_refs(repo_api, name_filter="heads/feature/old-branch")
)
post_repository_refs(repo_api, [GitRefUpdate(
    name="refs/heads/feature/old-branch",
    old_object_id=current_sha,
    new_object_id="0000000000000000000000000000000000000000",
)])
```

---

## Git push

pyado lets you push file changes to ADO repositories programmatically in a
single API call — no local git required. This is useful for automation that
generates or modifies files directly in ADO (config updates, generated code,
release notes, …).

### Building change objects

Four OOP helpers from `pyado` create the change descriptors:

```python
from pyado import AddFile, EditFile, DeleteFile, RenameFile

AddFile("/path/to/new.json", '{"key": "value"}')   # create new file
EditFile("/path/to/existing.py", new_content)       # overwrite existing file
DeleteFile("/path/to/old.txt")                      # delete a file
RenameFile("/path/a.json", "/path/b.json")          # rename without changing content
```

These return objects that can be passed to `repo.commit(...)` (OOP layer) or
converted to `GitPushChange` for direct use with `post_push`.

### `make_ref_update` and `ZERO_SHA`

`make_ref_update` builds the ref-update descriptor for a branch. It needs the
current HEAD SHA because ADO uses *optimistic concurrency* for all ref
mutations: you tell ADO what SHA you expect the branch to be at right now, and
ADO rejects the push if the branch has moved since you read that SHA.  This
means two concurrent pushes to the same branch cannot silently overwrite each
other — one will succeed and the other will receive a conflict error and must
re-read the new HEAD before retrying.

```python
from pyado.raw import iter_refs, make_ref_update

current_sha = next(
    ref.object_id for ref in iter_refs(repo_api, name_filter="heads/main")
)
ref_update = make_ref_update("main", current_sha)
```

When pushing to a branch that does not yet exist, use `ZERO_SHA` as the
old commit.  `ZERO_SHA` (`"000...0"`) is git's conventional null SHA meaning
"this ref does not exist yet" — ADO creates the branch only if it is absent,
and rejects the push if it already exists:

```python
from pyado.raw import ZERO_SHA, make_ref_update

ref_update = make_ref_update("feature/new-branch", ZERO_SHA)
```

### Pushing multiple changes

The raw `post_push` function accepts a `GitPushRequest` model directly:

```python
from pyado.raw import (
    get_repository_api_call,
    iter_refs,
    make_ref_update,
    post_push,
    GitPushRequest,
    GitPushCommit,
    GitPushChange,
    GitPushNewContent,
    GitPushContentType,
)

repo_api = get_repository_api_call(api, repo_id)
current_sha = next(
    ref.object_id for ref in iter_refs(repo_api, name_filter="heads/main")
)

result = post_push(
    repo_api,
    GitPushRequest(
        ref_updates=[make_ref_update("main", current_sha)],
        commits=[
            GitPushCommit(
                comment="chore: update generated config",
                changes=[
                    GitPushChange(
                        change_type="add",
                        item={"path": "/config/new.json"},
                        new_content=GitPushNewContent(content='{"created": true}', content_type=GitPushContentType.raw_text),
                    ),
                    GitPushChange(
                        change_type="edit",
                        item={"path": "/config/settings.json"},
                        new_content=GitPushNewContent(content='{"key": "value"}', content_type=GitPushContentType.raw_text),
                    ),
                    GitPushChange(
                        change_type="delete",
                        item={"path": "/config/old.json"},
                    ),
                ],
            )
        ],
    ),
)
print(result.push_id, result.commits[0].commit_id)
```

> **OOP shortcut:** `repo.commit("main", "chore: update", [EditFile(...), DeleteFile(...)])` handles
> fetching the current HEAD SHA and building the `GitPushRequest` automatically.

---

## Builds

### Inspecting builds

```python
from pyado.raw import get_build_api_call, get_build_details, iter_timeline_records

build_api = get_build_api_call(api, build_id=1234)

details = get_build_details(build_api)
print(details.id, details.status, details.result, details.source_branch)

# Timeline records show every stage, job, and task with its state and result
for record in iter_timeline_records(build_api):
    print(f"{record.type_name:10}  {record.name:40}  {record.state}/{record.result}")
```

### Listing builds

```python
from pyado.raw import iter_builds

# Builds for a specific pipeline definition
for build in iter_builds(api, definition_id=42):
    print(build.id, build.build_number, build.result)

# Filter to in-progress builds
for build in iter_builds(api, definition_id=42, status_filter="inProgress"):
    print(build.id)
```

### Queuing a build

```python
from pyado.raw import post_build, BuildQueueRequest

queued = post_build(
    api,
    BuildQueueRequest(
        definition={"id": 42},
        source_branch="refs/heads/main",
        parameters='{"env": "staging", "dry_run": "false"}',
    ),
)
print(f"Build {queued.id} queued — {queued.build_number}")
```

### Build artifacts

```python
from pyado.raw import iter_build_artifacts

for artifact in iter_build_artifacts(build_api):
    print(artifact.name, artifact.resource.download_url)
```

### Build tags

Tags on a build are free-form strings, useful for marking release candidates
or flagging builds for further processing:

```python
from pyado.raw import post_build_tag, iter_build_tags, delete_build_tag

post_build_tag(build_api, "release-candidate")
for tag in iter_build_tags(build_api):
    print(tag)
delete_build_tag(build_api, "release-candidate")
```

### Work items associated with a build

```python
from pyado.raw import iter_build_work_item_ids, iter_work_items_between_builds

# Work items linked directly to this build
for wi_id in iter_build_work_item_ids(build_api):
    print(wi_id)

# Work items introduced between two builds (useful for release notes)
for ref in iter_work_items_between_builds(api, from_build_id=100, to_build_id=200):
    print(ref.id)
```

### Pipeline definitions (classic pipelines)

```python
from pyado.raw import iter_pipeline_definitions

for defn in iter_pipeline_definitions(api):
    print(defn.id, defn.name, defn.path)

# Filter by name substring
for defn in iter_pipeline_definitions(api, name_filter="deploy"):
    print(defn.id, defn.name)
```

---

## Pipeline task callbacks

When an agent job runs a script that needs to communicate back to ADO — for
example to write to the task log, send feed messages, or signal completion —
pyado provides the full set of distributed task plane APIs.

You construct the API calls from the plan, timeline, and job IDs that ADO injects
into the agent environment as `SYSTEM_TEAMFOUNDATIONCOLLECTIONURI`,
`SYSTEM_PLANID`, `SYSTEM_JOBID`, etc.:

```python
import os, uuid
from pyado.raw import get_plan_api_call, get_job_api_call, get_log_api_call

# Values come from ADO agent environment variables
plan_id      = uuid.UUID(os.environ["SYSTEM_PLANID"])
timeline_id  = uuid.UUID(os.environ["SYSTEM_TIMELINEID"])
job_id       = uuid.UUID(os.environ["SYSTEM_JOBID"])
task_id      = uuid.UUID(os.environ["SYSTEM_TASKINSTANCEID"])
log_id       = int(os.environ.get("SYSTEM_LOGID", "1"))

plan_api = get_plan_api_call(api, hub_name="build", plan_id=plan_id)
job_api  = get_job_api_call(api, "build", plan_id, timeline_id, job_id)
log_api  = get_log_api_call(api, "build", plan_id, log_id)
```

### Feed messages and log lines

Feed messages appear in the ADO UI next to the task in real time:

```python
from pyado.raw import post_job_feed

post_job_feed(job_api, ["Step 1 complete", "Starting step 2…"])
```

Log lines are appended to the persistent task log:

```python
from pyado.raw import post_job_logs

post_job_logs(log_api, "Detailed diagnostic output here.\n")
```

### Signalling task completion

```python
from pyado.raw import post_job_event

post_job_event(
    plan_api,
    task_id=task_id,
    job_id=job_id,
    job_event_name="TaskCompleted",
    job_event_result="succeeded",   # or "failed"
)
```

### Updating timeline records

Timeline records track the state of stages, jobs, and tasks. You can update
them directly (e.g. to mark a task as in-progress before it starts):

```python
from pyado.raw import get_timeline_api_call, patch_timeline_records, BuildRecordInfo

timeline_api = get_timeline_api_call(api, "build", plan_id, timeline_id)
patch_timeline_records(
    timeline_api,
    [
        BuildRecordInfo(
            id=str(task_id),
            state="inProgress",
            result=None,
        )
    ],
)
```

### Environment approvals

```python
from pyado.raw import iter_approvals, patch_approvals, PipelineApprovalUpdateRequest

# List pending approvals in the project
for approval in iter_approvals(api):
    print(approval.id, approval.status, approval.created_on)

# Approve one
patch_approvals(
    api,
    [PipelineApprovalUpdateRequest(approval_id=approval.id, status="approved", comment="Verified in staging, LGTM")],
)
```

---

## Pipeline runs (YAML pipelines)

The `/pipelines` API covers YAML pipelines and their runs as a separate
resource from the older Builds API. Use this when triggering YAML pipelines
or querying run results by pipeline folder and name.

```python
from pyado.raw import iter_pipelines, get_pipeline, iter_pipeline_runs, get_pipeline_run, post_pipeline_run, PipelineRunRequest

# List all YAML pipelines
for pipeline in iter_pipelines(api):
    print(pipeline.id, pipeline.folder, pipeline.name)

# Fetch a single pipeline's metadata
pipeline = get_pipeline(api, pipeline_id=42)

# List runs (most recent first)
for run in iter_pipeline_runs(api, pipeline_id=42):
    print(run.id, run.state, run.result)

# Fetch a specific run
run = get_pipeline_run(api, pipeline_id=42, run_id=1)

# Trigger a new run with template parameters
run = post_pipeline_run(
    api,
    pipeline_id=42,
    request=PipelineRunRequest(
        template_parameters={"env": "staging", "run_smoke_tests": "true"},
    ),
)
print(f"Run {run.id} started — state: {run.state}")
```

---

## Projects

Organisation-level listing of all projects. Requires an organisation-level
`ApiCall` (see [ApiCall setup](#the-apicall-object)):

```python
from pyado.raw import ApiCall, iter_projects

org_api = ApiCall(
    access_token="<your-pat>",
    url="https://dev.azure.com/<organisation>/_apis/",
)

for project in iter_projects(org_api):
    print(project.id, project.name, project.state)
```

---

## Variable groups

Variable groups store key/value pairs (including secrets) shared across
pipelines. pyado lets you read and update them programmatically — useful
for automating secret rotation or configuration changes.

```python
from pyado.raw import iter_variable_group_details

# List all variable groups
for vg in iter_variable_group_details(api):
    print(vg.id, vg.name)
    for name, info in vg.variables.items():
        # Secrets have value=None in the response
        print(f"  {name} = {info.value!r}  (secret: {info.is_secret})")
```

### Updating a variable group

You must pass back the `variable_group_project_references` from the existing
group, because ADO uses it to determine which projects the group belongs to:

```python
from pyado.raw import (
    iter_variable_group_details,
    get_variable_group_api_call,
    put_variable_group,
    VariableGroupUpdateRequest,
    VariableInfo,
)

# Fetch the current state of the group you want to update
target_vg = next(vg for vg in iter_variable_group_details(api) if vg.name == "my-group")
vg_api = get_variable_group_api_call(api, target_vg.id)

put_variable_group(
    vg_api,
    VariableGroupUpdateRequest(
        name=target_vg.name,
        variables={
            # Preserve all existing variables, only change what you need to
            **target_vg.variables,
            "MY_VAR": VariableInfo(value="new-value"),
            "SECRET_VAR": VariableInfo(value="new-secret", is_secret=True),
        },
        variable_group_project_references=target_vg.variable_group_project_references,
    ),
)
```

> **Note:** Writing a secret variable (`is_secret=True`) sets it in ADO. Reading
> it back will always return `value=None` — ADO never returns secret values
> through the API.

---

## Profile

The user profile endpoint identifies the authenticated user and requires a
dedicated API call (see [Profile API call](#profile-api-call)):

```python
from pyado.raw import get_profile_api_call, get_my_profile

profile_api = get_profile_api_call(access_token="<your-pat>")
me = get_my_profile(profile_api)

print(me.display_name)    # "Jane Smith"
print(me.email_address)   # "jane@example.com"
print(me.id)              # identity UUID string
```
