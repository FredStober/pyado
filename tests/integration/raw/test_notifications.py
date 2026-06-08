"""Integration tests for notification subscription endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado import raw
from tests.integration.raw._support import console


def test_notification_read(org_api_call: raw.ApiCall) -> None:
    """List notification subscriptions."""
    console.print("\n=== NOTIFICATION (read) ===")
    subs = list(raw.iter_notification_subscriptions(org_api_call))
    assert subs == raw.list_notification_subscriptions(org_api_call)
