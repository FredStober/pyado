"""Smoke tests for project and connection-data endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado import raw
from pyado.raw.smoke_test._runner import _DIM, _RESET, console, run


def _test_projects(org_api_call: raw.ApiCall) -> list[raw.ProjectInfo]:
    console.print("\n=== PROJECTS ===")
    projects = run(
        "iter_projects",
        lambda: raw.list_projects(org_api_call),
    )
    if projects:
        console.print(f"  {_DIM}found {len(projects)} project(s){_RESET}")
    return projects or []


def _test_connection_data(org_api_call: raw.ApiCall) -> None:
    console.print("\n=== CONNECTION DATA ===")
    # get_connection_data internally appends "/_apis", so the URL passed here
    # must be the bare org URL without a trailing "/_apis" path component.
    org_base = org_api_call.url.unicode_string().rstrip("/").removesuffix("/_apis")
    base_api_call = raw.ApiCall(access_token=org_api_call.access_token, url=org_base)
    run("get_connection_data", lambda: raw.get_connection_data(base_api_call))


def _test_project_read(
    org_api_call: raw.ApiCall,
    project_name: str,
) -> None:
    console.print("\n=== PROJECT (get_project) ===")
    run(
        "get_project",
        lambda: raw.get_project(org_api_call, project_name),
    )
