"""Integration tests for service hooks subscription and publisher endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import uuid

from pyado import raw
from tests.integration.raw._support import console


def test_hook_subscriptions_read(org_api_call: raw.ApiCall) -> None:
    """List service-hooks subscriptions and verify iter/list consistency."""
    console.print("\n=== SERVICE HOOKS (read) ===")
    subs = list(raw.iter_hook_subscriptions(org_api_call))
    assert subs == raw.list_hook_subscriptions(org_api_call)
    console.print(f"  subscriptions: {len(subs)}")


def test_hook_subscription_get_by_id(org_api_call: raw.ApiCall) -> None:
    """Get a single subscription by ID when at least one exists."""
    subs = raw.list_hook_subscriptions(org_api_call)
    if not subs:
        console.print("  skipping get_hook_subscription — no subscriptions found")
        return
    first = subs[0]
    console.print(f"\n=== SERVICE HOOKS get {first.id} ===")
    fetched = raw.get_hook_subscription(org_api_call, first.id)
    assert fetched.id == first.id


def test_hook_publishers_read(org_api_call: raw.ApiCall) -> None:
    """List service-hooks publishers and verify iter/list consistency."""
    console.print("\n=== SERVICE HOOKS PUBLISHERS (read) ===")
    publishers = list(raw.iter_hook_publishers(org_api_call))
    assert publishers == raw.list_hook_publishers(org_api_call)
    console.print(f"  publishers: {len(publishers)}")


def test_hook_subscription_write(
    org_api_call: raw.ApiCall,
    projects: list[raw.ProjectInfo],
    project_name: str,
) -> None:
    """Create a webhook subscription, update it, then delete it."""
    current_project = next((p for p in projects if p.name == project_name), None)
    if current_project is None:
        console.print("  skipping hook subscription write — project info not available")
        return

    console.print("\n=== SERVICE HOOKS (create/update/delete) ===")
    smoke_url = f"https://smoke-test-hook.invalid/{uuid.uuid4().hex[:8]}"

    new_sub = raw.post_hook_subscription(
        org_api_call,
        raw.HookSubscriptionCreateRequest(
            publisher_id="tfs",
            event_type="build.complete",
            resource_version="1.0",
            consumer_id="webHooks",
            consumer_action_id="httpRequest",
            publisher_inputs={"projectId": str(current_project.id)},
            consumer_inputs={"url": smoke_url},
        ),
    )
    console.print(f"  created: {new_sub.id}  event={new_sub.event_type}")

    updated_url = f"{smoke_url}_upd"
    updated_sub = raw.put_hook_subscription(
        org_api_call,
        new_sub.id,
        raw.HookSubscriptionUpdateRequest(
            id=new_sub.id,
            publisher_id="tfs",
            event_type="build.complete",
            resource_version="1.0",
            consumer_id="webHooks",
            consumer_action_id="httpRequest",
            publisher_inputs={"projectId": str(current_project.id)},
            consumer_inputs={"url": updated_url},
        ),
    )
    console.print(f"  updated: {updated_sub.id}")

    raw.delete_hook_subscription(org_api_call, new_sub.id)
    console.print("  deleted")
