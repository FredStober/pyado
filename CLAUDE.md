# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```console
# Install deps
uv sync

# Run tests (coverage enforced at 100%)
uv run pytest

# Run a single test
uv run pytest tests/raw/test_work_item.py::TestGetWorkItem::test_returns_work_item

# Lint + format check
uv run ruff check src/
uv run ruff format --check src/

# Type checking (both mypy and ty must pass)
uv run mypy src/
uv run ty check src/

# Run all pre-commit hooks in one shot
uv run prek run -a

# Build docs
uv sync --group docs
uv run --group docs sphinx-build docs docs/_build/html

# Regenerate detect-secrets baseline (after adding test tokens or similar)
uv run detect-secrets scan > .secrets.baseline
```

## Architecture

pyado wraps the Azure DevOps REST API with two complementary layers, both re-exported from `pyado` so callers only need `import pyado`:

### `raw/` — one function per ADO endpoint

- Each function accepts an `ApiCall` (credential + URL) as its first argument and returns a Pydantic model — never a raw dict.
- Functions accept **fully-built Pydantic request models** and return Pydantic response models. No dict construction, no dict returns.
- `raw/_core.py` defines `ApiCall`, shared primitives, and the HTTP machinery (session caching, retry, error extraction, content-type negotiation).
- All public symbols are re-exported through `raw/__init__.py` and `pyado/__init__.py`.

### `oop/` — resource objects (preview layer)

- **Not** re-exported from `pyado` — import via `from pyado.oop import Client` or `pyado.AzureDevOpsService`.
- Public classes: `AzureDevOpsService`, `Organization`, `Project`, `Repository`, `PullRequest`, `WorkItem`, `Build`, `Pipeline`, `VariableGroup`, `Team`, `Iteration`, `Area`, `Commit`.
- Hierarchy: `AzureDevOpsService → Organization → Project → Repository / WorkItem / Build / Pipeline / VariableGroup / Team`. Pull requests live under `Repository`.
- Private helpers (`oop/_build.py`, `oop/_git.py`, `oop/_pull_request.py`, `oop/_variable_group.py`, `oop/_work_item.py`) take primitive arguments, construct Pydantic request models, and call `raw/` functions to interact with the API. All API interaction flows through `raw/`.
- Object properties (`.id`, `.name`, `.info`, `.status`, etc.) are cached on first access; call `.refresh()` to invalidate the cache.

### Adding new functionality

1. Add the HTTP wrapper + Pydantic models to the relevant `raw/<domain>.py`.
2. Export new public symbols from `raw/__init__.py` and `pyado/__init__.py`.
3. If the endpoint needs payload construction, pagination, or multi-step logic, add a helper in the matching `oop/_<domain>.py` and a method on the relevant OOP class.
4. Tests must keep coverage at 100% — run `uv run pytest` to verify.
5. Update `docs/usage.md` for any user-facing additions.

## Style

- **Double quotes** for strings (not single).
- Google-style docstrings on all public modules, classes, and functions.
- `snake_case` variables/functions, `PascalCase` classes, `UPPER_SNAKE_CASE` constants.
- mypy runs in **strict mode** with `warn_unreachable = true`. No `# type: ignore`.
- ruff uses `select = ["ALL"]` — do not add new ignores without good reason.
- 100% branch coverage is enforced; every new code path needs a test.

## Key design constraints

- `ApiCall` is immutable; construct once and reuse — the underlying `requests.Session` is LRU-cached on the access token, so recreating `ApiCall` on every call defeats connection pooling.
- Multi-field request models are public (no `_` prefix); single-field internal wrappers may be private.
- `oop/_pull_request._full_ref` normalises short branch names (`"main"`) to full refs (`"refs/heads/main"`) — ADO ref mutation APIs require the full form.
- Work item mutations use JSON Patch (RFC 6902) — ADO constraint, not a pyado choice.
