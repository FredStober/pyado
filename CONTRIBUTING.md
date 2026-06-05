# Contributor Guide

Thank you for your interest in improving pyado.
The project is open-source under the [MIT license] and welcomes bug reports,
feature requests, and pull requests.

- [Source Code]
- [Documentation]
- [Issue Tracker]
- [Code of Conduct]

**Quick links for development:**
[Usage guide](docs/usage.md) ·
[Quick reference](docs/quick_reference.md) ·
[API reference](https://pyado.readthedocs.io/) ·
[Architecture](#package-architecture) ·
[Coding standards](#coding-standards) ·
[Adding new functionality](#adding-new-functionality)

pyado uses Python 3.11, [uv] for dependency management, [ruff] for linting
and formatting, [mypy] in strict mode for type checking, and [pytest] with
100 % branch coverage enforced. All of these are configured in
`pyproject.toml`; no tool needs a separate config file.

[mit license]: https://opensource.org/licenses/MIT
[source code]: https://github.com/fredstober/pyado
[documentation]: https://pyado.readthedocs.io/
[issue tracker]: https://github.com/fredstober/pyado/issues

---

## Reporting bugs

File a bug report on the [Issue Tracker]. Include:

- Operating system and Python version
- pyado version (`pip show pyado`)
- What you did
- What you expected
- What actually happened (full traceback if applicable)

The fastest path to a fix is a minimal reproducible test case.

## Requesting features

Open a feature request on the [Issue Tracker]. Describe the use case and why
pyado is the right place to solve it (rather than, say, calling `build_call()`
directly). It helps to open a discussion before writing code — this avoids
work that might not align with the project's design.

---

## Setting up a development environment

You need **Python 3.11** and [uv].

```console
$ git clone https://github.com/fredstober/pyado
$ cd pyado
$ uv sync
```

`uv sync` installs the package and all development dependencies into an
isolated virtualenv. Activate it or prefix every command with `uv run`:

```console
$ uv run python
```

[uv]: https://docs.astral.sh/uv/

---

## Running the tests

```console
$ uv run pytest
```

The test suite enforces **100% branch coverage**. Every new code path must be
covered by a test. The coverage report is printed automatically; failed coverage
fails the build.

Tests live in `tests/`. Naming conventions:

| Thing | Convention |
|---|---|
| Test file | `test_<module_name>.py` |
| Test function | `test_<functionality>_<expected_behaviour>()` |

Keep test data realistic but synthetic. No PII. Avoid over-mocking — test
observable behaviour, not internal call sequences.

---

## Linting, formatting, and type checking

Run all pre-commit hooks in one shot:

```console
$ uv run prek run -a
```

Or run individual tools:

```console
$ uv run ruff check src/          # lint
$ uv run ruff format --check src/ # format check
$ uv run mypy src/                 # type checking (strict mode)
```

mypy runs in **strict mode** with `warn_unreachable = true`. Every new function
and class must be fully annotated. No `# type: ignore` suppressions.

### detect-secrets

pyado uses [detect-secrets] to prevent accidentally committing tokens or keys.
If the baseline becomes stale (e.g. after adding a string that looks like a
secret), regenerate it:

```console
$ uv run detect-secrets scan > .secrets.baseline
$ git add .secrets.baseline
```

[detect-secrets]: https://github.com/Yelp/detect-secrets

---

## Coding standards

### Language and runtime

- **Python 3.11 only** — `requires-python = ">=3.11"`
- **Double quotes** for strings
- `snake_case` for variables and functions, `PascalCase` for classes,
  `UPPER_SNAKE_CASE` for module-level constants

### Style tooling

| Tool | Role | Config |
|---|---|---|
| [ruff] | Lint + format | `pyproject.toml` — `select = ["ALL"]` |
| [mypy] | Type checking | strict mode |
| [pytest] | Test runner | 100% branch coverage enforced |

The ruff configuration uses `select = ["ALL"]` with a small set of explicit
ignores. Do not add new ignores without discussion.

[ruff]: https://docs.astral.sh/ruff/
[mypy]: https://mypy.readthedocs.io/
[pytest]: https://pytest.readthedocs.io/

### Docstrings

Google-style docstrings are required on every public module, class, and
function. Private helpers (`_prefixed`) do not require docstrings but benefit
from them when the logic is non-obvious.

```python
def my_function(api_call: ApiCall, work_item_id: WorkItemId) -> WorkItemInfo:
    """Return full work item data for a single ID.

    Args:
        api_call: Work-item-level ADO API call.
        work_item_id: Integer ID of the work item to fetch.

    Returns:
        WorkItemInfo with all fields and relations populated.

    Raises:
        RuntimeError: If the ADO API returns a non-2xx response.
    """
```

### Design principles (in priority order)

1. **KISS** — write the simplest thing that works.
2. **SOLID** — single responsibility, open/closed, etc.
3. **DRY** — don't repeat yourself.
4. **YAGNI** — no code for hypothetical future requirements.

Practical rules that follow from these:

- No global state — pass everything explicitly.
- No error handling for scenarios that cannot happen.
- No abstractions for code that appears only once.
- No features beyond what was asked.

### Pydantic models

All request and response types are Pydantic v2 `BaseModel` subclasses.
Raw `dict` is never returned from any public function.

- **Multi-field request models are public** (no `_` prefix) — callers may need
  to construct them directly.
- Single-field internal wrappers may be private.
- Never use `model_config = ConfigDict(populate_by_name=True)` as a shortcut
  to avoid aliasing correctly — keep the alias and expose the Python-friendly
  name through the field definition.

---

## Package architecture

pyado has two layers.  All raw functions are re-exported through the top-level
`pyado` namespace.  The OOP layer is a preview API imported from `pyado.oop`.

```
src/pyado/
├── __init__.py         ← re-exports everything from raw/
├── raw/                ← one function per ADO REST endpoint
│   ├── _core.py        ← ApiCall, shared primitive types, HTTP machinery
│   ├── build.py
│   ├── git.py
│   ├── identity.py
│   ├── pipeline.py
│   ├── profile.py
│   ├── project.py
│   ├── pull_request.py
│   ├── variable_group.py
│   └── work_item.py
└── oop/                ← OOP resource objects (preview layer)
    ├── service.py      ← AzureDevOpsService, entry point
    ├── organization.py
    ├── project.py
    ├── repository.py
    ├── pull_request.py
    ├── work_item.py
    ├── build.py
    ├── pipeline.py
    ├── variable_group.py
    ├── team.py
    ├── iteration.py
    ├── area.py
    ├── _build.py       ← private helpers: payload construction + multi-step logic
    ├── _git.py
    ├── _pull_request.py
    ├── _variable_group.py
    └── _work_item.py
```

### The two layers

| Layer | Responsibility |
|---|---|
| `pyado.raw` | One function per ADO REST endpoint. Accepts fully-built Pydantic request models; returns Pydantic response models. No payload construction, no pagination, no multi-step logic. |
| `pyado.oop` | OOP resource objects (`AzureDevOpsService → Organization → Project → …`). Private helpers (`oop/_*.py`) accept plain Python values, construct request models, own pagination loops, and orchestrate multi-step operations. All HTTP goes through `pyado.raw`. |

### Rules for `raw/`

1. **One function per endpoint.** No multi-step logic.
2. **Accept fully-built Pydantic request models.** Do not construct models
   from primitive arguments inside a `raw/` function.
3. **Return Pydantic response models.** Never a raw `dict`.
4. **Public request models.** Multi-field request models must be public (no
   `_` prefix) so callers can reference them if needed.

### Rules for `oop/` private helpers

The private modules (`oop/_build.py`, `oop/_git.py`, `oop/_pull_request.py`,
`oop/_variable_group.py`, `oop/_work_item.py`) bridge the OOP objects and the
`raw/` layer.

1. **Accept primitive arguments.** Strings, ints, enums — no Pydantic models
   at the call site unless there is no simpler alternative.
2. **Construct request models internally.** Build the Pydantic model, then
   pass it to the corresponding `raw/` function.
3. **Own pagination.** `iter_*` functions yield individual items and page
   through results internally — callers should never need to manage `skip`/`top`.
4. **Delegate all HTTP to `raw/`.** Never call `api_call.get()` / `.post()` /
   `.patch()` / `.delete()` directly from `oop/` modules.
5. **Intent-expressing names are allowed.** `push_commits` wrapping `post_push`,
   or `start_build` wrapping `post_build`, is fine.

---

## Design decisions

This section explains the *why* behind the less obvious choices in pyado's
implementation.

### `ApiCall` session caching

`ApiCall._get_session` is decorated with `@lru_cache(maxsize=8)` keyed on the
access token string.  The cache is intentional: `requests.Session` holds an
internal connection pool.  Reusing the same session object for every call that
shares a token avoids negotiating a new TLS connection on each request.  The
cache is bounded at 8 so applications that use a small number of tokens still
benefit without accumulating sessions indefinitely.

A practical consequence: do not recreate `ApiCall` on every call.  Construct it
once and pass it around — the underlying session and its connection pool are
shared automatically.

### Content-type negotiation

ADO expects different `Content-Type` headers depending on the operation:

| Payload | Content-Type |
|---|---|
| Regular JSON body | `application/json` |
| JSON Patch sequence | `application/json-patch+json` |
| Raw bytes (file upload) | `application/octet-stream` |

`_get_content_type` detects the payload type from the value being sent.  A list
of dicts each containing `op` and `path` keys is treated as a JSON Patch
document; raw `bytes` triggers the octet-stream type; everything else uses
`application/json`.  Callers never specify the content-type directly — it
follows from the shape of the request.

### Why JSON Patch for work item mutations

The ADO Work Item Tracking API uses [JSON Patch][jsonpatch] (RFC 6902) for all
mutations.  A field update, a relation addition, and a multiline-format hint are
all expressed as patch operations with a `path` and a `value`.  This is an API
constraint imposed by Microsoft, not a pyado choice.  `JsonPatchAdd` models the
only operation type pyado requires — `op: "add"`, which ADO uses both for adding
new values and for overwriting existing ones.

The `multilineFieldsFormat` patch path (`/multilineFieldsFormat/<field>`) is a
pyado-discovered extension that ADO accepts in the same PATCH request alongside
field values.  It tells the ADO UI to render the field as markdown rather than
plain text.

[jsonpatch]: https://jsonpatch.com/

### Error extraction

When ADO returns a non-2xx response, pyado tries to extract a human-readable
message in order:

1. Parse the body as JSON and return `body["message"]`.
2. If the body is HTML (e.g. an IIS or gateway error page), strip tags with
   `HTMLTextFilter` and return the visible text.
3. Fall back to `repr(response.content)`.

This layered approach handles both well-formed ADO error JSON and the raw HTML
pages that ADO gateway proxies sometimes return for infrastructure-level errors.
All three cases surface as `RuntimeError` with a readable message.

### Retry strategy

`ApiCall._request` retries up to 3 times, but only on `ConnectionResetError` —
a TCP-level reset that occurs when a long-lived pooled connection is silently
closed by the server between requests.  HTTP-level errors (4xx, 5xx) are *not*
retried, because they represent definitive ADO responses that would return the
same error on every attempt.

### Optimistic concurrency for git ref mutations

ADO's ref update API requires both an `old_object_id` (the SHA the caller
expects the branch HEAD to be at) and a `new_object_id` (the desired new SHA).
If the branch has moved between reading the SHA and submitting the update, ADO
rejects the request.  This is *optimistic concurrency control*: ADO holds no
server-side lock; instead it validates that the caller's expectation of the
current state still holds at commit time.

`ZERO_SHA` (`"000...0"`) is git's conventional null SHA, meaning "this ref does
not exist".  Using it as `old_object_id` tells ADO to create the branch only if
it does not yet exist, and reject the operation if it already does.  Using
`ZERO_SHA` as `new_object_id` on an existing branch deletes it.

### Pagination via `skip` and `top`

ADO REST endpoints that return collections accept `$skip` (offset) and `$top`
(page size) query parameters.  `iter_*` functions manage these internally.
`iter_commit_diff` additionally inspects the `all_changes_included` flag in
each page response — when `True`, the current page is the last one and iteration
stops without issuing a further request.  This is necessary because the diff
endpoint does not return a total count, so the only reliable stop condition is
the flag.

### Attachment upload is two steps

ADO separates file storage from work item data.  An attachment must first be
uploaded to the attachment store (`POST .../wit/attachments`), which returns a
permanent URL.  That URL is then added to the work item as an `AttachedFile`
relation via a JSON Patch operation.  `add_work_item_attachment` performs both
steps in sequence from the caller's perspective, but if the second step fails
(network error, permission problem), the file remains uploaded but unlinked.
Re-running the call will upload a second copy — ADO does not de-duplicate by
content.

### Tags as semicolons

ADO stores work item tags as a single semicolon-and-space-separated string in
the `System.Tags` field (e.g. `"bug; hotfix; reviewed"`).  pyado parses this on
read and re-serialises it on write, exposing tags as a plain Python list.
Comparison inside `add_work_item_tag` and `remove_work_item_tag` is
case-insensitive because ADO normalises tag casing in the UI — adding `"Bug"` to
a work item that already has `"bug"` would produce a duplicate visible only
through case difference.

### Branch name normalisation

Several functions accept a branch name as either a short name (`"main"`) or a
full ref (`"refs/heads/main"`).  The private `_full_ref` helper in
`oop/_pull_request.py` canonicalises both forms to `"refs/heads/<name>"` because
ADO's ref mutation APIs require the full path.  Functions that only *read* refs
(e.g. `iter_refs`) do not apply this normalisation because the `nameFilter`
query parameter accepts a prefix without the `refs/` root.

---

## Adding new functionality

Follow these steps whenever adding support for a new ADO endpoint or building a
new higher-level helper:

1. **`raw/` first.** Add the HTTP call and any request/response Pydantic models
   to the appropriate domain module (e.g. `raw/git.py`). If the endpoint needs
   a new multi-field request model, make it public.

2. **Export from `raw/`.** Add new public symbols to `raw/__init__.py` and
   `pyado/__init__.py`.

3. **`oop/_*.py` if needed.** If the new endpoint benefits from payload
   construction, pagination, or multi-step orchestration, add a helper in the
   matching private module (e.g. `oop/_git.py`) and expose a method on the
   relevant OOP class (e.g. `Repository`).

4. **Tests.** Add unit tests. Coverage must remain at 100%.

5. **Docs.** Add an example to `docs/usage.md` if the new function is
   user-facing.

### Example: adding a new `raw/` function

```python
# raw/work_item.py

def get_work_item_revisions(
    work_item_api_call: ApiCall,
) -> list[WorkItemInfo]:
    """Return all historical revisions of a work item.

    Args:
        work_item_api_call: Work-item-level ADO API call (from
            get_work_item_api_call).

    Returns:
        List of WorkItemInfo, one per revision, oldest first.
    """
    response = work_item_api_call.get("revisions", version="7.0")
    return _WorkItemInfoResults.model_validate(response).value
```

---

## Building the documentation

Documentation is built with [Sphinx] and [MyST Parser] — the source files are
Markdown, and the API reference is generated automatically from docstrings via
`sphinx.ext.autodoc`.

Install the docs dependencies (separate from the default dev group):

```console
$ uv sync --group docs
```

Build HTML output into `docs/_build/html/`:

```console
$ uv run --group docs sphinx-build docs docs/_build/html
```

Open `docs/_build/html/index.html` in a browser to review the result.

For live-reload during editing, add `sphinx-autobuild` on the fly:

```console
$ uv run --group docs --with sphinx-autobuild sphinx-autobuild docs docs/_build/html
```

### Docs source layout

| File | Purpose |
|---|---|
| `docs/conf.py` | Sphinx configuration (extensions, theme) |
| `docs/index.md` | Landing page; pulls top section of `README.md` via `{include}` |
| `docs/usage.md` | Full usage guide with worked examples — see also [Usage Guide] |
| `docs/reference.md` | API reference — auto-generated from module docstrings |
| `docs/AGENT.md` | Compact API reference for agent/LLM consumption |
| `docs/quick_reference.md` | One-page signature summary |
| `docs/alternatives.md` | Comparison with `azure-devops` and raw `requests` |
| `docs/contributing.md` | This contributor guide, rendered on the docs site |

[Usage Guide]: docs/usage.md

[Sphinx]: https://www.sphinx-doc.org/
[MyST Parser]: https://myst-parser.readthedocs.io/

---

## Submitting a pull request

1. Fork the repo and create a branch from `main`.
2. Open an issue first if the change is non-trivial — discuss the approach.
3. Make your changes, add tests, update `docs/usage.md` if adding user-facing
   functionality.
4. Ensure the full check suite passes locally: `uv run prek run -a`.
5. Open a pull request. The PR description should explain *why*, not just what.

**Acceptance criteria:**

- Test suite passes; coverage stays at 100%.
- All linting and type-checking checks pass.
- New public functions have Google-style docstrings.
- `docs/usage.md` is updated for any new user-facing functionality.

<!-- github-only -->

[code of conduct]: CODE_OF_CONDUCT.md
