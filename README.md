# pyado — Pythonic Azure DevOps Interface

[![PyPI](https://img.shields.io/pypi/v/pyado.svg)][pypi_]
[![Status](https://img.shields.io/pypi/status/pyado.svg)][status]
[![Python Version](https://img.shields.io/pypi/pyversions/pyado)][python version]
[![License](https://img.shields.io/pypi/l/pyado)][license]

[![Read the documentation at https://pyado.readthedocs.io/](https://img.shields.io/readthedocs/pyado/latest.svg?label=Read%20the%20Docs)][read the docs]
[![Tests](https://github.com/fredstober/pyado/workflows/Tests/badge.svg)][tests]
[![Codecov](https://codecov.io/gh/fredstober/pyado/branch/main/graph/badge.svg)][codecov]

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)][ruff]

[pypi_]: https://pypi.org/project/pyado/
[status]: https://pypi.org/project/pyado/
[python version]: https://pypi.org/project/pyado
[read the docs]: https://pyado.readthedocs.io/
[tests]: https://github.com/fredstober/pyado/actions?workflow=Tests
[codecov]: https://app.codecov.io/gh/fredstober/pyado
[ruff]: https://github.com/astral-sh/ruff

Typed Python wrapper around the Azure DevOps REST API, built on [Pydantic] models.
All functions accept an `ApiCall` object and return typed results — no raw dicts,
no string parsing.

---

## Requirements

- Python 3.11
- An Azure DevOps [personal access token (PAT)][pat]

## Installation

```console
$ pip install pyado
```

or with [uv]:

```console
$ uv add pyado
```

---

## Quick Start

Every function takes an `ApiCall` as its first argument. Construct one with your
organisation/project base URL and a PAT:

```python
from pyado.api_call import ApiCall

# Project-level API call (most functions need this)
api = ApiCall(
    access_token="<your-pat>",
    url="https://dev.azure.com/<organisation>/<project>/_apis/",
)

# Organisation-level API call (iter_projects, iter_open_prs across projects)
org_api = ApiCall(
    access_token="<your-pat>",
    url="https://dev.azure.com/<organisation>/_apis/",
)

# Profile API call (get_my_profile)
profile_api = ApiCall(
    access_token="<your-pat>",
    url="https://app.vssps.visualstudio.com/_apis/",
)
```

`ApiCall` is a [Pydantic] `BaseModel` — it validates inputs on construction and
is immutable. Use `build_call()` to derive a scoped call pointing at a specific
resource.

---

## Modules

### `pyado.work_item`

```python
from pyado.work_item import (
    iter_work_item_details,
    get_work_item,
    create_work_item,
    update_work_item,
    WorkItemRelation,
    iter_sprint_iterations,
    run_wiql,
    iter_work_item_comments,
    add_work_item_comment,
    add_work_item_attachment,
)

# Fetch multiple work items (batched automatically, 200 per request)
for item in iter_work_item_details(api, [123, 456]):
    print(item.id, item.fields["System.Title"])

# Fetch a single work item with relations
item = get_work_item(api, 123, expand_relations=True)

# Create a work item with a parent link
new_item = create_work_item(
    api,
    fields={
        "System.WorkItemType": "Task",
        "System.Title": "My task",
        "System.AreaPath": "MyProject\\Team",
    },
    relations=[
        WorkItemRelation(
            rel="System.LinkTypes.Hierarchy-Reverse",
            url="https://dev.azure.com/org/project/_workitems/edit/100",
        )
    ],
)

# Update fields (markdown description example)
update_work_item(
    api,
    123,
    fields={"System.Description": "## Summary\nSome details."},
    multiline_fields_format={"System.Description": "markdown"},
)

# WIQL query
refs = run_wiql(api, "SELECT [System.Id] FROM WorkItems WHERE [System.State] = 'Active'")
ids = [ref.id for ref in refs]

# Comments
for comment in iter_work_item_comments(api, 123):
    print(comment.text)

add_work_item_comment(api, 123, "Reviewed and confirmed.", comment_format="markdown")

# Attach a file
add_work_item_attachment(api, 123, "report.txt", b"file contents here")

# Sprint iterations
for sprint in iter_sprint_iterations(api):
    print(sprint.name, sprint.attributes.start_date)

for sprint in iter_sprint_iterations(api, timeframe_filter="current"):
    print(sprint.name)
```

---

### `pyado.pull_request`

```python
from pyado.pull_request import (
    get_pr_api_call,
    iter_open_prs,
    iter_prs,
    create_pr,
    update_pr,
    iter_pr_work_item_ids,
    get_pr_labels,
    add_pr_label,
    delete_pr_label,
    iter_pr_threads,
    create_pr_thread,
    reply_to_pr_thread,
    iter_pr_iterations,
    set_pr_reviewer_vote,
    add_pr_reviewer,
    remove_pr_reviewer,
    create_pr_comments,
    create_pr_status_flag,
    PullRequestComment,
    PullRequestCommentHolder,
    PullRequestStatusInfo,
    PullRequestStatusContext,
    PullRequestVote,
)
from pyado.repository import RepositoryId
import uuid

repo_id: RepositoryId = uuid.UUID("<repository-uuid>")
pr_api = get_pr_api_call(api, repo_id, pr_id=42)

# List all active PRs in the project
for pr in iter_open_prs(api):
    print(pr.pr_id, pr.repository.id)

# List PRs matching criteria
for pr in iter_prs(api, {"status": "active", "creatorId": "<identity-id>"}):
    print(pr.pr_id)

# Create a PR
new_pr = create_pr(
    api,
    repo_id,
    title="My feature",
    source_branch="feature/my-branch",
    target_branch="main",
    description="Details here.",
)

# Update PR fields
update_pr(pr_api, {"title": "Updated title", "description": "New description."})

# Work items linked to the PR
for work_item_id in iter_pr_work_item_ids(pr_api):
    print(work_item_id)

# Labels
labels = get_pr_labels(pr_api)
add_pr_label(pr_api, "ready-to-merge")
delete_pr_label(pr_api, "needs-review")

# Review threads
for thread in iter_pr_threads(pr_api):
    for comment in thread.comments:
        print(comment.content)

thread = create_pr_thread(
    pr_api,
    "Please address this.",
    file_path="/src/foo.py",
    line=42,
)
reply_to_pr_thread(pr_api, thread.id, thread.comments[0].id, "Done, thanks.")

# Iterations (commit pushes)
for iteration in iter_pr_iterations(pr_api):
    print(iteration.id, iteration.source_ref_commit)

# Reviewer vote
set_pr_reviewer_vote(pr_api, "<reviewer-identity-id>", PullRequestVote.APPROVED)
add_pr_reviewer(pr_api, "<reviewer-identity-id>", is_required=True)
remove_pr_reviewer(pr_api, "<reviewer-identity-id>")

# Status flags
status = PullRequestStatusInfo(
    context=PullRequestStatusContext(genre="ci", name="build"),
    description="Build passed",
    iteration_id=1,
    state="succeeded",
)
create_pr_status_flag(pr_api, status)
```

---

### `pyado.repository`

```python
from pyado.repository import (
    iter_repository_details,
    get_file_content_at_commit,
    get_file_content_at_branch,
    iter_commit_diff,
    get_last_commit_touching_file,
    iter_refs,
    create_branch,
    delete_branch,
)
import uuid

repo_id = uuid.UUID("<repository-uuid>")

# List repositories
for repo in iter_repository_details(api):
    print(repo.name, repo.id)

# Read a file at a specific commit
content = get_file_content_at_commit(api, repo_id, "/src/config.json", "abc123")

# Read a file at a branch tip
content = get_file_content_at_branch(api, repo_id, "/src/config.json", "main")

# File changes between two commits (paginated)
for change in iter_commit_diff(api, repo_id, base_commit="abc123", target_commit="def456"):
    print(change.change_type, change.item.path)

# Most recent commit touching a file
commit_sha = get_last_commit_touching_file(api, repo_id, "/src/foo.py", before_commit="def456")

# Refs (branches / tags)
for ref in iter_refs(api, repo_id, name_filter="heads/main"):
    print(ref.name, ref.object_id)

# Branch management
create_branch(api, repo_id, "feature/new-branch", from_commit="abc123")
delete_branch(api, repo_id, "feature/old-branch", current_commit="abc123")
```

### `pyado.git_push`

```python
from pyado.git_push import (
    # High-level helpers
    add_file, edit_file, delete_file, rename_file,
    make_commit, make_ref_update, push,
    # Low-level REST models (for custom payloads)
    GitPushChange, GitPushChangeItem, GitPushNewContent,
    GitPushCommit, GitPushRefUpdate, GitPushResult,
)
from pyado.repository import ZERO_SHA

# Push one or more file changes in a single commit (high-level)
result = push(
    repo_api_call,
    ref_updates=[make_ref_update("main", "abc123")],
    commits=[
        make_commit("Update settings", [
            add_file("/config/new.json", '{"created": true}'),
            edit_file("/config/settings.json", '{"key": "value"}'),
            delete_file("/config/old.json"),
            rename_file("/config/a.json", "/config/b.json"),
        ])
    ],
)
print(result.push_id, result.commits[0].commit_id)

# Same push built from the low-level models directly
result = push(
    repo_api_call,
    ref_updates=[GitPushRefUpdate(name="refs/heads/main", old_object_id="abc123")],
    commits=[
        GitPushCommit(
            comment="Update settings",
            changes=[
                GitPushChange(
                    change_type="edit",
                    item=GitPushChangeItem(path="/config/settings.json"),
                    new_content=GitPushNewContent(content='{"key": "value"}'),
                ),
            ],
        )
    ],
)
```

---

### `pyado.build`

```python
from pyado.build import (
    get_build_api_call,
    get_build_details,
    iter_builds,
    queue_build,
    iter_timeline_records,
    iter_build_work_item_ids,
    iter_pipeline_definitions,
)

build_api = get_build_api_call(api, build_id=1234)

# Top-level build details
details = get_build_details(build_api)
print(details.status, details.result, details.source_branch)

# List recent builds
for build in iter_builds(api, definition_id=42, status_filter="inProgress"):
    print(build.id, build.build_number)

# Queue a new build
queued = queue_build(
    api,
    definition_id=42,
    source_branch="refs/heads/main",
    parameters={"env": "staging"},
)

# Timeline records (stages, jobs, tasks)
for record in iter_timeline_records(build_api):
    print(record.type_name, record.name, record.state, record.result)

# Work items linked to a build
for work_item_id in iter_build_work_item_ids(build_api):
    print(work_item_id)

# Pipeline definitions
for defn in iter_pipeline_definitions(api, name_filter="deploy"):
    print(defn.id, defn.name)
```

---

### `pyado.pipeline`

Used to interact with a running pipeline task from within a task script (e.g.
an agent job calling back to ADO).

```python
from pyado.pipeline import (
    get_plan_api_call,
    get_timeline_api_call,
    get_job_api_call,
    get_log_api_call,
    send_job_feed,
    send_job_logs,
    send_job_event,
    update_timeline_records,
    iter_pending_approvals,
    approve_pipeline,
)
import uuid

plan_id = uuid.UUID("<plan-uuid>")
timeline_id = uuid.UUID("<timeline-uuid>")
job_id = uuid.UUID("<job-uuid>")
log_id = 1

plan_api = get_plan_api_call(api, hub_name="build", plan_id=plan_id)
job_api = get_job_api_call(api, "build", plan_id, timeline_id, job_id)
log_api = get_log_api_call(api, "build", plan_id, log_id)

# Send messages to the task feed (shown in the ADO UI)
send_job_feed(job_api, ["Step 1 complete", "Step 2 starting…"])

# Append content to the task log
send_job_logs(log_api, "Detailed log output here.\n")

# Signal task completion
send_job_event(plan_api, task_id=uuid.UUID("<task-uuid>"), job_id=job_id,
               job_event_name="TaskCompleted", job_event_result="succeeded")

# Pending environment approvals
for approval in iter_pending_approvals(api):
    print(approval.id, approval.status)

approve_pipeline(api, approval_id="<approval-uuid>", comment="LGTM")
```

---

### `pyado.project`

```python
from pyado.project import iter_projects

# Requires an organisation-level ApiCall
for project in iter_projects(org_api):
    print(project.id, project.name)
```

---

### `pyado.variable_group`

```python
from pyado.variable_group import (
    iter_variable_group_details,
    update_variable_group_entries,
    VariableInfo,
)

# List all variable groups in the project
for vg in iter_variable_group_details(api):
    print(vg.id, vg.name, vg.variables)

# Update variables in a group
update_variable_group_entries(
    api,
    var_group_id=42,
    var_group_name="MyGroup",
    variables={
        "MY_VAR": VariableInfo(value="new-value"),
        "SECRET_VAR": VariableInfo(value="secret", is_secret=True),
    },
)
```

---

### `pyado.profile`

```python
from pyado.profile import get_my_profile

# Requires the profile ApiCall (app.vssps.visualstudio.com)
me = get_my_profile(profile_api)
print(me.display_name, me.email_address)
```

---

## Contributing

Contributions are very welcome.
To learn more, see the [Contributor Guide].

## License

Distributed under the terms of the [MIT license][license],
_pyado_ is free and open source software.

## Issues

If you encounter any problems,
please [file an issue] along with a detailed description.

<!-- github-only -->

[pydantic]: https://docs.pydantic.dev/
[pat]: https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate
[file an issue]: https://github.com/fredstober/pyado/issues
[pip]: https://pip.pypa.io/
[uv]: https://docs.astral.sh/uv/
[license]: https://github.com/fredstober/pyado/blob/main/LICENSE
[contributor guide]: https://github.com/fredstober/pyado/blob/main/CONTRIBUTING.md
