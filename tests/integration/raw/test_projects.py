"""Integration tests for project and connection-data endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado import raw


def test_projects(org_api_call: raw.ApiCall) -> None:
    """List all projects in the organisation."""
    projects = list(raw.iter_projects(org_api_call))
    assert projects == raw.list_projects(org_api_call)


def test_connection_data(org_api_call: raw.ApiCall) -> None:
    """Fetch connection data for the organisation."""
    # get_connection_data internally appends "/_apis", so the URL passed here
    # must be the bare org URL without a trailing "/_apis" path component.
    org_base = org_api_call.url.unicode_string().rstrip("/").removesuffix("/_apis")
    base_api_call = raw.ApiCall(session=org_api_call.session, url=org_base)
    raw.get_connection_data(base_api_call)


def test_project_read(
    org_api_call: raw.ApiCall,
    project_name: str,
) -> None:
    """Fetch a single project by name."""
    raw.get_project(org_api_call, project_name)
