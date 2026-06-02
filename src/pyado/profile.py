"""Module to interact with Azure DevOps user profiles."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pydantic import BaseModel, Field

from pyado.api_call import ApiCall


class UserProfile(BaseModel):
    """Type to store Azure DevOps user profile details."""

    id: str
    display_name: str = Field(alias="displayName")
    email_address: str = Field(alias="emailAddress")
    public_alias: str = Field(alias="publicAlias")


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
