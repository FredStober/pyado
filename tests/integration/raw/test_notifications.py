"""Integration tests for notification subscription endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import pytest

from pyado import raw
from pyado.exceptions import AzureDevOpsError
from tests.integration.raw._support import console


def test_notification_read(org_api_call: raw.ApiCall) -> None:
    """List notification subscriptions."""
    console.print("\n=== NOTIFICATION (read) ===")
    subs = list(raw.iter_notification_subscriptions(org_api_call))
    assert subs == raw.list_notification_subscriptions(org_api_call)


def test_notification_subscription_lifecycle(
    org_api_call: raw.ApiCall,
    project_name: str,
) -> None:
    """Create, read, update, and delete a throwaway subscription."""
    console.print("\n=== NOTIFICATION (write) ===")
    project_id = str(raw.get_project(org_api_call, project_name).id)
    body = {
        "description": "pyado integration test (safe to delete)",
        "filter": {
            "type": "Expression",
            "eventType": "ms.vss-pipelines.run-state-changed-event",
        },
        "channel": {"type": "EmailHtml"},
        "scope": {"id": project_id, "type": "project"},
    }
    try:
        created = raw.post_notification_subscription(org_api_call, body)
    except AzureDevOpsError as exc:
        pytest.skip(reason=f"cannot create subscription: {exc}")
    try:
        fetched = raw.get_notification_subscription(org_api_call, created.id)
        assert fetched.id == created.id
        raw.patch_notification_subscription(
            org_api_call,
            created.id,
            {"description": "pyado integration test (patched)"},
        )
    finally:
        raw.delete_notification_subscription(org_api_call, created.id)
