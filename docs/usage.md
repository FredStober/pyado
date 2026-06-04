# Usage Guide

This guide covers every part of the pyado public API. It is organised by domain.
Each section explains what the functions do and why you would use them before
showing the code.

> **Why not the official `azure-devops` package?**
> Microsoft's auto-generated client surfaces models typed as `object`, omits
> pagination handling on many endpoints, and requires a separate
> `azure-identity` or `azure-devops` connection object for authentication.
> pyado replaces all of that with one `ApiCall` model, Pydantic-validated inputs
> and outputs on every function, and transparent pagination built into every
> iterator.

**Contents:**
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

## OOP interface

The `pyado.oop` subpackage (also re-exported directly from `pyado`) wraps
every ADO resource as a Python object. Instead of constructing `ApiCall`
objects yourself, you navigate a hierarchy: `AzureDevOpsService →
Organization → Project → Repository / WorkItem / Build / Pipeline /
VariableGroup / Team`. Pull requests live under `Repository`. Back-navigation
(`build.project`, `pr.repo.org`, etc.) is always zero-cost.

Objects obtained from different factory paths share identity when they
represent the same ADO resource: `build.project is wi.project` is guaranteed.

### Authentication and construction

```python
import pyado

# Explicit credentials
svc = pyado.AzureDevOpsService(
    org="https://dev.azure.com/myorg",
    pat="<personal-access-token>",
)

# From environment variables (AZURE_DEVOPS_ORG, AZURE_DEVOPS_EXT_PAT)
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
pr = repo.create_pr(
    title="Update config",
    source_branch="feature/update-config",
    target_branch="main",
    description="Fixes #123.",
)

# Fetch existing
pr = repo.get_pr(42)

# List
for pr in repo.iter_prs():              # active by default
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
pr.vote("<identity-id>", pyado.PullRequestVote.APPROVED)
reviewers = pr.get_reviewers()

# Threads (review comments)
thread = pr.add_thread(
    "This import is unused.",
    file_path="/src/foo.py",
    line=42,
)
pr.reply_to_thread(thread.id, "Fixed in the latest push.")
pr.update_thread_status(thread.id, pyado.PullRequestThreadStatus.FIXED)
for thread in pr.iter_threads():
    print(thread.status, thread.comments[0].content)

# Work item association
pr.link_work_item(wi)                         # artifact link on the work item
pr.set_work_item_refs([wi.id])                # visible in the ADO PR page
for wi_id in pr.iter_work_item_ids():
    print(wi_id)

# Status checks
pr.set_status(
    pyado.PullRequestStatusState.SUCCEEDED,
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
pr.enable_auto_complete("<identity-id>")
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
wi.add_link(other_wi, pyado.WorkItemRelationType.CHILD)

# Artifact links
wi.link_pull_request(pr)
wi.link_build(build)
wi.link_commit(repo, "abc123")

# Delete (soft — restorable from Recycle Bin for 30 days)
wi.delete()
```

### Build

```python
build = proj.get_build(456)

# Properties
print(build.id, build.number, build.status, build.result)
print(build.source_branch, build.start_time, build.finish_time)

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
build.cancel()
build.cancel_run()   # via Pipelines v2 endpoint

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

# Work items
for wi_id in build.iter_work_item_ids():
    print(wi_id)
for wi_id in build.iter_work_items_between(older_build):
    print(wi_id)

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
    pyado.PipelineResourceType.VARIABLE_GROUP,
    resource_id="42",
)

# Approvals (project-level)
for approval in proj.iter_pending_approvals():
    print(approval.id, approval.status)
proj.approve_pipeline(approval.id, comment="LGTM")
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
    "MY_VAR": pyado.VariableInfo(value="updated"),
})
vg.refresh()
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
    timeframe_filter=pyado.SprintIterationTimeframe.CURRENT
):
    print(sprint.name)

# Area path configuration
field_values = team.get_field_values()

# Assign iteration to team
team.add_iteration(iteration_id)
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
```

### WIT query folders

```python
tree = proj.get_query_tree(depth=2)
folder = proj.get_query_folder(folder_id="<uuid>", depth=1)
```

---

## The ApiCall object

`ApiCall` is the single credential and URL object that every pyado function
accepts as its first argument. It is an immutable [Pydantic] `BaseModel`, so
bad inputs (wrong URL scheme, missing token) are caught immediately on
construction rather than when the first API call fires.

