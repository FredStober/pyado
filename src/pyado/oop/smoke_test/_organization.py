"""Smoke tests for Organization."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado.oop import Organization, Project
from pyado.oop.smoke_test._runner import _ok, _skip, _take, console, run


def _test_organization(org: Organization) -> list[Project]:
    console.print("\n=== Organization ===")
    run("org.api_call (property)", lambda: org.api_call)
    run(
        "org.get_connection_data()",
        org.get_connection_data,
    )
    try:
        org.get_my_profile()
        _ok("org.get_my_profile()")
    except Exception as ex:
        _skip("org.get_my_profile()", str(ex))

    projects = run("org.iter_projects()", lambda: _take(org.iter_projects(), 5))
    run("org.list_projects()", org.list_projects)
    groups = run(
        "org.iter_graph_groups()",
        lambda: _take(org.iter_graph_groups(), 3),
    )
    run("org.list_graph_groups()", org.list_graph_groups)
    if groups:
        descriptors = [g.descriptor for g in groups if g.descriptor][:3]
        if descriptors:
            run(
                "org.get_identities(descriptors)",
                lambda ds=descriptors: org.get_identities(ds),
            )
        else:
            _skip("org.get_identities(descriptors)", "no descriptors in graph groups")
    else:
        _skip("org.get_identities(descriptors)", "no graph groups found")
    return projects or []
