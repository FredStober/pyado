"""Azure DevOps vssps identity and graph-group API wrappers.

All endpoints in this module live on ``https://vssps.dev.azure.com/{org}/``.
Using the relative-path form ``/{org}/`` returns 404 HTML responses — this
module always constructs the full absolute base URL.
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator

from pydantic import BaseModel, Field

from pyado.raw._core import _ADO_URL_ADAPTER, AccessToken, ApiCall

__all__ = [
    "GraphGroup",
    "IdentityInfo",
    "get_identities",
    "get_vssps_api_call",
    "iter_graph_groups",
]

# Full absolute base URL for the vssps service — relative paths return 404.
_VSSPS_URL_TEMPLATE = "https://vssps.dev.azure.com/{org}"


class IdentityInfo(BaseModel):
    """An identity record returned by the vssps identities endpoint."""

    id: str
    provider_display_name: str = Field(alias="providerDisplayName")
    subject_descriptor: str | None = Field(alias="subjectDescriptor", default=None)
    is_active: bool = Field(alias="isActive", default=True)
    is_container: bool = Field(alias="isContainer", default=False)


class _IdentityInfoResults(BaseModel):
    """Internal: container for identity list results."""

    value: list[IdentityInfo]


class GraphGroup(BaseModel):
    """A graph group record returned by the vssps graph/groups endpoint."""

    display_name: str = Field(alias="displayName")
    descriptor: str
    principal_name: str = Field(alias="principalName")
    description: str | None = None
    origin: str | None = None
    origin_id: str | None = Field(alias="originId", default=None)
    mail_address: str | None = Field(alias="mailAddress", default=None)
    subject_kind: str = Field(alias="subjectKind")


class _GraphGroupResults(BaseModel):
    """Internal: container for graph group list results."""

    value: list[GraphGroup]


def get_vssps_api_call(access_token: AccessToken, org_name: str) -> ApiCall:
    """Construct an API call targeting the vssps service for an organisation.

    The vssps service requires the full absolute URL
    ``https://vssps.dev.azure.com/{org}``.  Relative paths to the vssps
    service return 404 HTML responses.

    Args:
        access_token: ADO personal access token or OAuth token.
        org_name: Azure DevOps organisation name (the ``{org}`` slug from
            ``https://dev.azure.com/{org}``).

    Returns:
        ApiCall targeting ``https://vssps.dev.azure.com/{org_name}``.
    """
    url = _VSSPS_URL_TEMPLATE.format(org=org_name)
    return ApiCall(
        access_token=access_token,
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
    return _IdentityInfoResults.model_validate(response).value


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
