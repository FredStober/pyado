"""Smoke tests for profile and vssps endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado import raw
from pyado.raw.smoke_test._runner import _skip, console, run, run_or_skip


def _test_profile(
    access_token: str,
    org_url: str,
) -> tuple[raw.UserProfile | None, raw.ApiCall | None]:
    """Test profile and vssps-related APIs.  Returns (profile, vssps_api_call)."""
    console.print("\n=== PROFILE & VSSPS ===")

    profile_api_call = run(
        "get_profile_api_call",
        lambda: raw.get_profile_api_call(access_token),
    )
    profile = run_or_skip(
        "get_my_profile",
        lambda api=profile_api_call: (
            raw.get_my_profile(api)
            if api
            else (_ for _ in ()).throw(RuntimeError("no profile api call"))
        ),
    )

    # org name is the last path component of org_url (e.g. "myorg")
    org_name = org_url.rstrip("/").rsplit("/", 1)[-1]
    vssps_api_call = run(
        "get_vssps_api_call",
        lambda: raw.get_vssps_api_call(access_token, org_name),
    )

    if vssps_api_call:
        groups = run(
            "iter_graph_groups",
            lambda api=vssps_api_call: raw.list_graph_groups(api),
        )
        if groups:
            descriptors = [g.descriptor for g in groups if g.descriptor][:3]
            if descriptors:
                run_or_skip(
                    "get_identities",
                    lambda api=vssps_api_call, ds=descriptors: raw.get_identities(
                        api, ds
                    ),
                    "ADO returned unexpected identity response",
                )
            else:
                _skip("get_identities", "no descriptors in graph groups")
        else:
            _skip("get_identities", "no graph groups found")
    else:
        _skip("iter_graph_groups", "get_vssps_api_call failed")
        _skip("get_identities", "get_vssps_api_call failed")

    return profile, vssps_api_call
