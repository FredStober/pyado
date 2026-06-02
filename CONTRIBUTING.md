# Contributor Guide

Thank you for your interest in improving this project.
This project is open-source under the [MIT license] and
welcomes contributions in the form of bug reports, feature requests, and pull requests.

Here is a list of important resources for contributors:

- [Source Code]
- [Documentation]
- [Issue Tracker]
- [Code of Conduct]

[mit license]: https://opensource.org/licenses/MIT
[source code]: https://github.com/fredstober/pyado
[documentation]: https://pyado.readthedocs.io/
[issue tracker]: https://github.com/fredstober/pyado/issues

## How to report a bug

Report bugs on the [Issue Tracker].

When filing an issue, make sure to answer these questions:

- Which operating system and Python version are you using?
- Which version of this project are you using?
- What did you do?
- What did you expect to see?
- What did you see instead?

The best way to get your bug fixed is to provide a test case,
and/or steps to reproduce the issue.

## How to request a feature

Request features on the [Issue Tracker].

## How to set up your development environment

You need Python 3.11 and [uv].

Install the package with development requirements:

```console
$ uv sync
```

You can now run an interactive Python session:

```console
$ uv run python
```

[uv]: https://docs.astral.sh/uv/

## How to test the project

Run the full test suite:

```console
$ uv run pytest
```

Unit tests live in the `tests/` directory and are written using [pytest].

[pytest]: https://pytest.readthedocs.io/

## Linting and type checking

```console
$ uv run ruff check src/
$ uv run ruff format --check src/
$ uv run mypy src/
```

## Package architecture

The library is split into two subpackages:

| Subpackage | Purpose |
|---|---|
| `pyado.raw` | Thin wrappers around individual ADO REST endpoints. One function per endpoint; accepts a Pydantic request model; returns a Pydantic response model. |
| `pyado.high` | Higher-level helpers that construct request models from primitive args, own pagination loops, and orchestrate multi-step operations. Delegates all HTTP to `pyado.raw`. |

See the module docstrings in `src/pyado/raw/api.py` and `src/pyado/high/api.py` for
the full set of rules governing each layer.

## How to submit changes

Open a [pull request] to submit changes to this project.

Your pull request needs to meet the following guidelines for acceptance:

- The test suite must pass without errors.
- Include unit tests for new functionality.
- If your changes add functionality, update the documentation accordingly.

It is recommended to open an issue before starting work on anything.
This will allow a chance to talk it over with the owners and validate your approach.

[pull request]: https://github.com/fredstober/pyado/pulls

<!-- github-only -->

[code of conduct]: CODE_OF_CONDUCT.md
