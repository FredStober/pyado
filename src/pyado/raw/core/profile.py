"""Azure DevOps user profile API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import requests

from pyado.raw._core import _ADO_URL_ADAPTER, AdoBaseModel, ApiCall

__all__ = [
    "ConnectionData",
    "ConnectionDataIdentity",
    "UserProfile",
    "get_connection_data",
    "get_my_profile",
    "get_profile_api_call",
]

_PROFILE_API_URL = "https://app.vssps.visualstudio.com/_apis"


class ConnectionDataIdentity(AdoBaseModel):
    """Minimal identity record returned inside the connectionData response."""

    id: str
    provider_display_name: str


class ConnectionData(AdoBaseModel):
    """Response from ``GET /_apis/connectionData``."""

    authenticated_user: ConnectionDataIdentity


class UserProfile(AdoBaseModel):
    """Type to store Azure DevOps user profile details."""

    id: str
    display_name: str
    email_address: str
    public_alias: str


def get_profile_api_call(session: requests.Session) -> ApiCall:
    """Construct the API call for the user profile endpoint.

    The profile API lives on a different host from the rest of ADO
    (``app.vssps.visualstudio.com``), so it cannot be built from a
    project-level ApiCall.

    Args:
        session: Authenticated ``requests.Session`` (from
            :func:`~pyado.raw.get_session` or
            :func:`~pyado.raw.get_bearer_session`).

    Returns:
        ApiCall targeting ``https://app.vssps.visualstudio.com/_apis``.
    """
    return ApiCall(
        session=session,
        url=_ADO_URL_ADAPTER.validate_python(_PROFILE_API_URL),
    )


def get_connection_data(org_api_call: ApiCall) -> ConnectionData:
    """Return connection data for the organisation including the authenticated user.

    The result's ``authenticated_user`` field contains the current user's identity
    GUID and display name.

    Args:
        org_api_call: Organisation-level ADO API call
            (e.g. ``ApiCall(access_token=…, url="https://dev.azure.com/myorg")``).
            Must not include a project path segment.

    Returns:
        ConnectionData for the organisation and authenticated user.
    """
    response = org_api_call.get("_apis", "connectionData", version="5.1-preview")
    return ConnectionData.model_validate(response)


def get_my_profile(profile_api_call: ApiCall) -> UserProfile:
    """Return the profile of the currently authenticated user.

    The ``profile_api_call`` must point at the user profile base URL
    (``https://app.vssps.visualstudio.com/_apis``), not the project API.

    Args:
        profile_api_call: API call targeting ``app.vssps.visualstudio.com/_apis``.

    Returns:
        UserProfile for the authenticated user.
    """
    response = profile_api_call.get(
        "profile",
        "profiles",
        "me",
        version="7.1-preview.1",
    )
    return UserProfile.model_validate(response)
