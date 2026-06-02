# pyado — Python bindings for the Azure DevOps REST API

[![PyPI](https://img.shields.io/pypi/v/pyado.svg)][pypi_]
[![Status](https://img.shields.io/pypi/status/pyado.svg)][status]
[![Python Version](https://img.shields.io/pypi/pyversions/pyado)][python version]
[![License](https://img.shields.io/pypi/l/pyado)][license]
[![Read the Docs](https://img.shields.io/readthedocs/pyado/latest.svg?label=Read%20the%20Docs)][read the docs]
[![Tests](https://github.com/fredstober/pyado/workflows/Tests/badge.svg)][tests]
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)][ruff]
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)][uv]

[pypi_]: https://pypi.org/project/pyado/
[status]: https://pypi.org/project/pyado/
[python version]: https://pypi.org/project/pyado
[read the docs]: https://pyado.readthedocs.io/
[tests]: https://github.com/fredstober/pyado/actions?workflow=Tests
[ruff]: https://github.com/astral-sh/ruff
[uv]: https://github.com/astral-sh/uv

**Typed, Pydantic-backed wrappers and Pythonic convenience methods for the
Azure DevOps REST API — no raw dicts, no string parsing, full IDE completion.**

---

pyado exists to make working with Azure DevOps from Python straightforward
and pleasant. Every endpoint is available as a thin, typed wrapper, and
on top of that a higher-level layer handles the workflows most applications
require: iterating paginated results, constructing multi-part requests,
diffing branches, linking work items, and more. Authentication, retries, and
content-type negotiation are handled transparently — the focus stays on what
your code needs to accomplish.

[![Typing SVG](https://readme-typing-svg.demolab.com?font=Fira+Code&size=16&pause=1500&color=0078D4&vCenter=true&width=720&height=45&lines=for+item+in+pyado.iter_work_item_details%28api%2C+ids%29%3A;pr+%3D+pyado.create_pr%28repo_api%2C+title%3D%22Add+telemetry%22%29;pyado.push_commits%28repo_api%2C+ref_updates%2C+commits%29;for+commit+in+pyado.iter_commits%28repo_api%2C+%22main%22%29%3A)](https://readme-typing-svg.demolab.com)

---

## Quick look

```python
import pyado

api = pyado.ApiCall(
    access_token="<your-pat>",
    url="https://dev.azure.com/<organisation>/<project>/_apis/",
)

# Query work items with WIQL
refs = pyado.post_wiql(api, "SELECT [System.Id] FROM WorkItems WHERE [System.State] = 'Active'")
for item in pyado.iter_work_item_details(api, [ref.id for ref in refs]):
    print(f"#{item.id}  {item.fields['System.Title']}")

# Create a PR and link a work item
repo_api = pyado.get_repository_api_call(api, repo_id)
pr = pyado.create_pr(
    repo_api,
    title="Add telemetry",
    source_branch="feature/telemetry",
    target_branch="main",
    work_item_ids=[item.id],
)
print(f"PR #{pr.pull_request_id} created")

# Push a file change programmatically
result = pyado.push_commits(
    repo_api,
    ref_updates=[pyado.make_ref_update("main", current_sha)],
    commits=[pyado.make_commit("chore: update config", [
        pyado.edit_file("/config/settings.json", '{"key": "value"}'),
    ])],
)
print(f"Pushed commit {result.commits[0].commit_id}")
```

---

## What you get

- **Full type safety** — every function accepts and returns [Pydantic] models.
  Bad inputs are caught at construction, not buried in an HTTP 400 response.
- **No boilerplate** — authentication, session management, retries, and content
  type negotiation are handled for you.
- **Automatic pagination** — functions that return lists are generators that page
  through results transparently. `skip` and `top` are handled internally.
- **Pythonic convenience methods** — common workflows are first-class citizens.
  Iterate all commits on a branch with a `for` loop. Create a PR and attach work
  items in one call. Push file changes without touching git internals. The
  underlying REST mechanics are abstracted away.
- **Everything covered** — work items, pull requests, repositories, git push,
  builds, pipeline runs, pipeline task callbacks, variable groups, approvals,
  projects, and user profiles.

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

---

## Is pyado right for you?

Microsoft also publishes an official [`azure-devops`][azure-devops-pkg] Python
package. See the **[alternatives comparison][alternatives]** for a side-by-side
overview to help you decide which package fits your use case.

---

## Further reading

- **[Full usage guide][usage]** — every domain with detailed examples
- **[API reference][read the docs]** — auto-generated from docstrings
- **[Contributor Guide]** — coding standards, architecture, and how to get started

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
