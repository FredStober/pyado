"""Azure DevOps user profile API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pydantic import BaseModel, Field

from pyado.raw._core import _ADO_URL_ADAPTER, AccessToken, ApiCall

__all__ = [
    "UserProfile",
    "get_my_profile",
    "get_profile_api_call",
]

_PROFILE_API_URL = "https://app.vssps.visualstudio.com/_apis"


class UserProfile(BaseModel):
    """Type to store Azure DevOps user profile details."""

    id: str
    display_name: str = Field(alias="displayName")
    email_address: str = Field(alias="emailAddress")
    public_alias: str = Field(alias="publicAlias")


def get_profile_api_call(access_token: AccessToken) -> ApiCall:
    """Construct the API call for the user profile endpoint.

    The profile API lives on a different host from the rest of ADO
    (``app.vssps.visualstudio.com``), so it cannot be built from a
    project-level ApiCall.

    Args:
        access_token: ADO personal access token or OAuth token.

    Returns:
        ApiCall targeting ``https://app.vssps.visualstudio.com/_apis``.
    """
    return ApiCall(
        access_token=access_token,
        url=_ADO_URL_ADAPTER.validate_python(_PROFILE_API_URL),
    )


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
