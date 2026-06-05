"""Shared test infrastructure: state, runner helpers, config, coverage check."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import ast
import base64
import inspect
import json
import pathlib
from collections.abc import Callable, Iterable
from typing import Any

from rich.console import Console
from rich.markup import escape

from pyado import raw

console = Console()

# ---------------------------------------------------------------------------
# Terminal colours
# ---------------------------------------------------------------------------
_GREEN = "\033[92m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
_DIM = "\033[2m"
_RESET = "\033[0m"

# ---------------------------------------------------------------------------
# Shared mutable state
# ---------------------------------------------------------------------------
_results: list[tuple[str, str, str]] = []  # (label, status, detail)
_recordings: list[dict[str, Any]] = []
_token_unavailable_skips: set[str] = set()

# ---------------------------------------------------------------------------
# Onpremise pipeline constants (used here for skip policy and in _agent.py)
# ---------------------------------------------------------------------------
_ONPREMISE_PIPELINE_NAME = "onpremise"
_PRINT_STEP_NAME = "Print and encode system variables"

_ONPREMISE_WRITE_LABELS = (
    "post_job_feed [raw]",
    "post_job_logs",
    "post_job_event [raw]",
    "patch_timeline_records [onpremise, raw]",
)

_ONPREMISE_LABELS_BASE = (
    "patch_approvals [ManualValidation stage]",
    "get_plan_api_call",
    "get_job_api_call",
    "get_log_api_call",
    "get_timeline_api_call",
)

_ONPREMISE_LABELS = (*_ONPREMISE_LABELS_BASE, *_ONPREMISE_WRITE_LABELS)

# Reason string used when agent write APIs are attempted after job completion.
_ACTIVE_JOB_REQUIRED = "agent write requires an active job; step already completed"

# ---------------------------------------------------------------------------
# Allowed-skip policy
#
# ONLY the following tests are ever permitted to be skipped.  Any other SKIP
# recorded during a run is treated as a failure at summary time.
#
# Always allowed:
#   • "get_my_profile" — requires a different PAT (vso.profile scope) that is
#     separate from the project PAT used for every other test.
#
# Allowed only when --no-trigger or --no-onpremise is passed:
#   • "post_pipeline_run / iter_timeline_records (write)" } only with --no-trigger
#   • Every label in _ONPREMISE_LABELS                    } either flag
# ---------------------------------------------------------------------------

_ALWAYS_ALLOWED_SKIPS: frozenset[str] = frozenset(
    [
        "get_my_profile",
        # May fail if ADO returns null entries or method not supported yet.
        "get_identities",
        # Requires pre-existing builds triggered from commits with #<id>.
        "get_work_item [verify WI→commit back-link]",
        # Skipped when no teams exist or no iteration nodes with a UUID exist.
        "iter_sprint_iterations [team-level]",
        "add_team_iteration",
        "delete_team_iteration [remove then restore]",
        "add_team_iteration [restore after delete]",
        # Skipped when no build artifacts have a downloadUrl.
        "get_build_artifact_bytes",
        # Skipped when soft-delete of the smoke work item fails.
        "restore_work_item",
        "delete_work_item [permanent]",
        # Skipped when no pipelines exist to authorize, or if ADO rejects the method.
        "post_pipeline_permission [authorize VG]",
        # Skipped if variable group create failed or delete is rejected by ADO.
        "delete_variable_group",
    ]
)


def _allowed_skips(skip_pipeline_trigger: bool) -> frozenset[str]:
    """Return the set of test labels that are permitted to be skipped."""
    allowed = set(_ALWAYS_ALLOWED_SKIPS)
    allowed.update(_token_unavailable_skips)
    if skip_pipeline_trigger:
        allowed.update(_ONPREMISE_LABELS)
        allowed.add("post_pipeline_run / iter_timeline_records (write)")
        allowed.add("post_build [start build API]")
        allowed.add("patch_build [cancel, build API]")
        allowed.add("patch_build [raw, cancel]")
    return frozenset(allowed)


# ---------------------------------------------------------------------------
# Raw API coverage check
# ---------------------------------------------------------------------------

# Symbols intentionally excluded from coverage checking:
#   get_session        — low-level transport helper, not an ADO endpoint
#   ADOUrl             — type alias / constructor, not an endpoint function
#
# iter_* variants below are tested transitively: each has a list_* wrapper
# that is called directly in the smoke test, and every list_* wrapper
# delegates to its iter_* counterpart, so the endpoint is exercised.
_RAW_COVERAGE_SKIP: frozenset[str] = frozenset(
    [
        "get_session",
        "ADOUrl",
        "iter_build_artifacts",
        "iter_build_logs",
        "iter_builds",
        "iter_graph_groups",
        "iter_pipelines",
        "iter_projects",
        "iter_pull_request_statuses",
        "iter_repository_details",
        "iter_repository_items",
        "iter_tags",
        "iter_team_members",
        "iter_teams",
        "iter_variable_group_details",
        "iter_work_items_between_builds",
    ]
)


def check_raw_coverage(smoke_test_dir: pathlib.Path) -> None:
    """Warn about any public raw API functions not referenced in the smoke test.

    Scans all ``*.py`` files in *smoke_test_dir* for ``raw.<name>`` attribute
    accesses, then checks whether every public callable in ``pyado.raw`` is
    covered.  Prints a warning for each uncovered function — informational only.
    """
    # Collect every ``raw.<name>`` attribute access across all submodule files.
    raw_attrs_used: set[str] = set()
    for py_file in smoke_test_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "raw"
            ):
                raw_attrs_used.add(node.attr)

    # Enumerate all public callables in pyado.raw.
    uncovered: list[str] = []
    for name in dir(raw):
        if name.startswith("_") or name in _RAW_COVERAGE_SKIP:
            continue
        obj = getattr(raw, name)
        if not (inspect.isfunction(obj) or inspect.isbuiltin(obj)):
            continue
        if name not in raw_attrs_used:
            uncovered.append(name)

    _report_coverage_gaps(
        uncovered,
        "Raw API coverage",
        "functions not called via raw.<name> in this smoke test",
    )


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def _load_config() -> tuple[str, str, str]:
    """Return (org_url, project_name, access_token) from test.json.

    Accepts two formats:

    * ``url`` key — full project-level ``_apis`` URL
      (e.g. ``"https://dev.azure.com/myorg/myproject/_apis"``).
    * ``org`` key — ADO organisation name; optional ``project`` key sets the
      project name (defaults to the org name when absent).

    Returns:
        Tuple of (org_url, project_name, access_token) where org_url is the
        base organisation URL without a trailing slash or ``/_apis`` suffix.
    """
    cfg_path = pathlib.Path("test.json")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    token: str = cfg["access_token"]
    if "url" in cfg:
        parts = cfg["url"].rstrip("/").rsplit("/", 2)
        return parts[0], parts[1], token
    org = cfg["org"]
    project_name = cfg.get("project", org)
    return f"https://dev.azure.com/{org}", project_name, token


# ---------------------------------------------------------------------------
# Response recorder
# ---------------------------------------------------------------------------


def _install_recorder() -> None:
    """Monkey-patch ApiCall._request to capture every request/response."""
    original = raw.ApiCall._request

    def _wrapped(
        method: str,
        api_call: raw.ApiCall,
        json: Any = None,
        data: Any = None,
        **flags: Any,
    ) -> Any:
        entry: dict[str, Any] = {
            "method": method,
            "url": api_call.url.unicode_string(),
            "params": dict(api_call.parameters),
            "request_json": json,
            "request_data": (
                base64.b64encode(data).decode() if isinstance(data, bytes) else data
            ),
            "response": None,
            "error": None,
        }
        try:
            result = original(method, api_call, json, data, **flags)
        except Exception as ex:
            entry["error"] = str(ex)
            raise
        else:
            entry["response"] = (
                base64.b64encode(result).decode()
                if isinstance(result, bytes)
                else result
            )
            return result
        finally:
            _recordings.append(entry)

    raw.ApiCall._request = staticmethod(_wrapped)  # type: ignore[method-assign]


def _save_recordings(path: pathlib.Path) -> None:
    """Write all captured request/response pairs to *path* as JSON."""
    path.write_text(
        json.dumps(_recordings, indent=2, default=str),
        encoding="utf-8",
    )
    console.print(f"\n[dim]Recorded {len(_recordings)} API calls → {path}[/dim]")


# ---------------------------------------------------------------------------
# Test runners
# ---------------------------------------------------------------------------


def _ok(label: str) -> None:
    _results.append((label, "PASS", ""))
    console.print(f"  [green]PASS[/]  {escape(label)}")


def _fail(label: str, ex: BaseException) -> None:
    detail = f"{type(ex).__name__}: {ex}"
    _results.append((label, "FAIL", detail))
    console.print(f"  [red]FAIL[/]  {escape(label)}")
    console.print(f"        [dim]{escape(detail)}[/dim]")


def _skip(label: str, reason: str = "") -> None:
    _results.append((label, "SKIP", reason))
    suffix = f"  ({escape(reason)})" if reason else ""
    console.print(f"  [yellow]SKIP[/]  {escape(label)}{suffix}")


def run(label: str, fn: Callable[[], Any]) -> Any:
    """Call *fn()*, record pass/fail, return the result (or None on error)."""
    try:
        result = fn()
    except Exception as ex:
        _fail(label, ex)
        return None
    else:
        _ok(label)
        return result


def run_or_skip(label: str, fn: Callable[[], Any], skip_reason: str = "") -> Any:
    """Like run(), but records SKIP instead of FAIL on exception.

    Use for tests that require runtime conditions that cannot be guaranteed,
    such as an active agent job token.
    """
    try:
        result = fn()
    except Exception as ex:
        reason = f"{skip_reason}: {ex}" if skip_reason else str(ex)
        _skip(label, reason)
        return None
    else:
        _ok(label)
        return result


# ---------------------------------------------------------------------------
# Shared summary and coverage reporting
# ---------------------------------------------------------------------------


def _report_coverage_gaps(
    gaps: list[str],
    title: str,
    detail: str,
) -> None:
    """Print coverage report: list gaps or an all-clear message.

    Args:
        gaps: Uncovered symbol names (empty means full coverage).
        title: Short label, e.g. ``"Raw API coverage"``.
        detail: Parenthetical description shown in the gap header.
    """
    if gaps:
        console.print(f"\n[yellow]{escape(title)} gaps ({escape(detail)}):[/yellow]")
        for sym in sorted(gaps):
            console.print(f"  [dim]{escape(sym)}[/dim]")
    else:
        console.print(f"\n[dim]{escape(title)}: all public symbols referenced.[/dim]")


def _print_failures() -> None:
    """Print the FAIL entries from _results."""
    console.print("\n[red]Failures:[/red]")
    for label, status, detail in _results:
        if status == "FAIL":
            console.print(f"  [red]FAIL[/]  {escape(label)}")
            console.print(f"        [dim]{escape(detail)}[/dim]")


def _print_unexpected(unexpected: list[tuple[str, str]]) -> None:
    """Print unexpected-skip entries."""
    console.print(
        "\n[red]Unexpected skips "
        "(must not be skipped — fix the test or the config):[/red]"
    )
    for label, reason in unexpected:
        console.print(f"  {escape(label)}")
        console.print(f"    [dim]{escape(reason)}[/dim]")


def _print_skips() -> None:
    """Print the SKIP entries from _results."""
    console.print("\n[yellow]Skipped:[/yellow]")
    for label, status, reason in _results:
        if status == "SKIP":
            console.print(f"  [yellow]SKIP[/]  {escape(label)}")
            if reason:
                console.print(f"        [dim]{escape(reason)}[/dim]")


def _print_summary(
    *,
    unexpected: list[tuple[str, str]] | None = None,
    note: str | None = None,
) -> int:
    """Print the final pass/fail/skip summary and return the exit code.

    Args:
        unexpected: Skipped labels that are not in the allowed-skip list; each
            entry is ``(label, reason)``.  When non-empty these are shown as
            failures and the exit code is 1.
        note: Optional one-line footnote printed below the totals line (e.g.
            to explain that write tests were skipped).

    Returns:
        0 if all tests passed (and no unexpected skips), 1 otherwise.
    """
    passes = sum(1 for _, s, _ in _results if s == "PASS")
    fails = sum(1 for _, s, _ in _results if s == "FAIL")
    skips = sum(1 for _, s, _ in _results if s == "SKIP")
    total = len(_results)

    console.print("\n" + "=" * 60)
    console.print(
        f"  [green]{passes} passed[/]  "
        f"[red]{fails} failed[/]  "
        f"[yellow]{skips} skipped[/]  "
        f"({total} total)"
    )
    if note:
        console.print(f"[dim]{escape(note)}[/dim]")

    if fails:
        _print_failures()
    if unexpected:
        _print_unexpected(unexpected)
    if skips:
        _print_skips()
    console.print("=" * 60)
    return 1 if (fails or unexpected) else 0


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _take(iterable: Iterable[Any], count: int) -> list[Any]:
    """Consume up to *count* items from an iterator."""
    result = []
    for item in iterable:
        result.append(item)
        if len(result) >= count:
            break
    return result
