# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```console
# Install deps
uv sync

# Lint + format check
uv run ruff check src/
uv run ruff format --check src/

# Type checking (both mypy and ty must pass)
uv run mypy src/
uv run ty check src/

# Run a single unit test
uv run pytest tests/raw/test_work_item.py -k test_get_work_item

# Run all unit tests (coverage enforced at 100%)
uv run pytest tests/

# Run integration tests (requires test.json — see below)
uv run pytest tests/integration/

# Run all pre-commit hooks in one shot
uv run prek run -a

# Build docs
uv sync --group docs
uv run --group docs sphinx-build docs docs/_build/html
```

## Architecture

pyado wraps the Azure DevOps REST API with two complementary layers, both re-exported from `pyado` so callers only need `import pyado`:

### `raw/` — one function per ADO endpoint

- Each function accepts an `ApiCall` (credential + URL) as its first argument and returns a Pydantic model — never a raw dict.
- Functions accept **fully-built Pydantic request models** and return Pydantic response models. No dict construction, no dict returns.
- `raw/_core.py` defines `ApiCall`, shared primitives, and the HTTP machinery (session caching, retry, error extraction, content-type negotiation).
- All public symbols (not the functions) are re-exported through `raw/__init__.py` and `pyado/__init__.py`.

### `oop/` — resource objects (preview layer)

- **Not** re-exported from `pyado` — import via `from pyado.oop import AzureDevOpsService` or `pyado.AzureDevOpsService`.
- Public classes: `AzureDevOpsService`, `Organization`, `Project`, `Repository`, `PullRequest`, `WorkItem`, `Build`, `Pipeline`, `VariableGroup`, `Team`, `Iteration`, `Area`, `Commit`.
- Hierarchy: `AzureDevOpsService → Organization → Project → Repository / WorkItem / Build / Pipeline / VariableGroup / Team`. Pull requests live under `Repository`.
- Private helpers (`oop/_build.py`, `oop/_git.py`, `oop/_pull_request.py`, `oop/_variable_group.py`, `oop/_work_item.py`) take primitive arguments, construct Pydantic request models, and call `raw/` functions to interact with the API. All API interaction flows through `raw/`.
- Object properties (`.id`, `.name`, `.info`, `.status`, etc.) are cached on first access; call `.refresh()` to invalidate the cache.

### Test layout

```
tests/
  raw/          Unit tests for the raw layer (no network; 100% coverage required).
  oop/          Unit tests for the OOP layer (no network; 100% coverage required).
  integration/
    raw/        Live-API tests for raw functions (need test.json).
    oop/        Live-API tests for OOP classes (need test.json).
```

Integration tests require a `test.json` file in the repo root with ADO credentials:

```json
{"org": "https://dev.azure.com/myorg", "project": "MyProject", "token": "<PAT>"}
```

Without `test.json` the integration tests are automatically skipped.

Each `tests/integration/raw/` module covers one domain (e.g. `test_pull_request_read.py`,
`test_wiki.py`).  The `tests/integration/raw/_support.py` module provides shared
fixtures and helpers (`_take`, `console`).

The `tests/integration/oop/_support.py` module provides `check_oop_coverage`, which
verifies that every public OOP class is referenced in at least one integration test file.

### Adding new functionality

1. Add the HTTP wrapper + Pydantic models to the relevant `raw/<domain>.py`.
2. Export new public symbols from `raw/__init__.py` and `pyado/__init__.py`.
3. If the endpoint needs payload construction, pagination, or multi-step logic, add a helper in the matching `oop/_<domain>.py` and a method on the relevant OOP class.
4. Unit tests in `tests/raw/` or `tests/oop/` must keep coverage at 100% — run `uv run pytest tests/` to verify.
5. Update `docs/usage.md` for any user-facing additions.

## Style

- **Imports are never allowed inside functions** — all imports must be at the top of the module.
- **Double quotes** for strings (not single).
- Google-style docstrings on all public modules, classes, and functions.
- `snake_case` variables/functions, `PascalCase` classes, `UPPER_SNAKE_CASE` constants.
- mypy runs in **strict mode** with `warn_unreachable = true`. No `# type: ignore`.
- ruff uses `select = ["ALL"]` — do not add new ignores without a very good reason.
- 100% branch coverage is enforced; every new code path needs a test.

## Re-exports in `__init__.py`

Public symbols in `pyado/__init__.py`, `pyado/raw/__init__.py`, and `pyado/oop/__init__.py` are re-exported via `__all__`.  Use plain `from x import Y` — **never** `from x import Y as Y`.  mypy's `--no-implicit-reexport` (enabled by strict mode) treats any name listed in `__all__` as a public re-export, so the `as Y` alias is redundant.

## Key design constraints

- `ApiCall` is immutable; construct once and reuse — the underlying `requests.Session` is LRU-cached on the access token, so recreating `ApiCall` on every call defeats connection pooling.
- Multi-field request models are public (no `_` prefix); single-field internal wrappers may be private.
- `oop/_pull_request._full_ref` normalises short branch names (`"main"`) to full refs (`"refs/heads/main"`) — ADO ref mutation APIs require the full form.
- Work item mutations use JSON Patch (RFC 6902) — ADO constraint, not a pyado choice.
