"""Azure DevOps notification subscription API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import Any

from pydantic import Field

from pyado.raw._core import AdoBaseModel, ApiCall

__all__ = [
    "NotificationSubscription",
    "delete_notification_subscription",
    "get_notification_subscription",
    "iter_notification_subscriptions",
    "list_notification_subscriptions",
    "patch_notification_subscription",
    "post_notification_subscription",
]

_NOTIFICATION_API_VERSION = "7.1"


class NotificationSubscription(AdoBaseModel):
    """A single ADO notification subscription."""

    id: str
    description: str = ""
    filter: dict[str, Any] = Field(default_factory=dict)
    subscriber: dict[str, Any] = Field(default_factory=dict)
    channel: dict[str, Any] = Field(default_factory=dict)
    scope: dict[str, Any] = Field(default_factory=dict)
    status: str | None = None
    url: str | None = None
    flags: str | None = None
    permissions: str | None = None
    admin_settings: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    extended_properties: dict[str, Any] = Field(default_factory=dict)
    user_settings: dict[str, Any] = Field(default_factory=dict)


def iter_notification_subscriptions(
    org_api_call: ApiCall,
) -> Iterator[NotificationSubscription]:
    """Iterate over all notification subscriptions in the organisation.

    The endpoint is org-scoped; filter to a specific project client-side
    by inspecting ``subscription.scope``.

    Args:
        org_api_call: Organisation-level ADO API call.

    Yields:
        NotificationSubscription for each subscription.
    """
    result = org_api_call.get(
        "notification",
        "subscriptions",
        version=_NOTIFICATION_API_VERSION,
    )
    for item in result.get("value", []):
        yield NotificationSubscription.model_validate(item)


def list_notification_subscriptions(
    org_api_call: ApiCall,
) -> list[NotificationSubscription]:
    """Return all notification subscriptions in the organisation as a list."""
    return list(iter_notification_subscriptions(org_api_call))


def get_notification_subscription(
    org_api_call: ApiCall,
    subscription_id: str,
) -> NotificationSubscription:
    """Fetch a single notification subscription by ID.

    Args:
        org_api_call: Organisation-level ADO API call.
        subscription_id: Subscription identifier (GUID or numeric string).

    Returns:
        NotificationSubscription parsed from the API response.
    """
    result = org_api_call.get(
        "notification",
        "subscriptions",
        subscription_id,
        version=_NOTIFICATION_API_VERSION,
    )
    return NotificationSubscription.model_validate(result)


def post_notification_subscription(
    org_api_call: ApiCall,
    body: dict[str, Any],
) -> NotificationSubscription:
    """Create a new notification subscription.

    Args:
        org_api_call: Organisation-level ADO API call.
        body: Subscription creation payload (description, filter, channel,
            subscriber, scope, etc.).

    Returns:
        NotificationSubscription for the newly created subscription.
    """
    result = org_api_call.post(
        "notification",
        "subscriptions",
        json=body,
        version=_NOTIFICATION_API_VERSION,
    )
    return NotificationSubscription.model_validate(result)


def patch_notification_subscription(
    org_api_call: ApiCall,
    subscription_id: str,
    body: dict[str, Any],
) -> NotificationSubscription:
    """Update an existing notification subscription via PATCH.

    Args:
        org_api_call: Organisation-level ADO API call.
        subscription_id: Subscription identifier (GUID or numeric string).
        body: Partial subscription payload with fields to update.

    Returns:
        Updated NotificationSubscription parsed from the API response.
    """
    result = org_api_call.patch(
        "notification",
        "subscriptions",
        subscription_id,
        json=body,
        version=_NOTIFICATION_API_VERSION,
    )
    return NotificationSubscription.model_validate(result)


def delete_notification_subscription(
    org_api_call: ApiCall,
    subscription_id: str,
) -> None:
    """Delete a notification subscription.

    Args:
        org_api_call: Organisation-level ADO API call.
        subscription_id: Subscription identifier (GUID or numeric string).
    """
    org_api_call.delete(
        "notification",
        "subscriptions",
        subscription_id,
        version=_NOTIFICATION_API_VERSION,
    )
