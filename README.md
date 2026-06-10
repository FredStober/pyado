# pyado — Python bindings for the Azure DevOps REST API

[![PyPI](https://img.shields.io/pypi/v/pyado.svg)][pypi_]
[![Status](https://img.shields.io/pypi/status/pyado.svg)][status]
[![Python Version](https://img.shields.io/pypi/pyversions/pyado)][python version]
[![License](https://img.shields.io/pypi/l/pyado)][license]
[![Read the Docs](https://img.shields.io/readthedocs/pyado/latest.svg?label=Read%20the%20Docs)][read the docs]
[![Tests](https://github.com/fredstober/pyado/workflows/Tests/badge.svg)][tests]
[![Coverage](https://codecov.io/gh/fredstober/pyado/branch/main/graph/badge.svg)][coverage]
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)][ruff]
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)][uv]

[pypi_]: https://pypi.org/project/pyado/
[status]: https://pypi.org/project/pyado/
[python version]: https://pypi.org/project/pyado
[read the docs]: https://pyado.readthedocs.io/
[tests]: https://github.com/fredstober/pyado/actions?workflow=Tests
[coverage]: https://codecov.io/gh/fredstober/pyado
[ruff]: https://github.com/astral-sh/ruff
[uv]: https://github.com/astral-sh/uv

<p align="center">
  <img src="docs/banner.svg" alt="pyado — Python bindings for the Azure DevOps REST API" width="860"/>
</p>

[![Typing SVG](https://readme-typing-svg.demolab.com?font=Fira+Code&size=15&pause=2500&color=0078D4&vCenter=true&width=760&height=45&lines=pr+%3D+repo.create_pull_request%28%22Deploy+v2.1%22%2C+%22feature%2Fv2%22%2C+%22main%22%29;wi.update%28%7B%22System.State%22%3A+%22Resolved%22%7D%29;build+%3D+proj.pipelines.start_build%28pipeline%29;vg.set_variable%28%22API_TOKEN%22%2C+%22secret-v2%22%2C+is_secret%3DTrue%29;repo.commit%28%22main%22%2C+%22chore%3A+update+config%22%2C+%5BEditFile%28...%29%5D%29;for+pr+in+proj.repos.iter_active_prs%28%29%3A+print%28pr.title%29)](https://readme-typing-svg.demolab.com)

**Typed, Pydantic-backed wrappers and Pythonic convenience methods for the
Azure DevOps REST API — no raw dicts, no string parsing, full IDE completion.**

---

pyado wraps the Azure DevOps REST API at two levels so you can pick the right
abstraction for the job.

The **raw layer** (`pyado.raw`) is a thin, one-function-per-endpoint mapping of
the ADO REST surface. Every function accepts an `ApiCall` credential object and
one or more fully-typed [Pydantic] request models, then returns a fully-typed
Pydantic response model. Bad inputs are caught at model construction time, before
any HTTP request is ever issued. Pagination is transparent: list endpoints return
plain Python generators that fetch the next page automatically when the iterator
advances.

The **OOP layer** (`pyado.oop`, also re-exported at the top-level `pyado`)
builds on top of the raw layer and exposes every ADO resource as a Python object.
`AzureDevOpsService` is the single entry point; from there you navigate a strict
ownership hierarchy down to repositories, pull requests, work items, builds,
pipelines, variable groups, teams, and classification nodes. Objects cache their
data lazily on first access and share identity across paths — fetching
`build.project` and calling `org.get_project("MyProject")` both return the exact
same `Project` instance. Authentication, retries, connection pooling, and
content-type negotiation are handled entirely by the framework.

---

## Common operations

```python
import pyado

# Credentials come from env vars if not passed explicitly:
#   AZURE_DEVOPS_ORG (or SYSTEM_TEAMFOUNDATIONCOLLECTIONURI)
#   AZURE_DEVOPS_EXT_PAT
svc  = pyado.AzureDevOpsService(org="https://dev.azure.com/myorg", pat="<pat>")
proj = svc.org.get_project("MyProject")
```

### Work items

```python
# Fetch and update a work item
wi = proj.boards.get_work_item(153)
print(wi.title, wi.state)
wi.update({"System.State": "Resolved"})
wi.add_tag("reviewed")
wi.add_comment("Confirmed in staging.", comment_format="markdown")

# Query with WIQL
for wi in proj.boards.iter_work_items(
    "SELECT [System.Id] FROM WorkItems WHERE [System.State] = 'Active'"
):
    print(wi.id, wi.title)

# Create a work item
wi = proj.boards.create_work_item(
    "Task",
    fields={"System.Title": "Investigate memory leak", "System.AssignedTo": "jane@example.com"},
)
```

### Pull requests

```python
repo = proj.repos.get_repository("myrepo")

# Create — branch names are normalised automatically
pr = repo.create_pull_request(
    title="Deploy v2.1",
    source_branch="feature/v2",
    target_branch="main",
    description="Promotes the v2 feature branch.",
)
pr.add_reviewer(reviewer_id, is_required=True)
pr.add_label("ready-to-merge")
pr.link_work_item(wi)          # shows on both the PR page and the work item

# List all active PRs across every repo in the project
for pr in proj.repos.iter_active_prs():
    print(pr.repo.name, pr.title, pr.status)

# Complete a PR
pr.enable_auto_complete()
pr.complete(last_merge_source_commit=pr.info.last_merge_source_commit.commit_id)
```

### Builds and pipelines

```python
# Queue a build
pipeline = proj.pipelines.get_pipeline("deploy-prod")
build = proj.pipelines.start_build(pipeline, source_branch="refs/heads/main")
print(build.id, build.number, build.status)

# Inspect stages, jobs, and tasks
for stage in build.iter_stages():
    for job in stage.iter_jobs():
        for task in job.iter_tasks():
            print(f"  {task.name}: {task.result}")

# Trigger a YAML pipeline run with template parameters
run = pipeline.start_run(template_parameters={"env": "staging"})

# Approve a pending environment gate
for approval in proj.pipelines.iter_approvals():
    proj.pipelines.approve(approval.id, comment="LGTM")
```

### Repositories and file commits

```python
# Read file content — no local git clone required
text = repo.get_file_at_branch("/config.json", "main")

# Push changes programmatically
result = repo.commit("main", "chore: update config", [
    pyado.EditFile("/config.json", '{"key": "value"}'),
    pyado.DeleteFile("/old_config.json"),
    pyado.AddFile("/new_file.txt", "hello"),
])
print(result.commits[0].commit_id)

# Branches and tags
repo.create_branch("feature/new-branch", from_commit="abc123")
repo.create_tag("v1.2.3", "abc123")
for tag in proj.repos.iter_git_tags("myrepo"):
    print(tag.name, tag.commit_id)
```

### Variable groups

```python
vg = proj.pipelines.library.get_variable_group("my-secrets")

# Read-modify-write — safe for concurrent callers
vg.set_variable("API_KEY", "new-value")
vg.set_variable("API_SECRET", "s3cr3t", is_secret=True)
vg.delete_variable("DEPRECATED_KEY")
vg.refresh()
```

### Teams and iterations

```python
team = proj.boards.get_team("Backend Team")
for sprint in team.iter_sprint_iterations():
    print(sprint.name, sprint.attributes.start_date)

for member in team.iter_members():
    print(member.identity.display_name)
```

### Service hooks

```python
# List all webhook subscriptions
for sub in org.iter_hook_subscriptions():
    print(sub.publisher_id, sub.event_type, sub.consumer_id)

# Create a webhook that fires on every completed build
from pyado.raw import HookSubscriptionCreateRequest

org.create_hook_subscription(HookSubscriptionCreateRequest(
    publisher_id="tfs",
    event_type="build.complete",
    resource_version="1.0",
    consumer_id="webHooks",
    consumer_action_id="httpRequest",
    publisher_inputs={"projectId": "<project-id>"},
    consumer_inputs={"url": "https://hooks.example.com/ado"},
))
```

### Task groups

```python
for tg in proj.pipelines.iter_task_groups():
    print(tg.name, tg.description)

tg = proj.pipelines.get_task_group("my-deploy-steps")
```

See the **[full usage guide][usage]** for all domains and the raw API.

---

## Authentication

pyado resolves credentials from three sources, checked in order:

| Source | Argument | Environment variable |
|---|---|---|
| Personal access token | `pat="<token>"` | `AZURE_DEVOPS_EXT_PAT` |
| Organisation URL | `org="https://dev.azure.com/myorg"` | `AZURE_DEVOPS_ORG` or `SYSTEM_TEAMFOUNDATIONCOLLECTIONURI` |
| Azure identity | `credential=DefaultAzureCredential()` | _(any azure-identity flow)_ |

```python
# From environment variables — useful in CI/CD (SYSTEM_ACCESSTOKEN works too)
svc = pyado.AzureDevOpsService()

# Azure managed identity or workload identity federation
from azure.identity import DefaultAzureCredential
svc = pyado.AzureDevOpsService(
    org="https://dev.azure.com/myorg",
    credential=DefaultAzureCredential(),
)
```

The underlying `requests.Session` is LRU-cached per access token, so
constructing multiple `ApiCall` objects with the same token all share
a single connection pool — no reconnect overhead.

---

## What you get

- **Full type safety.** Every function accepts and returns [Pydantic] models.
  Bad inputs — wrong URL scheme, missing required field, invalid UUID — are
  caught at construction time with a clear validation error, not buried inside
  an HTTP 400 response long after the call was made. IDE completion works on
  every field of every request and response model.

- **No boilerplate.** Authentication (PAT or Azure identity), session management
  (LRU-cached connection pools keyed on the token), automatic retries on
  transient connection resets, and content-type negotiation (JSON vs JSON Patch
  vs octet-stream) are handled transparently. Every call site looks the same.

- **Automatic pagination.** Every list endpoint returns a plain Python
  generator. Page boundaries, `$skip`/`$top` bookkeeping, and the ADO diff
  endpoint's `allChangesIncluded` stop flag are managed internally. Write a
  `for` loop, get all items.

- **Optimistic concurrency for git operations.** pyado reads the current HEAD
  SHA before every push and passes it as `old_object_id`, so concurrent pushes
  to the same branch cannot silently overwrite each other — ADO rejects the
  later write, and the caller retries with the updated SHA.

- **Pythonic convenience methods.** Push a commit without touching git
  internals. Create a PR and attach work items in two lines. Fetch all log
  output for a build in a single call. Manage tags on work items as plain
  Python lists, with case-insensitive deduplication matching ADO's own
  normalisation.

- **Shared object identity.** The OOP service deduplicates resource objects
  by identity: `build.project is wi.project` is guaranteed when both objects
  belong to the same project, regardless of how they were fetched. Back
  navigation (`.project`, `.repo`, `.org`) is always zero-cost.

- **Everything covered.** Work items, pull requests, git repositories, builds,
  YAML pipeline runs, variable groups, teams, iterations and areas, wikis,
  dashboards, policies, search, environments and deployment approvals, agent
  pools and queues, secure files, service endpoints, service hooks, task groups,
  work process templates, notification subscriptions, and the full distributed
  task plane API for pipeline task callbacks.

---

## Installation

```console
$ pip install pyado
```

or with [uv]:

```console
$ uv add pyado
```

Requires Python 3.11 and an Azure DevOps [personal access token (PAT)][pat].
The `azure-identity` package is optional; install it only if you need
managed identity or federated workload authentication:

```console
$ pip install pyado[azure-identity]
```

---

## Is pyado right for you?

Microsoft also publishes an official [`azure-devops`][azure-devops-pkg] Python
package. See the **[alternatives comparison][alternatives]** for a side-by-side
overview to help you decide which package fits your use case.

---

## Further reading

- **[Full usage guide][usage]** — every domain with detailed examples including the raw API
- **[API reference][read the docs]** — auto-generated from docstrings
- **[Contributor Guide]** — coding standards, architecture, and how to get started
- **[Alternatives][alternatives]** — side-by-side comparison with `azure-devops` and raw `requests`

---

## Contributing

Contributions are very welcome. See the [Contributor Guide] for details.

## License

Distributed under the terms of the [MIT license][license].
_pyado_ is free and open source software.

## Issues

Please [file an issue] with a detailed description of the problem.

<!-- github-only -->

[pydantic]: https://docs.pydantic.dev/
[pat]: https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate
[azure-devops-pkg]: https://pypi.org/project/azure-devops/
[file an issue]: https://github.com/fredstober/pyado/issues
[uv]: https://docs.astral.sh/uv/
[license]: https://github.com/fredstober/pyado/blob/main/LICENSE
[contributor guide]: https://github.com/fredstober/pyado/blob/main/CONTRIBUTING.md
[usage]: https://github.com/fredstober/pyado/blob/main/docs/usage.md
[alternatives]: https://github.com/fredstober/pyado/blob/main/docs/alternatives.md