[Pydantic]: https://docs.pydantic.dev/

```python
import pyado

# Project-level — used by the vast majority of functions
api = pyado.ApiCall(
    access_token="<your-pat>",
    url="https://dev.azure.com/<organisation>/<project>/_apis/",
)

# Organisation-level — needed for iter_projects and cross-project PR listing
org_api = pyado.ApiCall(
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
repo_api  = pyado.get_repository_api_call(api, repo_id)   # → …/git/repositories/{id}
wi_api    = pyado.get_work_item_api_call(api, 123)         # → …/wit/workitems/123
build_api = pyado.get_build_api_call(api, build_id=1234)   # → …/build/builds/1234
pr_api    = pyado.get_pr_api_call(api, repo_id, pr_id=42)  # → …/git/pullrequests/42
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
profile_api = pyado.get_profile_api_call(access_token="<your-pat>")
```

---

## Work items

### Fetching work items

`iter_work_item_details` fetches full work item data in batches of 200 (the ADO
API limit). Pass any number of IDs and iterate — batching is automatic:

```python
import pyado

for item in pyado.iter_work_item_details(api, [123, 456, 789]):
    print(item.id, item.fields["System.Title"], item.fields.get("System.State"))
```

To fetch a single item and include its relations (parent links, attached files, …):

```python
wi_api = pyado.get_work_item_api_call(api, 123)
item = pyado.get_work_item(wi_api, expand_relations=True)

for relation in item.relations or []:
    print(relation.rel, relation.url)
```

To limit which fields come back (useful for large batches where you only need
a few columns):

```python
for item in pyado.iter_work_item_details(api, ids, work_item_field_list=["System.Id", "System.Title"]):
    print(item.id, item.fields["System.Title"])
```

### Querying with WIQL

WIQL (Work Item Query Language) is ADO's SQL-like query language. Use
`post_wiql` to run a query and get back a list of `WorkItemRef` objects. The
refs only contain IDs; pass them to `iter_work_item_details` to get full data:

```python
refs = pyado.post_wiql(
    api,
    "SELECT [System.Id] FROM WorkItems "
    "WHERE [System.TeamProject] = @project "
    "  AND [System.State] = 'Active' "
    "ORDER BY [System.CreatedDate] DESC",
)
ids = [ref.id for ref in refs]
for item in pyado.iter_work_item_details(api, ids):
    print(item.id, item.fields["System.Title"])
```

### Creating work items

`create_work_item` requires at minimum `"System.WorkItemType"` in the `fields`
dict. Every other ADO field reference name is optional. Optionally attach
relations (parent links, artifact links, …) at creation time:

```python
import pyado

task = pyado.create_work_item(
    api,
    fields={
        "System.WorkItemType": "Task",
        "System.Title": "Investigate memory leak",
        "System.Description": "Heap grows unbounded under load.",
        "System.AreaPath": "MyProject\\Backend",
        "System.AssignedTo": "jane@example.com",
    },
    relations=[
        pyado.WorkItemRelation(
            rel="System.LinkTypes.Hierarchy-Reverse",   # parent link
            url="https://dev.azure.com/org/project/_workitems/edit/100",
        )
    ],
)
print(f"Created #{task.id}")
```

### Updating work items

`update_work_item` takes a dict of field reference names to new values. Use
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
wi_api = pyado.get_work_item_api_call(api, 123)

