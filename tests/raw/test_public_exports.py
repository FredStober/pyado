"""Tests that the documented raw API symbols are exported from pyado.raw."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import pytest

import pyado
import pyado.raw

_NAMES = [
    "AzureDevOpsError",
    "AzureDevOpsNotFoundError",
    "AceEntry",
    "make_build_token",
    "make_classification_node_token",
    "make_environment_token",
    "make_git_repo_token",
    "parse_classification_node_token",
    "delete_namespace_acl",
    "get_identities_by_descriptor",
    "get_identities_by_subject_descriptor",
    "get_namespace_acl",
    "get_namespace_actions",
    "get_namespace_names",
    "post_namespace_acl",
    "list_graph_memberships",
    "iter_graph_memberships",
    "list_personal_access_tokens",
    "get_boards",
    "get_board_columns",
    "put_board_columns",
    "get_board_rows",
    "put_board_rows",
    "get_card_settings",
    "put_card_settings",
    "get_team_settings",
    "patch_team_settings",
    "get_team_iterations",
    "patch_team_field_values",
    "get_notification_subscription",
    "post_notification_subscription",
    "patch_notification_subscription",
    "delete_notification_subscription",
]


@pytest.mark.parametrize("name", _NAMES)
def test_symbol_is_exported_from_raw(name: str) -> None:
    """Each symbol is listed in ``__all__`` and importable."""
    assert name in pyado.raw.__all__
    assert getattr(pyado.raw, name) is not None


def test_ace_entry_exported_from_pyado() -> None:
    """``AceEntry`` is re-exported from the top-level package."""
    assert pyado.AceEntry is pyado.raw.AceEntry
