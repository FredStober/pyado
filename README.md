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

[![Typing SVG](https://readme-typing-svg.demolab.com?font=Fira+Code&size=15&pause=2500&color=0078D4&vCenter=true&width=760&height=45&lines=svc+%3D+pyado.AzureDevOpsService%28org%3D%22myorg%22%2C+pat%3D%22...%22%29;proj+%3D+svc.org.get_project%28%22MyProject%22%29;repo+%3D+proj.get_repository%28%22backend%22%29;pr+%3D+repo.create_pr%28title%3D%22Deploy+v2.1%22%2C+source_branch%3D%22feature%2Fv2%22%29;pr.add_reviewer%28reviewer_id%2C+is_required%3DTrue%29;pr.add_label%28%22ready-to-merge%22%29;pr.link_work_item%28wi%29;wi+%3D+proj.get_work_item%28153%29%3B+wi.update%28%7B%22System.State%22%3A+%22Resolved%22%7D%29;build+%3D+proj.start_build%2842%2C+source_branch%3D%22refs%2Fheads%2Fmain%22%29;for+stage+in+build.iter_stages%28%29%3A+print%28stage.name%2C+stage.result%29;repo.commit%28%22main%22%2C+%22chore%3A+update+config%22%2C+%5BEditFile%28...%29%5D%29;vg+%3D+proj.get_variable_group%28%22my-secrets%22%29%3B+vg.set_variable%28%22KEY%22%2C+%22v2%22%29)](https://readme-typing-svg.demolab.com)

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

## OOP interface

Navigate a hierarchy of resource objects instead of threading `ApiCall`
arguments through every call. Import via `from pyado.oop import
AzureDevOpsService`, or use `pyado.AzureDevOpsService` directly.

```python
import pyado

# Construct once — org URL and PAT also resolve from env vars
# (AZURE_DEVOPS_ORG / SYSTEM_TEAMFOUNDATIONCOLLECTIONURI, AZURE_DEVOPS_EXT_PAT)
svc  = pyado.AzureDevOpsService(org="https://dev.azure.com/myorg", pat="<pat>")
proj = svc.org.get_project("MyProject")

# Repositories and file pushes — no local git required
repo = proj.get_repository("myrepo")
print(repo.default_branch)               # "refs/heads/main"
repo.commit("main", "chore: update config", [
    pyado.EditFile("/config.json", '{"key": "value"}'),
    pyado.DeleteFile("/old_config.json"),
])

# Pull requests — branch names normalised automatically
pr = repo.create_pr(
    title="Deploy v2.1",
    source_branch="feature/v2",
    target_branch="main",
    description="Promotes the v2 feature branch to main.",
)
pr.add_reviewer(reviewer_id, is_required=True)
pr.add_label("ready-to-merge")
pr.link_work_item(wi)                     # artifact link on the work item + PR page

# Work items — full CRUD
wi = proj.get_work_item(153)
print(wi.title, wi.state)                 # "Fix the bug"  "Active"
wi.update({"System.State": "Resolved"})
wi.add_tag("reviewed")
wi.add_comment("Confirmed in staging — closing.", comment_format="markdown")

# Builds and pipelines
build = proj.start_build(42, source_branch="refs/heads/main")
print(build.status, build.number)
for stage in build.iter_stages():
    print(stage.name, stage.result)
    for job in stage.iter_jobs():
        for task in job.iter_tasks():
            print(f"  {task.name}: {task.result}")

pipeline = proj.get_pipeline(99)
run = pipeline.start_run(template_parameters={"env": "staging"})

# Variable groups — secret-safe read-modify-write
vg = proj.get_variable_group("my-secrets")
vg.set_variable("KEY", "v2")
vg.set_variable("TOKEN", "abc123", is_secret=True)
```

See the **[full OOP usage guide][oop-usage]** for all classes and methods.

---

## Authentication

pyado resolves credentials from three sources, checked in order:

| Source | Argument | Environment variable |
|---|---|---|
| Personal access token | `pat="<token>"` | `AZURE_DEVOPS_EXT_PAT` |
| Organisation URL | `org="https://dev.azure.com/myorg"` | `AZURE_DEVOPS_ORG` or `SYSTEM_TEAMFOUNDATIONCOLLECTIONURI` |
| Azure identity | `credential=DefaultAzureCredential()` | _(any azure-identity flow)_ |

```python
# From environment variables — useful in CI/CD
svc = pyado.AzureDevOpsService()

# Azure managed identity or workload identity federation
from azure.identity import DefaultAzureCredential
svc = pyado.AzureDevOpsService(
    org="https://dev.azure.com/myorg",
    credential=DefaultAzureCredential(),
)

# Inject a custom SSL session (corporate CAs, proxies, etc.)
import requests
session = requests.Session()
session.verify = "/etc/ssl/certs/corporate-ca.pem"
svc = pyado.AzureDevOpsService(
    org="https://dev.azure.com/myorg",
    pat="<pat>",
    session=session,
)
```

The underlying `requests.Session` is LRU-cached per access token, so
constructing multiple `ApiCall` objects with the same token all share
a single connection pool — no reconnect overhead.

---

## Raw API

For scripts or advanced use-cases that need direct endpoint access, import
from `pyado.raw`:

```python
from pyado.raw import (
    ApiCall,
    get_repository_api_call,
    post_wiql,
    get_work_item_api_call,
    get_work_item,
    iter_refs,
    make_ref_update,
    post_push,
    GitPushRequest,
    GitPushCommit,
    GitPushChange,
    GitPushNewContent,
    GitPushContentType,
    post_pull_request,
    PullRequestCreateRequest,
)

# A project-level ApiCall is the root credential object.
# Derive more scoped calls from it via get_*_api_call helpers.
api = ApiCall(
    access_token="<your-pat>",
    url="https://dev.azure.com/<organisation>/<project>/_apis/",
)

# Query work items with WIQL
refs = post_wiql(api, "SELECT [System.Id] FROM WorkItems WHERE [System.State] = 'Active'")
for ref in refs:
    item = get_work_item(get_work_item_api_call(api, ref.id))
    print(f"#{item.id}  {item.fields['System.Title']}")

# Push a file change programmatically — no local git clone required
repo_api = get_repository_api_call(api, repo_id)
current_sha = next(r.object_id for r in iter_refs(repo_api, name_filter="heads/main"))
result = post_push(
    repo_api,
    GitPushRequest(
        ref_updates=[make_ref_update("main", current_sha)],
        commits=[GitPushCommit(
            comment="chore: update config",
            changes=[GitPushChange(
                change_type="edit",
                item={"path": "/config/settings.json"},
                new_content=GitPushNewContent(
                    content='{"key": "value"}',
                    content_type=GitPushContentType.raw_text,
                ),
            )],
        )],
    ),
)
print(f"Pushed commit {result.commits[0].commit_id}")

# Create a PR — branch names must be full refs at the raw layer
pr = post_pull_request(
    repo_api,
    PullRequestCreateRequest(
        title="Update config",
        source_ref_name="refs/heads/feature/update-config",
        target_ref_name="refs/heads/main",
    ),
)
print(f"PR #{pr.pull_request_id} created")
```

---

## What you get

- **Full type safety.** Every function accepts and returns [Pydantic] models.
  Bad inputs — wrong URL scheme, missing required field, invalid UUID — are
  caught at construction time with a clear validation error, not buried inside
  an HTTP 400 response long after the call was made. IDE completion works on
  every field of every request and response model.

- **No boilerplate.** Authentication (Basic Auth with PAT or Azure identity),
  session management (LRU-cached connection pools keyed on the token),
  automatic retries on transient connection resets, and content-type
  negotiation (JSON vs JSON Patch vs octet-stream) are handled transparently.
  Every call site looks the same.

- **Automatic pagination.** Every list endpoint returns a plain Python
  generator. Page boundaries, `$skip`/`$top` bookkeeping, and the ADO diff
  endpoint's `allChangesIncluded` stop flag are managed internally. Write a
  `for` loop, get all items.

- **Optimistic concurrency for git operations.** pyado reads the current HEAD
  SHA before every push and passes it as `old_object_id`, so concurrent pushes
  to the same branch cannot silently overwrite each other — ADO rejects the
  later write, and the caller retries with the updated SHA. `ZERO_SHA` marks
  branch creation (reject if already exists) and branch deletion (set HEAD to
  null).

- **Pythonic convenience methods.** The OOP layer wraps multi-step ADO
  workflows behind clean, intent-expressing methods. Push a commit without
  touching git internals. Create a PR and attach work items in two lines. Fetch
  all log output for a build in a single call. Manage tags on work items as
  plain Python lists, with case-insensitive deduplication matching ADO's own
  normalisation.

- **Shared object identity.** The OOP service deduplicates resource objects
  by identity: `build.project is wi.project` is guaranteed when both objects
  belong to the same project, regardless of how they were fetched. Back
  navigation (`.project`, `.repo`, `.org`) is always zero-cost.

- **Everything covered.** Work items (full CRUD, WIQL queries, comments,
  attachments, tags, relations, artifact links), pull requests (lifecycle,
  reviewers, threads, status checks, labels, iterations, auto-complete), git
  repositories (push, refs, branches, diffs, commits, ACLs), builds (queue,
  cancel, retry, stages/jobs/tasks, logs, artifacts, tags), pipelines (YAML
  runs, template parameters, resource permissions, approvals), variable groups
  (read, write, secrets, create, delete), teams (members, sprint iterations,
  area paths), classification nodes (iterations, areas), and user profiles.

- **Pipeline task callback support.** pyado exposes the full distributed task
  plane API used inside Azure Pipelines agent jobs: write to the task feed and
  task log in real time, update timeline record state, and signal completion
  from an external process or serverless function.

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

- **[OOP interface guide][oop-usage]** — all OOP classes and methods with examples
- **[Full usage guide][usage]** — every domain with detailed examples
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
[oop-usage]: https://github.com/fredstober/pyado/blob/main/docs/usage.md#oop-interface
[quick-reference]: https://github.com/fredstober/pyado/blob/main/docs/quick_reference.md
[alternatives]: https://github.com/fredstober/pyado/blob/main/docs/alternatives.md