pyado.update_work_item(
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
string in the `System.Tags` field (e.g. `"bug; hotfix; reviewed"`). pyado
parses and formats that for you, exposing tags as a plain Python list.
Comparison in `add_work_item_tag` and `remove_work_item_tag` is
case-insensitive — ADO normalises casing in the UI, so `"Bug"` and `"bug"` are
the same tag:

```python
wi_api = pyado.get_work_item_api_call(api, 123)

# Read
tags = pyado.get_work_item_tags(wi_api)         # → ["bug", "hotfix"]

# Add — no-op if already present (case-insensitive)
tags = pyado.add_work_item_tag(wi_api, "reviewed")

# Remove — no-op if not present
tags = pyado.remove_work_item_tag(wi_api, "hotfix")
```

### Comments

Comments support plain text and markdown:

```python
wi_api = pyado.get_work_item_api_call(api, 123)

# Read all comments
for comment in pyado.iter_work_item_comments(wi_api):
    print(comment.created_by.display_name, comment.text)

# Post a new comment
pyado.post_work_item_comment(
    wi_api,
    "Confirmed in staging. Closing.",
    comment_format="markdown",
)
```

### Attaching files

Attachment is a two-step operation that pyado combines into a single call.
First, the file bytes are uploaded to ADO's attachment store, which returns a
permanent URL.  Then a JSON Patch operation adds an `AttachedFile` relation
pointing to that URL on the work item.

> **Partial failure.** If the second step fails after the file has already been
> uploaded, the file exists in the attachment store but is not linked to any work
> item.  Retrying the call uploads a second copy — ADO does not de-duplicate by
> content.  The orphaned upload does no harm; it is simply inaccessible.

```python
report = pathlib.Path("report.html").read_bytes()
ref = pyado.add_work_item_attachment(api, work_item_id=123, filename="report.html", content=report)
print(ref.url)  # permanent download URL
```

### Linking a pull request to a work item

ADO's artifact URL format for a pull request is
`vstfs:///Git/PullRequestId/{project_id}%2F{repo_id}%2F{pr_id}`.
`add_artifact_link` adds an `ArtifactLink` relation to the work item:

```python
artifact_url = (
    f"vstfs:///Git/PullRequestId/"
    f"{project_id}%2F{repo_id}%2F{pr_id}"
)
wi_api = pyado.get_work_item_api_call(api, work_item_id)
pyado.add_artifact_link(wi_api, artifact_url, comment="PR that fixes this")
```

### Sprint iterations

```python
# All sprints for the default team
for sprint in pyado.iter_sprint_iterations(api):
    print(sprint.name, sprint.attributes.start_date, sprint.attributes.finish_date)

# Only the current sprint
for sprint in pyado.iter_sprint_iterations(api, timeframe_filter="current"):
    print(sprint.name)
```

---

## Pull requests

### Scoped API calls

Most PR functions take either a project-level `ApiCall` or a PR-level one.
Derive the PR-level call once and reuse it:

```python
import uuid, pyado

repo_id: pyado.RepositoryId = uuid.UUID("<repository-uuid>")
repo_api = pyado.get_repository_api_call(api, repo_id)
pr_api   = pyado.get_pr_api_call(api, repo_id, pr_id=42)
```

### Listing PRs

```python
# All active PRs in the project (across all repositories)
for pr in pyado.iter_open_prs(api):
    print(pr.pr_id, pr.repository.name, pr.title)

# Filtered listing — any query parameter the ADO API accepts
for pr in pyado.iter_prs(api, {"status": "active", "creatorId": "<identity-uuid>"}):
    print(pr.pr_id, pr.title)

# Commits on a PR
for commit in pyado.iter_pr_commits(pr_api):
    print(commit.commit_id, commit.comment)
```

### Creating and updating PRs

`create_pr` normalises branch names automatically — you can pass
`"feature/my-branch"` or the full `"refs/heads/feature/my-branch"`.
Linking work items at creation time makes them immediately visible in the ADO UI
and via `iter_pr_work_item_ids`:

```python
pr = pyado.create_pr(
    repo_api,
    title="Add telemetry to the data pipeline",
    source_branch="feature/telemetry",
    target_branch="main",
    description="Implements #123 — adds structured logging throughout.",
    work_item_ids=[123],
)
print(f"PR #{pr.pull_request_id}: {pr.url}")

# Update title or description after creation
pyado.patch_pr(pr_api, pyado.PullRequestUpdateRequest(title="Updated title"))
```

### Work items linked to a PR

```python
for wi_id in pyado.iter_pr_work_item_ids(pr_api):
    print(wi_id)
```

### Labels

Labels are free-form strings attached to a PR. They are commonly used to
signal state (e.g. `"ready-to-merge"`, `"do-not-merge"`, `"needs-review"`):

```python
# Read
labels = pyado.get_pr_labels(pr_api)    # → ["ready-to-merge"]

# Add
pyado.post_pr_label(pr_api, "ready-to-merge")

# Remove
pyado.delete_pr_label(pr_api, "needs-review")
```

### Review threads

A review thread anchors a conversation to an optional file and line. Threads
without a file path are PR-level comments:

```python
# Read all threads
for thread in pyado.iter_pr_threads(pr_api):
    print(f"Thread {thread.id} ({thread.status})")
    for comment in thread.comments:
        print(f"  {comment.author.display_name}: {comment.content}")

# Create a file-level thread
thread = pyado.create_pr_thread(
    pr_api,
    "This import is unused.",
    file_path="/src/pyado/raw/git.py",
    line=42,
)

# Create a PR-level thread (no file)
thread = pyado.create_pr_thread(pr_api, "Please add a CHANGELOG entry.")

# Reply to an existing thread
pyado.reply_to_pr_thread(pr_api, thread.id, "Good catch, fixed in the latest push.")
```

### Iterations

An iteration is created every time commits are pushed to the PR source branch.
Iterations are useful for diffing exactly what changed since the last review:

```python
for iteration in pyado.iter_pr_iterations(pr_api):
    print(iteration.id, iteration.source_ref_commit)
```

### Reviewers

```python
# Cast a vote (approved / approved with suggestions / waiting / rejected / no vote)
pyado.set_pr_reviewer_vote(pr_api, "<reviewer-identity-id>", pyado.PullRequestVote.APPROVED)

# Add or update a reviewer
pyado.add_pr_reviewer(pr_api, "<reviewer-identity-id>", is_required=True)

# Remove a reviewer
pyado.delete_pr_reviewer(pr_api, "<reviewer-identity-id>")

# Read current reviewers
reviewers = pyado.get_pr_reviewers(pr_api)
for reviewer in reviewers:
    print(reviewer.display_name, reviewer.vote)
```

### Status checks

Status checks let external systems (CI, custom tools) post a pass/fail
indicator to a PR that appears in the PR status section:

```python
pyado.post_pr_status(
    pr_api,
    pyado.PullRequestStatusRequest(
        context=pyado.PullRequestStatusContext(genre="ci", name="integration-tests"),
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
pr = pyado.get_pr_details(pr_api)
print(pr.merge_status, pr.last_merge_source_commit)
```

---

## Repository

### Listing repositories

```python
for repo in pyado.iter_repository_details(api):
    print(repo.id, repo.name, repo.default_branch)
    if repo.parent_repository:
        print(f"  forked from {repo.parent_repository.name}")
```

### Reading file content

```python
repo_api = pyado.get_repository_api_call(api, repo_id)

# File at a specific commit SHA
content = pyado.get_file_content_at_commit(repo_api, "/src/config.json", "abc123")

# File at the tip of a branch
content = pyado.get_file_content_at_branch(repo_api, "/src/config.json", "main")

# Both return "" when the file does not exist at that ref — no exception raised
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
for change in pyado.iter_commit_diff(repo_api, base_commit="abc123", target_commit="def456"):
    print(change.change_type, change.item.path)
    # change.change_type is one of: add, edit, delete, rename, ...
```

### Last commit touching a file

Useful for cache invalidation or audit trails — finds the most recent commit
in the history at or before a given commit that modified a specific file:

```python
sha = pyado.get_last_commit_touching_file(
    repo_api,
    path="/config/pipeline.json",
    before_commit="def456",
)
```

### Refs (branches and tags)

```python
# All refs
for ref in pyado.iter_refs(repo_api):
    print(ref.name, ref.object_id)

# Only branches matching a prefix
for ref in pyado.iter_refs(repo_api, name_filter="heads/release/"):
    print(ref.name)
```

### Branch management

```python
# Create a new branch from an existing commit
pyado.create_branch(repo_api, "feature/new-branch", from_commit="abc123")

# Delete a branch (requires the current HEAD SHA for optimistic concurrency)
current_sha = next(
    ref.object_id for ref in pyado.iter_refs(repo_api, name_filter="heads/feature/old-branch")
)
pyado.delete_branch(repo_api, "feature/old-branch", current_commit=current_sha)
```

---

## Git push

pyado lets you push file changes to ADO repositories programmatically in a
single API call — no local git required. This is useful for automation that
generates or modifies files directly in ADO (config updates, generated code,
release notes, …).

### Building change objects

Four helpers create the change descriptors:

```python
pyado.add_file("/path/to/new.json", '{"key": "value"}')   # create new file
pyado.edit_file("/path/to/existing.py", new_content)       # overwrite existing file
pyado.delete_file("/path/to/old.txt")                      # delete a file
pyado.rename_file("/path/a.json", "/path/b.json")          # rename without changing content
```

All four return a `GitPushChange` object. Combine them in a commit with
`make_commit`, and push with `push_commits`.

### `make_ref_update` and `ZERO_SHA`

`make_ref_update` builds the ref-update descriptor for a branch. It needs the
current HEAD SHA because ADO uses *optimistic concurrency* for all ref
mutations: you tell ADO what SHA you expect the branch to be at right now, and
ADO rejects the push if the branch has moved since you read that SHA.  This
means two concurrent pushes to the same branch cannot silently overwrite each
other — one will succeed and the other will receive a conflict error and must
re-read the new HEAD before retrying.

```python
current_sha = next(
    ref.object_id for ref in pyado.iter_refs(repo_api, name_filter="heads/main")
)
ref_update = pyado.make_ref_update("main", current_sha)
```

When pushing to a branch that does not yet exist, use `pyado.ZERO_SHA` as the
old commit.  `ZERO_SHA` (`"000...0"`) is git's conventional null SHA meaning
"this ref does not exist yet" — ADO creates the branch only if it is absent,
and rejects the push if it already exists:

```python
ref_update = pyado.make_ref_update("feature/new-branch", pyado.ZERO_SHA)
```

### Pushing multiple changes

```python
import pyado

repo_api = pyado.get_repository_api_call(api, repo_id)
current_sha = next(
    ref.object_id for ref in pyado.iter_refs(repo_api, name_filter="heads/main")
)

result = pyado.push_commits(
    repo_api,
    ref_updates=[pyado.make_ref_update("main", current_sha)],
    commits=[
        pyado.make_commit(
            "chore: update generated config",
            [
                pyado.add_file("/config/new.json", '{"created": true}'),
                pyado.edit_file("/config/settings.json", '{"key": "value"}'),
                pyado.delete_file("/config/old.json"),
                pyado.rename_file("/config/a.json", "/config/b.json"),
            ],
        )
    ],
)
print(result.push_id, result.commits[0].commit_id)
```

Multiple commits can be included in a single push by passing more
`make_commit(...)` entries to the `commits` list.

---

## Builds

### Inspecting builds

```python
import pyado

build_api = pyado.get_build_api_call(api, build_id=1234)

details = pyado.get_build_details(build_api)
print(details.id, details.status, details.result, details.source_branch)

# Timeline records show every stage, job, and task with its state and result
for record in pyado.iter_timeline_records(build_api):
    print(f"{record.type_name:10}  {record.name:40}  {record.state}/{record.result}")
```

### Listing builds

```python
# Builds for a specific pipeline definition
for build in pyado.iter_builds(api, definition_id=42):
    print(build.id, build.build_number, build.result)

# Filter to in-progress builds
for build in pyado.iter_builds(api, definition_id=42, status_filter="inProgress"):
    print(build.id)
```

### Queuing a build

```python
queued = pyado.start_build(
    api,
    definition_id=42,
    source_branch="refs/heads/main",
    parameters={"env": "staging", "dry_run": "false"},
)
print(f"Build {queued.id} queued — {queued.build_number}")
```

### Build artifacts

```python
for artifact in pyado.iter_build_artifacts(build_api):
    print(artifact.name, artifact.resource.download_url)
```

### Build tags

Tags on a build are free-form strings, useful for marking release candidates
or flagging builds for further processing:

```python
pyado.post_build_tag(build_api, "release-candidate")
for tag in pyado.iter_build_tags(build_api):
    print(tag)
pyado.delete_build_tag(build_api, "release-candidate")
```

### Work items associated with a build

```python
# Work items linked directly to this build
for wi_id in pyado.iter_build_work_item_ids(build_api):
    print(wi_id)

# Work items introduced between two builds (useful for release notes)
for ref in pyado.iter_work_items_between_builds(api, from_build_id=100, to_build_id=200):
    print(ref.id)
```

### Pipeline definitions (classic pipelines)

```python
for defn in pyado.iter_pipeline_definitions(api):
    print(defn.id, defn.name, defn.path)

# Filter by name substring
for defn in pyado.iter_pipeline_definitions(api, name_filter="deploy"):
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
import uuid, pyado

# Values come from ADO agent environment variables
plan_id      = uuid.UUID(os.environ["SYSTEM_PLANID"])
timeline_id  = uuid.UUID(os.environ["SYSTEM_TIMELINEID"])
job_id       = uuid.UUID(os.environ["SYSTEM_JOBID"])
task_id      = uuid.UUID(os.environ["SYSTEM_TASKINSTANCEID"])
log_id       = int(os.environ.get("SYSTEM_LOGID", "1"))

plan_api = pyado.get_plan_api_call(api, hub_name="build", plan_id=plan_id)
job_api  = pyado.get_job_api_call(api, "build", plan_id, timeline_id, job_id)
log_api  = pyado.get_log_api_call(api, "build", plan_id, log_id)
```

### Feed messages and log lines

Feed messages appear in the ADO UI next to the task in real time:

```python
pyado.send_job_feed(job_api, ["Step 1 complete", "Starting step 2…"])
```

Log lines are appended to the persistent task log:

```python
pyado.post_job_logs(log_api, "Detailed diagnostic output here.\n")
```

### Signalling task completion

```python
pyado.send_job_event(
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
timeline_api = pyado.get_timeline_api_call(api, "build", plan_id, timeline_id)
pyado.update_timeline_records(
    timeline_api,
    [
        pyado.BuildRecordInfo(
            id=str(task_id),
            state="inProgress",
            result=None,
        )
    ],
)
```

### Environment approvals

```python
# List pending approvals in the project
for approval in pyado.iter_pending_approvals(api):
    print(approval.id, approval.status, approval.created_on)

# Approve one
pyado.approve_pipeline(api, approval_id=str(approval.id), comment="Verified in staging, LGTM")
```

---

## Pipeline runs (YAML pipelines)

The `/pipelines` API covers YAML pipelines and their runs as a separate
resource from the older Builds API. Use this when triggering YAML pipelines
or querying run results by pipeline folder and name.

```python
import pyado

# List all YAML pipelines
for pipeline in pyado.iter_pipelines(api):
    print(pipeline.id, pipeline.folder, pipeline.name)

# Fetch a single pipeline's metadata
pipeline = pyado.get_pipeline(api, pipeline_id=42)

# List runs (most recent first)
for run in pyado.iter_pipeline_runs(api, pipeline_id=42):
    print(run.id, run.state, run.result)

# Fetch a specific run
run = pyado.get_pipeline_run(api, pipeline_id=42, run_id=1)

# Trigger a new run with template parameters
run = pyado.post_pipeline_run(
    api,
    pipeline_id=42,
    request=pyado.PipelineRunRequest(
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
import pyado

org_api = pyado.ApiCall(
    access_token="<your-pat>",
    url="https://dev.azure.com/<organisation>/_apis/",
)

for project in pyado.iter_projects(org_api):
    print(project.id, project.name, project.state)
```

---

## Variable groups

Variable groups store key/value pairs (including secrets) shared across
pipelines. pyado lets you read and update them programmatically — useful
for automating secret rotation or configuration changes.

```python
import pyado

# List all variable groups
for vg in pyado.iter_variable_group_details(api):
    print(vg.id, vg.name)
    for name, info in vg.variables.items():
        # Secrets have value=None in the response
        print(f"  {name} = {info.value!r}  (secret: {info.is_secret})")
```

### Updating a variable group

You must pass back the `variable_group_project_references` from the existing
group, because ADO uses it to determine which projects the group belongs to:

```python
# Fetch the current state of the group you want to update
target_vg = next(vg for vg in pyado.iter_variable_group_details(api) if vg.name == "my-group")
vg_api = pyado.get_variable_group_api_call(api, target_vg.id)

pyado.update_variable_group(
    vg_api,
    name=target_vg.name,
    variables={
        # Preserve all existing variables, only change what you need to
        **target_vg.variables,
        "MY_VAR": pyado.VariableInfo(value="new-value"),
        "SECRET_VAR": pyado.VariableInfo(value="new-secret", is_secret=True),
    },
    variable_group_project_references=target_vg.variable_group_project_references,
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
import pyado

profile_api = pyado.get_profile_api_call(access_token="<your-pat>")
me = pyado.get_my_profile(profile_api)

print(me.display_name)    # "Jane Smith"
print(me.email_address)   # "jane@example.com"
print(me.id)              # identity UUID string
```
