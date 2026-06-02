# pyado — Pythonic Azure DevOps Interface

[![PyPI](https://img.shields.io/pypi/v/pyado.svg)][pypi_]
[![Status](https://img.shields.io/pypi/status/pyado.svg)][status]
[![Python Version](https://img.shields.io/pypi/pyversions/pyado)][python version]
[![License](https://img.shields.io/pypi/l/pyado)][license]

[![Read the documentation at https://pyado.readthedocs.io/](https://img.shields.io/readthedocs/pyado/latest.svg?label=Read%20the%20Docs)][read the docs]
[![Tests](https://github.com/fredstober/pyado/workflows/Tests/badge.svg)][tests]
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)][ruff]

[pypi_]: https://pypi.org/project/pyado/
[status]: https://pypi.org/project/pyado/
[python version]: https://pypi.org/project/pyado
[read the docs]: https://pyado.readthedocs.io/
[tests]: https://github.com/fredstober/pyado/actions?workflow=Tests
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
import pyado

# Project-level API call (most functions need this)
api = pyado.ApiCall(
    access_token="<your-pat>",
    url="https://dev.azure.com/<organisation>/<project>/_apis/",
)

# Organisation-level API call (iter_projects, iter_open_prs across projects)
org_api = pyado.ApiCall(
    access_token="<your-pat>",
    url="https://dev.azure.com/<organisation>/_apis/",
)

# Profile API call (get_my_profile)
profile_api = pyado.ApiCall(
    access_token="<your-pat>",
    url="https://app.vssps.visualstudio.com/_apis/",
)
```

`ApiCall` is a [Pydantic] `BaseModel` — it validates inputs on construction and
is immutable. Use `build_call()` to derive a scoped call pointing at a specific
resource.

All public symbols are available directly from the `pyado` namespace.

---

## Work items

```python
import pyado

# Fetch multiple work items (batched automatically, 200 per request)
for item in pyado.iter_work_item_details(api, [123, 456]):
    print(item.id, item.fields["System.Title"])

# Fetch a single work item with relations
work_item_api = pyado.get_work_item_api_call(api, 123)
item = pyado.get_work_item(work_item_api, expand_relations=True)

# Create a work item with a parent link
new_item = pyado.create_work_item(
    api,
    fields={
        "System.WorkItemType": "Task",
        "System.Title": "My task",
        "System.AreaPath": "MyProject\\Team",
    },
    relations=[
        pyado.WorkItemRelation(
            rel="System.LinkTypes.Hierarchy-Reverse",
            url="https://dev.azure.com/org/project/_workitems/edit/100",
        )
    ],
)

# Update fields (markdown description example)
pyado.update_work_item(
    work_item_api,
    fields={"System.Description": "## Summary\nSome details."},
    multiline_fields_format={"System.Description": "markdown"},
)

# WIQL query
refs = pyado.post_wiql(api, "SELECT [System.Id] FROM WorkItems WHERE [System.State] = 'Active'")
ids = [ref.id for ref in refs]

# Comments
for comment in pyado.iter_work_item_comments(work_item_api):
    print(comment.text)

pyado.post_work_item_comment(work_item_api, "Reviewed and confirmed.", comment_format="markdown")

# Attach a file
pyado.add_work_item_attachment(api, 123, "report.txt", b"file contents here")

# Sprint iterations
for sprint in pyado.iter_sprint_iterations(api):
    print(sprint.name, sprint.attributes.start_date)

for sprint in pyado.iter_sprint_iterations(api, timeframe_filter="current"):
    print(sprint.name)
```

---

## Pull requests

```python
import uuid
import pyado

repo_id: pyado.RepositoryId = uuid.UUID("<repository-uuid>")
repo_api = pyado.get_repository_api_call(api, repo_id)
pr_api = pyado.get_pr_api_call(api, repo_id, pr_id=42)

# List all active PRs in the project
for pr in pyado.iter_open_prs(api):
    print(pr.pr_id, pr.repository.id)

# List PRs matching criteria
for pr in pyado.iter_prs(api, {"status": "active", "creatorId": "<identity-id>"}):
    print(pr.pr_id)

# Create a PR
new_pr = pyado.create_pr(
    repo_api,
    title="My feature",
    source_branch="feature/my-branch",
    target_branch="main",
    description="Details here.",
)

# Update PR fields
pyado.patch_pr(pr_api, pyado.PullRequestUpdateRequest(title="Updated title"))

# Work items linked to the PR
for work_item_id in pyado.iter_pr_work_item_ids(pr_api):
    print(work_item_id)

# Labels
labels = pyado.get_pr_labels(pr_api)
pyado.post_pr_label(pr_api, "ready-to-merge")
pyado.delete_pr_label(pr_api, "needs-review")

# Review threads
for thread in pyado.iter_pr_threads(pr_api):
    for comment in thread.comments:
        print(comment.content)

thread = pyado.create_pr_thread(
    pr_api,
    "Please address this.",
    file_path="/src/foo.py",
    line=42,
)
pyado.reply_to_pr_thread(pr_api, thread.id, "Done, thanks.")

# Iterations (commit pushes to the PR source branch)
for iteration in pyado.iter_pr_iterations(pr_api):
    print(iteration.id, iteration.source_ref_commit)

# Reviewer management
pyado.set_pr_reviewer_vote(pr_api, "<reviewer-identity-id>", pyado.PullRequestVote.APPROVED)
pyado.add_pr_reviewer(pr_api, "<reviewer-identity-id>", is_required=True)
pyado.delete_pr_reviewer(pr_api, "<reviewer-identity-id>")

# Post a status flag (e.g. from a CI check)
pyado.post_pr_status(
    pr_api,
    pyado.PullRequestStatusRequest(
        context=pyado.PullRequestStatusContext(genre="ci", name="build"),
        description="Build passed",
        iteration_id=1,
        state="succeeded",
    ),
)
```

---

## Repository

```python
import uuid
import pyado

repo_id = uuid.UUID("<repository-uuid>")
repo_api = pyado.get_repository_api_call(api, repo_id)

# List repositories
for repo in pyado.iter_repository_details(api):
    print(repo.name, repo.id)

# Read a file at a specific commit
content = pyado.get_file_content_at_commit(repo_api, "/src/config.json", "abc123")

# Read a file at a branch tip
content = pyado.get_file_content_at_branch(repo_api, "/src/config.json", "main")

# File changes between two commits (paginated)
for change in pyado.iter_commit_diff(repo_api, base_commit="abc123", target_commit="def456"):
    print(change.change_type, change.item.path)

# Most recent commit touching a file
commit_sha = pyado.get_last_commit_touching_file(repo_api, "/src/foo.py", before_commit="def456")

# Refs (branches / tags)
for ref in pyado.iter_refs(repo_api, name_filter="heads/main"):
    print(ref.name, ref.object_id)

# Branch management
pyado.create_branch(repo_api, "feature/new-branch", from_commit="abc123")
pyado.delete_branch(repo_api, "feature/old-branch", current_commit="abc123")
```

---

## Git push

```python
import pyado

repo_api = pyado.get_repository_api_call(api, repo_id)

# Push one or more file changes in a single commit
result = pyado.push_commits(
    repo_api,
    ref_updates=[pyado.make_ref_update("main", "abc123")],
    commits=[
        pyado.make_commit("Update settings", [
            pyado.add_file("/config/new.json", '{"created": true}'),
            pyado.edit_file("/config/settings.json", '{"key": "value"}'),
            pyado.delete_file("/config/old.json"),
            pyado.rename_file("/config/a.json", "/config/b.json"),
        ])
    ],
)
print(result.push_id, result.commits[0].commit_id)
```

---

## Build

```python
import pyado

build_api = pyado.get_build_api_call(api, build_id=1234)

# Top-level build details
details = pyado.get_build_details(build_api)
print(details.status, details.result, details.source_branch)

# List recent builds
for build in pyado.iter_builds(api, definition_id=42, status_filter="inProgress"):
    print(build.id, build.build_number)

# Queue a new build
queued = pyado.start_build(
    api,
    definition_id=42,
    source_branch="refs/heads/main",
    parameters={"env": "staging"},
)

# Timeline records (stages, jobs, tasks)
for record in pyado.iter_timeline_records(build_api):
    print(record.type_name, record.name, record.state, record.result)

# Work items linked to a build
for work_item_id in pyado.iter_build_work_item_ids(build_api):
    print(work_item_id)

# Work items introduced between two build IDs
for ref in pyado.iter_work_items_between_builds(api, from_build_id=100, to_build_id=200):
    print(ref.id)

# Build artifacts
for artifact in pyado.iter_build_artifacts(build_api):
    print(artifact.name, artifact.resource.download_url)

# Build tags
for tag in pyado.iter_build_tags(build_api):
    print(tag)
pyado.post_build_tag(build_api, "release-candidate")
pyado.delete_build_tag(build_api, "release-candidate")

# Pipeline definitions (classic / Build API)
for defn in pyado.iter_pipeline_definitions(api, name_filter="deploy"):
    print(defn.id, defn.name)
```

---

## Pipeline (task callbacks)

Used to interact with a running pipeline task from within a task script (e.g.
an agent job calling back to ADO).

```python
import uuid
import pyado

plan_id = uuid.UUID("<plan-uuid>")
timeline_id = uuid.UUID("<timeline-uuid>")
job_id = uuid.UUID("<job-uuid>")
log_id = 1

plan_api = pyado.get_plan_api_call(api, hub_name="build", plan_id=plan_id)
job_api = pyado.get_job_api_call(api, "build", plan_id, timeline_id, job_id)
log_api = pyado.get_log_api_call(api, "build", plan_id, log_id)

# Send messages to the task feed (shown in the ADO UI)
pyado.send_job_feed(job_api, ["Step 1 complete", "Step 2 starting..."])

# Append content to the task log
pyado.post_job_logs(log_api, "Detailed log output here.\n")

# Signal task completion
pyado.send_job_event(
    plan_api,
    task_id=uuid.UUID("<task-uuid>"),
    job_id=job_id,
    job_event_name="TaskCompleted",
    job_event_result="succeeded",
)

# Pending environment approvals
for approval in pyado.iter_pending_approvals(api):
    print(approval.id, approval.status)

pyado.approve_pipeline(api, approval_id="<approval-uuid>", comment="LGTM")
```

---

## Pipeline runs (YAML pipelines)

The `/pipelines` REST API covers YAML pipelines and their runs separately from
the Build Definitions API.

```python
import pyado

# List all YAML pipelines in the project
for pipeline in pyado.iter_pipelines(api):
    print(pipeline.id, pipeline.name, pipeline.folder)

# Fetch a single pipeline
pipeline = pyado.get_pipeline(api, pipeline_id=42)

# List runs for a pipeline (newest first)
for run in pyado.iter_pipeline_runs(api, pipeline_id=42):
    print(run.id, run.state, run.result)

# Fetch a single run
run = pyado.get_pipeline_run(api, pipeline_id=42, run_id=1)

# Trigger a new run
run = pyado.post_pipeline_run(
    api,
    pipeline_id=42,
    request=pyado.PipelineRunRequest(
        template_parameters={"env": "staging"},
    ),
)
print(run.id, run.state)
```

---

## Projects

```python
import pyado

# Requires an organisation-level ApiCall
for project in pyado.iter_projects(org_api):
    print(project.id, project.name)
```

---

## Variable groups

```python
import pyado

# List all variable groups in the project
for vg in pyado.iter_variable_group_details(api):
    print(vg.id, vg.name, vg.variables)

# Update variables in a group
vg = next(vg for vg in pyado.iter_variable_group_details(api) if vg.id == 42)
vg_api = pyado.get_variable_group_api_call(api, 42)
pyado.update_variable_group(
    vg_api,
    name=vg.name,
    variables={
        "MY_VAR": pyado.VariableInfo(value="new-value"),
        "SECRET_VAR": pyado.VariableInfo(value="secret", is_secret=True),
    },
    variable_group_project_references=vg.variable_group_project_references,
)
```

---

## Profile

```python
import pyado

# Requires the profile ApiCall (app.vssps.visualstudio.com)
me = pyado.get_my_profile(profile_api)
print(me.display_name, me.email_address)
```

---

## Development

### Package structure

The library is split into two subpackages that are re-exported through the top-level
`pyado` namespace:

| Subpackage | Purpose |
|---|---|
| `pyado.raw` | Thin wrappers around individual ADO REST endpoints. Each function makes exactly one API call, accepts a typed Pydantic request model, and returns a typed Pydantic response model. No payload construction, no orchestration. |
| `pyado.high` | Higher-level helpers. Responsible for constructing request models from primitive args, pagination loops, and multi-step operations. Delegates all HTTP calls to `pyado.raw`. |

Both subpackages are split into domain modules:

| Module | Covers |
|---|---|
| `raw/_core.py` | `ApiCall`, shared types |
| `raw/build.py` | Builds, timeline records, artifacts, tags, pipeline definitions |
| `raw/git.py` | Repositories, commits, refs, file content, git push |
| `raw/pipeline.py` | YAML pipeline runs, distributed task plane (job feed, events, approvals) |
| `raw/profile.py` | User profile |
| `raw/project.py` | Projects |
| `raw/pull_request.py` | Pull requests, threads, reviewers, labels, statuses |
| `raw/variable_group.py` | Variable groups |
| `raw/work_item.py` | Work items, comments, WIQL, sprint iterations |
| `high/build.py` | `start_build`, `send_job_feed`, `send_job_event`, `approve_pipeline`, etc. |
| `high/git.py` | `push_commits`, `iter_commit_diff`, `get_file_content_at_*`, branch helpers |
| `high/pull_request.py` | `create_pr`, `create_pr_thread`, `reply_to_pr_thread`, reviewer helpers |
| `high/variable_group.py` | `update_variable_group` |
| `high/work_item.py` | `create_work_item`, `update_work_item`, `iter_work_item_details`, attachment |

**Rules for `raw/`:**
- One function per ADO REST endpoint; no multi-step logic.
- Accept fully-built Pydantic request models — no model construction inside the function.
- Return Pydantic response models; never raw `dict`.
- Multi-field request models are named publicly so callers can reference them directly.

**Rules for `high/`:**
- Construct request models from plain Python values (strings, ints, enums).
- Own pagination loops; yield individual items.
- May use intent-expressing names that differ from the underlying raw function
  (e.g. `push_commits` wraps `post_push`, `start_build` wraps `post_build`).
- Never call `api_call.get / post / patch / ...` directly — always delegate to `raw/`.
- Never re-export raw symbols; every public symbol in `high/` must be a function
  defined in that module.

**Adding new functionality:**

1. Add the HTTP call (and any request/response models) to the appropriate domain
   submodule in `raw/` (e.g. `raw/git.py`, `raw/build.py`, `raw/pull_request.py`).
2. Export new public symbols from `raw/__init__.py` and `pyado/__init__.py`.
3. If payload construction, pagination, or orchestration is needed, add a wrapper
   in the matching domain submodule in `high/` (e.g. `high/git.py`), then export
   it from `high/__init__.py` and `pyado/__init__.py`.

### Setting up a development environment

You need Python 3.11 and [uv]:

```console
$ uv sync
```

Run the test suite:

```console
$ uv run pytest
```

Run linting and type checks:

```console
$ uv run ruff check src/
$ uv run mypy src/
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
