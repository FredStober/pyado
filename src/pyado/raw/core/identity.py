"""Azure DevOps vssps identity and graph-group API wrappers.

All endpoints in this module live on ``https://vssps.dev.azure.com/{org}/``.
Using the relative-path form ``/{org}/`` returns 404 HTML responses — this
module always constructs the full absolute base URL.
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from uuid import UUID

import requests

from pyado.raw._core import _ADO_URL_ADAPTER, AdoBaseModel, ApiCall

__all__ = [
    "AccessLevel",
    "GraphGroup",
    "GraphMembership",
    "GraphUser",
    "IdentityInfo",
    "UserEntitlement",
    "UserEntitlementCreateRequest",
    "delete_graph_membership",
    "get_graph_user",
    "get_identities",
    "get_vssps_api_call",
    "iter_graph_groups",
    "iter_graph_users",
    "iter_user_entitlements",
    "list_graph_memberships",
    "list_graph_users",
    "list_user_entitlements",
    "patch_user_entitlement",
    "post_user_entitlement",
    "put_graph_membership",
]

# Full absolute base URL for the vssps service — relative paths return 404.
_VSSPS_URL_TEMPLATE = "https://vssps.dev.azure.com/{org}"


class IdentityInfo(AdoBaseModel):
    """An identity record returned by the vssps identities endpoint."""

    id: str
    provider_display_name: str
    subject_descriptor: str | None = None
    is_active: bool = True
    is_container: bool = False


class _IdentityInfoResults(AdoBaseModel):
    """Internal: container for identity list results."""

    value: list[IdentityInfo | None]


class GraphGroup(AdoBaseModel):
    """A graph group record returned by the vssps graph/groups endpoint."""

    display_name: str
    descriptor: str
    principal_name: str
    description: str | None = None
    origin: str | None = None
    origin_id: str | None = None
    mail_address: str | None = None
    subject_kind: str


class _GraphGroupResults(AdoBaseModel):
    """Internal: container for graph group list results."""

    value: list[GraphGroup]


def get_vssps_api_call(session: requests.Session, org_name: str) -> ApiCall:
    """Construct an API call targeting the vssps service for an organisation.

    The vssps service requires the full absolute URL
    ``https://vssps.dev.azure.com/{org}``.  Relative paths to the vssps
    service return 404 HTML responses.

    Args:
        session: Authenticated ``requests.Session`` (from
            :func:`~pyado.raw.get_session` or
            :func:`~pyado.raw.get_bearer_session`).
        org_name: Azure DevOps organisation name (the ``{org}`` slug from
            ``https://dev.azure.com/{org}``).

    Returns:
        ApiCall targeting ``https://vssps.dev.azure.com/{org_name}``.
    """
    url = _VSSPS_URL_TEMPLATE.format(org=org_name)
    return ApiCall(
        session=session,
        url=_ADO_URL_ADAPTER.validate_python(url),
    )


def get_identities(
    vssps_call: ApiCall,
    descriptors: list[str],
) -> list[IdentityInfo]:
    """Look up one or more identities by subject descriptor.

    Args:
        vssps_call: vssps-scoped API call (from :func:`get_vssps_api_call`).
        descriptors: List of subject descriptor strings to resolve.

    Returns:
        List of IdentityInfo objects for the requested descriptors.
    """
    response = vssps_call.get(
        "_apis",
        "identities",
        parameters={"descriptors": ",".join(descriptors)},
        version="7.1",
    )
    results = _IdentityInfoResults.model_validate(response)
    return [item for item in results.value if item is not None]


def iter_graph_groups(vssps_call: ApiCall) -> Iterator[GraphGroup]:
    """Iterate over all graph groups in the organisation.

    Args:
        vssps_call: vssps-scoped API call (from :func:`get_vssps_api_call`).

    Yields:
        GraphGroup for each group in the organisation.
    """
    response = vssps_call.get(
        "_apis",
        "graph",
        "groups",
        version="7.1-preview.1",
    )
    yield from _GraphGroupResults.model_validate(response).value


def list_graph_groups(vssps_call: ApiCall) -> list[GraphGroup]:
    """Return all graph groups as a list."""
    return list(iter_graph_groups(vssps_call))


class GraphUser(AdoBaseModel):
    """A graph user record returned by the vssps graph/users endpoint."""

    descriptor: str
    display_name: str
    subject_kind: str
    principal_name: str | None = None
    mail_address: str | None = None
    origin: str | None = None
    origin_id: str | None = None
    is_deleted_in_origin: bool = False


class _GraphUserResults(AdoBaseModel):
    """Internal: container for graph user list results."""

    value: list[GraphUser]


class GraphMembership(AdoBaseModel):
    """A graph membership record linking a member to a container group."""

    container_descriptor: str
    member_descriptor: str


class _GraphMembershipResults(AdoBaseModel):
    """Internal: container for graph membership list results."""

    value: list[GraphMembership]


def list_graph_memberships(
    vssps_call: ApiCall,
    descriptor: str,
) -> list[str]:
    """Return the member descriptors of a group (direction=Down).

    Args:
        vssps_call: vssps-scoped API call (from get_vssps_api_call).
        descriptor: Subject descriptor of the container group.

    Returns:
        Sorted list of member subject descriptors.
    """
    response = vssps_call.get(
        "_apis",
        "graph",
        "memberships",
        descriptor,
        parameters={"direction": "Down"},
        version="7.1-preview.1",
    )
    if not response:
        return []
    return sorted(
        m.member_descriptor
        for m in _GraphMembershipResults.model_validate(response).value
    )


class AccessLevel(AdoBaseModel):
    """License / access-level information for a user entitlement."""

    licensing_source: str | None = None
    account_license_type: str | None = None
    msdn_license_type: str | None = None
    license_display_name: str | None = None
    status: str | None = None
    status_message: str | None = None
    assignment_source: str | None = None


class UserEntitlement(AdoBaseModel):
    """A user entitlement record pairing a graph user with an access level."""

    id: UUID
    user: GraphUser
    access_level: AccessLevel | None = None


class UserEntitlementCreateRequest(AdoBaseModel):
    """Request body for creating a new user entitlement."""

    user: GraphUser
    access_level: AccessLevel


class _UserEntitlementMembers(AdoBaseModel):
    """Internal: paged list container for user entitlements."""

    members: list[UserEntitlement]


class _UserEntitlementOperationResult(AdoBaseModel):
    """Internal: operation result returned by the add-entitlement endpoint."""

    is_success: bool
    result: UserEntitlement


def get_graph_user(vssps_call: ApiCall, descriptor: str) -> GraphUser:
    """Return a single graph user by subject descriptor.

    Args:
        vssps_call: vssps-scoped API call (from :func:`get_vssps_api_call`).
        descriptor: Subject descriptor of the user to retrieve.

    Returns:
        GraphUser for the requested descriptor.
    """
    response = vssps_call.get(
        "_apis",
        "graph",
        "users",
        descriptor,
        version="7.1-preview.1",
    )
    return GraphUser.model_validate(response)


def iter_graph_users(vssps_call: ApiCall) -> Iterator[GraphUser]:
    """Iterate over all graph users in the organisation.

    Args:
        vssps_call: vssps-scoped API call (from :func:`get_vssps_api_call`).

    Yields:
        GraphUser for each user in the organisation.
    """
    response = vssps_call.get(
        "_apis",
        "graph",
        "users",
        version="7.1-preview.1",
    )
    yield from _GraphUserResults.model_validate(response).value


def list_graph_users(vssps_call: ApiCall) -> list[GraphUser]:
    """Return all graph users as a list."""
    return list(iter_graph_users(vssps_call))


def put_graph_membership(
    vssps_call: ApiCall,
    subject_descriptor: str,
    container_descriptor: str,
) -> GraphMembership:
    """Add a user (or group) to a group.

    Args:
        vssps_call: vssps-scoped API call (from :func:`get_vssps_api_call`).
        subject_descriptor: Descriptor of the member to add.
        container_descriptor: Descriptor of the group to add the member to.

    Returns:
        GraphMembership describing the new membership link.
    """
    response = vssps_call.put(
        "_apis",
        "graph",
        "memberships",
        subject_descriptor,
        container_descriptor,
        version="7.1-preview.1",
    )
    return GraphMembership.model_validate(response)


def delete_graph_membership(
    vssps_call: ApiCall,
    subject_descriptor: str,
    container_descriptor: str,
) -> None:
    """Remove a user (or group) from a group.

    Args:
        vssps_call: vssps-scoped API call (from :func:`get_vssps_api_call`).
        subject_descriptor: Descriptor of the member to remove.
        container_descriptor: Descriptor of the group to remove the member from.
    """
    vssps_call.delete(
        "_apis",
        "graph",
        "memberships",
        subject_descriptor,
        container_descriptor,
        version="7.1-preview.1",
    )


def iter_user_entitlements(vssps_call: ApiCall) -> Iterator[UserEntitlement]:
    """Iterate over all user entitlements in the organisation.

    Args:
        vssps_call: vssps-scoped API call (from :func:`get_vssps_api_call`).

    Yields:
        UserEntitlement for each user in the organisation.
    """
    response = vssps_call.get(
        "_apis",
        "memberentitlementmanagement",
        "userentitlements",
        version="7.1-preview.2",
    )
    yield from _UserEntitlementMembers.model_validate(response).members


def list_user_entitlements(vssps_call: ApiCall) -> list[UserEntitlement]:
    """Return all user entitlements as a list."""
    return list(iter_user_entitlements(vssps_call))


def post_user_entitlement(
    vssps_call: ApiCall,
    request: UserEntitlementCreateRequest,
) -> UserEntitlement:
    """Add a user to the organisation with an access level.

    Args:
        vssps_call: vssps-scoped API call (from :func:`get_vssps_api_call`).
        request: Create request specifying the user and desired access level.

    Returns:
        UserEntitlement for the newly added user.
    """
    response = vssps_call.post(
        "_apis",
        "memberentitlementmanagement",
        "userentitlements",
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
        version="7.1-preview.2",
    )
    return _UserEntitlementOperationResult.model_validate(response).result


def patch_user_entitlement(
    vssps_call: ApiCall,
    user_id: UUID,
    access_level: AccessLevel,
) -> UserEntitlement:
    """Update the access level for an existing user entitlement.

    Args:
        vssps_call: vssps-scoped API call (from :func:`get_vssps_api_call`).
        user_id: UUID of the user whose access level should be updated.
        access_level: New access level to apply.

    Returns:
        Updated UserEntitlement.
    """
    patch_doc = [
        {
            "op": "replace",
            "path": "/accessLevel",
            "value": access_level.model_dump(
                mode="json", by_alias=True, exclude_none=True
            ),
        }
    ]
    response = vssps_call.patch(
        "_apis",
        "memberentitlementmanagement",
        "userentitlements",
        str(user_id),
        json=patch_doc,
        version="7.1-preview.2",
    )
    return _UserEntitlementOperationResult.model_validate(response).result
