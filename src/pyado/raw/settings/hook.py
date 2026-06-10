"""Azure DevOps service hooks subscription and publisher API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import datetime
from enum import StrEnum
from typing import Any, TypeAlias
from uuid import UUID

from pydantic import Field

from pyado.raw._core import AdoBaseModel, ApiCall

__all__ = [
    "HookConsumerId",
    "HookPublisherId",
    "HookPublisherInfo",
    "HookSubscriptionCreateRequest",
    "HookSubscriptionId",
    "HookSubscriptionInfo",
    "HookSubscriptionStatus",
    "HookSubscriptionUpdateRequest",
    "delete_hook_subscription",
    "get_hook_subscription",
    "iter_hook_publishers",
    "iter_hook_subscriptions",
    "list_hook_publishers",
    "list_hook_subscriptions",
    "post_hook_subscription",
    "put_hook_subscription",
]

_HOOK_API_VERSION = "7.1"

#: UUID identifier for a service-hooks subscription.
HookSubscriptionId: TypeAlias = UUID
#: String identifier for a service-hooks publisher (e.g. ``"tfs"``).
HookPublisherId: TypeAlias = str
#: String identifier for a service-hooks consumer (e.g. ``"webHooks"``).
HookConsumerId: TypeAlias = str


class HookSubscriptionStatus(StrEnum):
    """Lifecycle status of a service-hooks subscription."""

    DISABLED_BY_INACTIVITY = "disabledByInactivity"
    DISABLED_BY_SYSTEM = "disabledBySystem"
    DISABLED_BY_USER = "disabledByUser"
    ENABLED = "enabled"
    ON_PROBATION = "onProbation"


class HookSubscriptionInfo(AdoBaseModel):
    """Minimal representation of an ADO service-hooks subscription."""

    id: HookSubscriptionId
    status: HookSubscriptionStatus | None = None
    publisher_id: HookPublisherId
    event_type: str
    consumer_id: HookConsumerId
    consumer_action_id: str
    resource_version: str | None = None
    action_description: str | None = None
    publisher_inputs: dict[str, Any] = Field(default_factory=dict)
    consumer_inputs: dict[str, Any] = Field(default_factory=dict)
    created_date: datetime | None = None
    modified_date: datetime | None = None


class HookPublisherInfo(AdoBaseModel):
    """Minimal representation of an ADO service-hooks publisher."""

    id: HookPublisherId
    name: str
    description: str | None = None


class HookSubscriptionCreateRequest(AdoBaseModel):
    """Request body for creating a service-hooks subscription."""

    publisher_id: HookPublisherId
    event_type: str
    resource_version: str
    consumer_id: HookConsumerId
    consumer_action_id: str
    publisher_inputs: dict[str, Any] = Field(default_factory=dict)
    consumer_inputs: dict[str, Any] = Field(default_factory=dict)


class HookSubscriptionUpdateRequest(AdoBaseModel):
    """Request body for updating a service-hooks subscription."""

    id: HookSubscriptionId
    publisher_id: HookPublisherId
    event_type: str
    resource_version: str
    consumer_id: HookConsumerId
    consumer_action_id: str
    publisher_inputs: dict[str, Any] = Field(default_factory=dict)
    consumer_inputs: dict[str, Any] = Field(default_factory=dict)


def iter_hook_subscriptions(
    org_api_call: ApiCall,
) -> Iterator[HookSubscriptionInfo]:
    """Iterate over all service-hooks subscriptions in the organisation.

    Args:
        org_api_call: Organisation-level ADO API call.

    Yields:
        HookSubscriptionInfo for each subscription.
    """
    result = org_api_call.get(
        "hooks",
        "subscriptions",
        version=_HOOK_API_VERSION,
    )
    for item in result.get("value", []):
        yield HookSubscriptionInfo.model_validate(item)


def list_hook_subscriptions(
    org_api_call: ApiCall,
) -> list[HookSubscriptionInfo]:
    """Return all service-hooks subscriptions in the organisation as a list."""
    return list(iter_hook_subscriptions(org_api_call))


def get_hook_subscription(
    org_api_call: ApiCall,
    subscription_id: HookSubscriptionId,
) -> HookSubscriptionInfo:
    """Fetch a single service-hooks subscription by ID.

    Args:
        org_api_call: Organisation-level ADO API call.
        subscription_id: UUID of the subscription.

    Returns:
        HookSubscriptionInfo for the requested subscription.
    """
    result = org_api_call.get(
        "hooks",
        "subscriptions",
        subscription_id,
        version=_HOOK_API_VERSION,
    )
    return HookSubscriptionInfo.model_validate(result)


def post_hook_subscription(
    org_api_call: ApiCall,
    request: HookSubscriptionCreateRequest,
) -> HookSubscriptionInfo:
    """Create a new service-hooks subscription.

    Args:
        org_api_call: Organisation-level ADO API call.
        request: Create request specifying the publisher, event type,
            consumer, and consumer action.

    Returns:
        HookSubscriptionInfo for the newly created subscription.
    """
    result = org_api_call.post(
        "hooks",
        "subscriptions",
        version=_HOOK_API_VERSION,
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return HookSubscriptionInfo.model_validate(result)


def put_hook_subscription(
    org_api_call: ApiCall,
    subscription_id: HookSubscriptionId,
    request: HookSubscriptionUpdateRequest,
) -> HookSubscriptionInfo:
    """Update an existing service-hooks subscription.

    Args:
        org_api_call: Organisation-level ADO API call.
        subscription_id: UUID of the subscription to update.
        request: Update request.  The ``id`` field must match
            ``subscription_id``.

    Returns:
        Updated HookSubscriptionInfo parsed from the API response.
    """
    result = org_api_call.put(
        "hooks",
        "subscriptions",
        subscription_id,
        version=_HOOK_API_VERSION,
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return HookSubscriptionInfo.model_validate(result)


def delete_hook_subscription(
    org_api_call: ApiCall,
    subscription_id: HookSubscriptionId,
) -> None:
    """Delete a service-hooks subscription.

    Args:
        org_api_call: Organisation-level ADO API call.
        subscription_id: UUID of the subscription to delete.
    """
    org_api_call.delete(
        "hooks",
        "subscriptions",
        subscription_id,
        version=_HOOK_API_VERSION,
    )


def iter_hook_publishers(
    org_api_call: ApiCall,
) -> Iterator[HookPublisherInfo]:
    """Iterate over all service-hooks publishers in the organisation.

    Args:
        org_api_call: Organisation-level ADO API call.

    Yields:
        HookPublisherInfo for each publisher.
    """
    result = org_api_call.get(
        "hooks",
        "publishers",
        version=_HOOK_API_VERSION,
    )
    for item in result.get("value", []):
        yield HookPublisherInfo.model_validate(item)


def list_hook_publishers(
    org_api_call: ApiCall,
) -> list[HookPublisherInfo]:
    """Return all service-hooks publishers in the organisation as a list."""
    return list(iter_hook_publishers(org_api_call))
