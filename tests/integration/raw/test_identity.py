"""Integration tests for graph user and user entitlement endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import pytest

from pyado import raw
from pyado.exceptions import (
    AzureDevOpsAuthError,
    AzureDevOpsError,
    AzureDevOpsNotFoundError,
)
from tests.integration.raw._support import console


def test_graph_users_read(
    token: str,
    org_url: str,
) -> None:
    """List graph users and fetch a single user by descriptor."""
    console.print("\n=== GRAPH USERS (read) ===")
    session = raw.get_session(pat=token)
    org_name = org_url.rstrip("/").rsplit("/", 1)[-1]
    try:
        vssps_call = raw.get_vssps_api_call(session, org_name)
    except AzureDevOpsAuthError:
        pytest.skip(reason="PAT lacks graph scope")

    try:
        users = raw.list_graph_users(vssps_call)
        assert users == list(raw.iter_graph_users(vssps_call))
    except AzureDevOpsAuthError:
        pytest.skip(reason="PAT lacks vso.graph scope")

    console.print(f"  found {len(users)} graph user(s)")

    if users:
        first = users[0]
        console.print(f"  fetching user {first.descriptor!r}")
        try:
            fetched = raw.get_graph_user(vssps_call, first.descriptor)
            assert fetched.descriptor == first.descriptor
        except AzureDevOpsNotFoundError:
            console.print("  get_graph_user returned 404 — skipping single-user check")


def test_user_entitlements_read(
    token: str,
    org_url: str,
) -> None:
    """List user entitlements."""
    console.print("\n=== USER ENTITLEMENTS (read) ===")
    session = raw.get_session(pat=token)
    org_name = org_url.rstrip("/").rsplit("/", 1)[-1]
    vssps_call = raw.get_vssps_api_call(session, org_name)

    try:
        entitlements = raw.list_user_entitlements(vssps_call)
        assert entitlements == list(raw.iter_user_entitlements(vssps_call))
    except AzureDevOpsAuthError:
        pytest.skip(reason="PAT lacks vso.memberentitlementmanagement scope")
    except AzureDevOpsNotFoundError:
        pytest.skip(
            reason="memberentitlementmanagement endpoint not available in this org"
        )

    console.print(f"  found {len(entitlements)} entitlement(s)")


def test_graph_membership_and_entitlement_write(
    token: str,
    org_url: str,
) -> None:
    """Smoke-test write paths: update access level, membership add/remove.

    Uses read-only assertions where possible; skips each write operation
    when the PAT lacks the required scope.
    """
    console.print("\n=== GRAPH MEMBERSHIP / ENTITLEMENT (write) ===")
    session = raw.get_session(pat=token)
    org_name = org_url.rstrip("/").rsplit("/", 1)[-1]
    vssps_call = raw.get_vssps_api_call(session, org_name)

    # --- update_user_access_level ---
    try:
        entitlements = raw.list_user_entitlements(vssps_call)
    except AzureDevOpsAuthError:
        pytest.skip(reason="PAT lacks vso.memberentitlementmanagement scope")
    except AzureDevOpsNotFoundError:
        pytest.skip(
            reason="memberentitlementmanagement endpoint not available in this org"
        )

    if entitlements:
        first = entitlements[0]
        existing_level = first.access_level or raw.AccessLevel()
        console.print(
            f"  updating access level for user {first.id}"
            f"  (current: {existing_level.account_license_type})"
        )
        try:
            updated = raw.update_user_access_level(vssps_call, first.id, existing_level)
            new_license = (
                updated.access_level.account_license_type
                if updated.access_level
                else None
            )
            console.print(f"  updated access level: {new_license}")
        except AzureDevOpsAuthError:
            console.print("  skipping update_user_access_level — insufficient scope")
    else:
        console.print("  skipping update_user_access_level — no entitlements found")

    # --- add_graph_membership / remove_graph_membership ---
    try:
        users = raw.list_graph_users(vssps_call)
        groups = raw.list_graph_groups(vssps_call)
    except AzureDevOpsAuthError:
        console.print("  skipping membership write — insufficient scope")
        return

    if not users or not groups:
        console.print("  skipping membership write — no users or groups available")
        return

    subject = users[0]
    container = groups[0]
    console.print(f"  add {subject.descriptor!r} to {container.descriptor!r}")
    try:
        membership = raw.add_graph_membership(
            vssps_call, subject.descriptor, container.descriptor
        )
        console.print(
            f"  added: member={membership.member_descriptor!r}"
            f"  container={membership.container_descriptor!r}"
        )
        raw.remove_graph_membership(
            vssps_call, subject.descriptor, container.descriptor
        )
        console.print("  removed membership")
    except (AzureDevOpsAuthError, AzureDevOpsNotFoundError) as exc:
        console.print(f"  skipping membership write — {exc}")

    # --- add_user_entitlement (attempt; skip gracefully on any API error) ---
    try:
        new_entitlement = raw.add_user_entitlement(
            vssps_call,
            raw.UserEntitlementCreateRequest(
                user=raw.GraphUser(
                    descriptor=subject.descriptor,
                    display_name=subject.display_name,
                    subject_kind=subject.subject_kind,
                ),
                access_level=raw.AccessLevel(account_license_type="express"),
            ),
        )
        console.print(f"  add_user_entitlement returned: {new_entitlement.id}")
    except AzureDevOpsError as exc:
        console.print(f"  skipping add_user_entitlement — {exc}")
