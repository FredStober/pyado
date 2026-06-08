"""Shared test infrastructure for raw integration tests."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import json
import pathlib
from collections.abc import Iterable
from typing import Any

from rich.console import Console

from pyado import raw
from pyado.exceptions import AzureDevOpsAuthError

console = Console()

# ---------------------------------------------------------------------------
# Onpremise pipeline constants
# ---------------------------------------------------------------------------
_ONPREMISE_PIPELINE_NAME = "onpremise"
_PRINT_STEP_NAME = "Print and encode system variables"

_ONPREMISE_WRITE_LABELS = (
    "post_job_feed [raw]",
    "post_job_logs",
    "post_job_event [raw]",
    "patch_timeline_records [onpremise, raw]",
)

_ONPREMISE_LABELS = (
    "patch_approvals [ManualValidation stage]",
    "get_plan_api_call",
    "get_job_api_call",
    "get_log_api_call",
    "get_timeline_api_call",
    *_ONPREMISE_WRITE_LABELS,
)


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def _load_config() -> tuple[str, str, str]:
    """Return (org_url, project_name, access_token) from test.json.

    * ``org`` key — ADO organisation name
    * ``project`` key sets the project name

    Returns:
        Tuple of (org_url, project_name, access_token) where org_url is the
        base organisation URL without a trailing slash or ``/_apis`` suffix.
    """
    cfg_path = pathlib.Path("test.json")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    token: str = cfg["access_token"]
    org = cfg["org"]
    project_name = cfg["project"]
    return f"https://dev.azure.com/{org}", project_name, token


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


# ---------------------------------------------------------------------------
# Profile & VSSPS smoke tests
# ---------------------------------------------------------------------------


def _test_profile(
    access_token: str,
    org_url: str,
) -> tuple[raw.UserProfile | None, raw.ApiCall | None]:
    """Test profile and vssps-related APIs.  Returns (profile, vssps_api_call)."""
    console.print("\n=== PROFILE & VSSPS ===")

    session = raw.get_session(pat=access_token)

    profile_api_call = raw.get_profile_api_call(session)
    if not profile_api_call:
        console.print("  WARNING: no profile API call available; skipping profile test")
        return None, None

    try:
        profile: raw.UserProfile | None = raw.get_my_profile(profile_api_call)
    except AzureDevOpsAuthError:
        console.print("  WARNING: PAT lacks vso.profile scope; skipping profile test")
        return None, None

    org_name = org_url.rstrip("/").rsplit("/", 1)[-1]
    vssps_api_call = raw.get_vssps_api_call(session, org_name)

    if vssps_api_call:
        groups = list(raw.iter_graph_groups(vssps_api_call))
        assert groups == raw.list_graph_groups(vssps_api_call)
        if groups:
            descriptors = [g.descriptor for g in groups if g.descriptor][:3]
            if descriptors:
                raw.get_identities(vssps_api_call, descriptors)

    return profile, vssps_api_call
