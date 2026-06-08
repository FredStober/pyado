"""Azure DevOps notification subscription API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import Any

from pydantic import Field

from pyado.raw._core import AdoBaseModel, ApiCall

__all__ = [
    "NotificationSubscription",
    "iter_notification_subscriptions",
    "list_notification_subscriptions",
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
