"""Integration tests for security namespace ACL endpoints and token builders."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import uuid

import pytest

from pyado import raw
from pyado.exceptions import AzureDevOpsAuthError
from tests.integration.raw._support import console


def test_namespace_acl_read(
    org_api_call: raw.ApiCall,
    project_name: str,
) -> None:
    """Read ACLs for project-level tokens built with the typed builders."""
    console.print("\n=== SECURITY (read) ===")
    org_root = raw.ApiCall(
        session=org_api_call.session,
        url=org_api_call.url.unicode_string().rstrip("/").removesuffix("/_apis"),
    )
    project_id = str(raw.get_project(org_api_call, project_name).id)
    try:
        names = raw.get_namespace_names(org_root)
    except AzureDevOpsAuthError:
        pytest.skip(reason="PAT lacks security scope")

    tokens = {
        "git repositories": raw.make_git_repo_token(project_id),
        "build": raw.make_build_token(project_id),
        "environment": raw.make_environment_token(project_id),
    }
    for namespace, token in tokens.items():
        namespace_id = names[namespace]
        actions = raw.get_namespace_actions(org_root, namespace_id)
        aces = raw.get_namespace_acl(org_root, namespace_id, token)
        console.print(f"  {namespace}: {len(actions)} actions, {len(aces)} ACEs")
        descriptors = [ace.descriptor for ace in aces]
        if descriptors:
            raw.get_identities_by_descriptor(org_root, descriptors)

    node_token = raw.make_classification_node_token("a", "b")
    assert raw.parse_classification_node_token(node_token) == ["a", "b"]


def test_namespace_acl_write_roundtrip(
    token: str,
    org_api_call: raw.ApiCall,
    project_api_call: raw.ApiCall,
    org_url: str,
    project_name: str,
) -> None:
    """Write and delete an ACL on a temporary variable group."""
    console.print("\n=== SECURITY (write) ===")
    org_root = raw.ApiCall(
        session=org_api_call.session,
        url=org_api_call.url.unicode_string().rstrip("/").removesuffix("/_apis"),
    )
    project = raw.get_project(org_api_call, project_name)
    try:
        names = raw.get_namespace_names(org_root)
        vssps_call = raw.get_vssps_api_call(
            raw.get_session(pat=token), org_url.rstrip("/").rsplit("/", 1)[-1]
        )
        users = raw.list_graph_users(vssps_call)
    except AzureDevOpsAuthError:
        pytest.skip(reason="PAT lacks security or graph scope")
    storage_keys = (
        raw.get_identities_by_subject_descriptor(org_root, [users[0].descriptor])
        if users
        else {}
    )
    if not storage_keys:
        pytest.skip(reason="no resolvable identity to build an ACE for")

    namespace_id = names["library"]
    group_name = f"_smoke_{uuid.uuid4().hex[:6]}"
    project_ref = raw.VariableGroupProjectReference.model_validate(
        {
            "projectReference": {"id": str(project.id), "name": project.name},
            "name": group_name,
            "description": "",
        }
    )
    group = raw.post_variable_group(
        project_api_call,
        raw.VariableGroupCreateRequest(
            name=group_name,
            variables={"_test": raw.VariableInfo(value="smoke")},
            variable_group_project_references=[project_ref],
        ),
    )
    try:
        acl_token = f"Library/{project.id}/VariableGroup/{group.id}"
        ace = raw.AceEntry(
            descriptor=next(iter(storage_keys.values())), allow=1, deny=0
        )
        raw.post_namespace_acl(org_root, namespace_id, acl_token, [ace])
        raw.get_namespace_acl(org_root, namespace_id, acl_token)
        raw.delete_namespace_acl(org_root, namespace_id, acl_token)
    finally:
        raw.delete_variable_group(org_api_call, group.id, [str(project.id)])
