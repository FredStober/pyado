"""Integration tests for Organization OOP class."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import contextlib

from pyado.oop import Organization
from tests.integration.raw._support import _take, console


def test_organization(org: Organization) -> None:
    """Exercise Organization methods.

    Covers projects, graph groups, notifications, identities.
    """
    console.print("\n=== Organization ===")
    _ = org.api_call
    org.get_connection_data()
    with contextlib.suppress(Exception):
        org.get_my_profile()

    _take(org.iter_projects(), 5)
    org.list_projects()
    groups = _take(org.iter_graph_groups(), 3)
    org.list_graph_groups()
    _take(org.iter_notification_subscriptions(), 5)
    org.list_notification_subscriptions()
    if groups:
        descriptors = [g.descriptor for g in groups if g.descriptor][:3]
        if descriptors:
            org.get_identities(descriptors)
