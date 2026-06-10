"""Azure DevOps service endpoint API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import Any, TypeAlias
from uuid import UUID

from pydantic import Field, model_validator

from pyado.raw._core import AdoBaseModel, ApiCall

__all__ = [
    "ServiceEndpointAuthorization",
    "ServiceEndpointCreateRequest",
    "ServiceEndpointId",
    "ServiceEndpointInfo",
    "ServiceEndpointProjectReference",
    "ServiceEndpointUpdateRequest",
    "delete_service_endpoint",
    "get_service_endpoint",
    "iter_service_endpoints",
    "list_service_endpoints",
    "patch_service_endpoint_share",
    "post_service_endpoint",
    "put_service_endpoint",
]

_SERVICE_ENDPOINT_API_VERSION = "7.1"

#: UUID identifier for a service endpoint (service connection).
ServiceEndpointId: TypeAlias = UUID


class ServiceEndpointInfo(AdoBaseModel):
    """Minimal representation of an ADO service endpoint."""

    id: ServiceEndpointId
    name: str
    type: str
    url: str
    is_shared: bool = False
    is_ready: bool = False
    owner: str | None = None
    description: str | None = None
    authorization_scheme: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _extract_authorization_scheme(cls, data: Any) -> Any:
        """Flatten authorization.scheme into authorization_scheme.

        Returns:
            The (possibly modified) raw input dict.
        """
        if isinstance(data, dict):
            auth = data.get("authorization")
            if isinstance(auth, dict) and "authorization_scheme" not in data:
                data = {**data, "authorization_scheme": auth.get("scheme")}
        return data


class ServiceEndpointAuthorization(AdoBaseModel):
    """Authorization block for a service endpoint create or update request."""

    scheme: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class _SeProjectRef(AdoBaseModel):
    """Internal: project id/name pair within a service endpoint project reference."""

    id: str
    name: str


class ServiceEndpointProjectReference(AdoBaseModel):
    """A project reference entry within a service endpoint's project references list."""

    project_reference: _SeProjectRef
    name: str
    description: str | None = None


class ServiceEndpointCreateRequest(AdoBaseModel):
    """Request body for creating a service endpoint."""

    name: str
    type: str
    url: str
    authorization: ServiceEndpointAuthorization
    service_endpoint_project_references: list[ServiceEndpointProjectReference]
    description: str | None = None
    is_shared: bool = False
    data: dict[str, Any] | None = None


class ServiceEndpointUpdateRequest(AdoBaseModel):
    """Request body for updating a service endpoint."""

    id: ServiceEndpointId
    name: str
    type: str
    url: str
    authorization: ServiceEndpointAuthorization
    service_endpoint_project_references: list[ServiceEndpointProjectReference]
    description: str | None = None
    is_shared: bool = False
    data: dict[str, Any] | None = None


def iter_service_endpoints(
    project_api_call: ApiCall,
) -> Iterator[ServiceEndpointInfo]:
    """Iterate over all service endpoints in a project.

    Args:
        project_api_call: Project-level ADO API call.

    Yields:
        ServiceEndpointInfo for each service endpoint.
    """
    result = project_api_call.get(
        "serviceendpoint",
        "endpoints",
        version=_SERVICE_ENDPOINT_API_VERSION,
    )
    for item in result.get("value", []):
        yield ServiceEndpointInfo.model_validate(item)


def list_service_endpoints(
    project_api_call: ApiCall,
) -> list[ServiceEndpointInfo]:
    """Return all service endpoints in a project as a list."""
    return list(iter_service_endpoints(project_api_call))


def get_service_endpoint(
    project_api_call: ApiCall,
    endpoint_id: ServiceEndpointId,
) -> ServiceEndpointInfo:
    """Fetch a single service endpoint by ID.

    Args:
        project_api_call: Project-level ADO API call.
        endpoint_id: UUID of the service endpoint.

    Returns:
        ServiceEndpointInfo for the requested endpoint.
    """
    result = project_api_call.get(
        "serviceendpoint",
        "endpoints",
        endpoint_id,
        version=_SERVICE_ENDPOINT_API_VERSION,
    )
    return ServiceEndpointInfo.model_validate(result)


def post_service_endpoint(
    org_api_call: ApiCall,
    request: ServiceEndpointCreateRequest,
) -> ServiceEndpointInfo:
    """Create a new service endpoint.

    The endpoint is created at organisation scope and shared with the
    projects listed in ``request.service_endpoint_project_references``.

    Args:
        org_api_call: Organisation-level ADO API call.
        request: Create request specifying the name, type, URL, authorization,
            and project references.

    Returns:
        ServiceEndpointInfo for the newly created endpoint.
    """
    result = org_api_call.post(
        "serviceendpoint",
        "endpoints",
        version=_SERVICE_ENDPOINT_API_VERSION,
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return ServiceEndpointInfo.model_validate(result)


def put_service_endpoint(
    org_api_call: ApiCall,
    endpoint_id: ServiceEndpointId,
    request: ServiceEndpointUpdateRequest,
) -> ServiceEndpointInfo:
    """Update an existing service endpoint.

    Args:
        org_api_call: Organisation-level ADO API call.
        endpoint_id: UUID of the service endpoint to update.
        request: Update request.  The ``id`` field must match ``endpoint_id``.

    Returns:
        Updated ServiceEndpointInfo parsed from the API response.
    """
    result = org_api_call.put(
        "serviceendpoint",
        "endpoints",
        endpoint_id,
        version=_SERVICE_ENDPOINT_API_VERSION,
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return ServiceEndpointInfo.model_validate(result)


def delete_service_endpoint(
    project_api_call: ApiCall,
    endpoint_id: ServiceEndpointId,
    project_ids: list[str],
) -> None:
    """Delete a service endpoint from one or more projects.

    The DELETE endpoint is project-scoped and requires the ``projectIds``
    query parameter listing every project the endpoint should be removed from.

    Args:
        project_api_call: Project-level ADO API call.
        endpoint_id: UUID of the service endpoint to delete.
        project_ids: List of project UUIDs to remove the endpoint from.
    """
    project_api_call.delete(
        "serviceendpoint",
        "endpoints",
        endpoint_id,
        parameters={"projectIds": ",".join(project_ids)},
        version=_SERVICE_ENDPOINT_API_VERSION,
    )


def patch_service_endpoint_share(
    org_api_call: ApiCall,
    endpoint_id: ServiceEndpointId,
    project_references: list[ServiceEndpointProjectReference],
) -> None:
    """Share a service endpoint with additional projects.

    Sends a PATCH to the organisation-scoped endpoint, appending the
    given project references to the endpoint's sharing list.

    Args:
        org_api_call: Organisation-level ADO API call.
        endpoint_id: UUID of the service endpoint to share.
        project_references: Project references describing each project to
            share the endpoint with and the name to use in each project.
    """
    org_api_call.patch(
        "serviceendpoint",
        "endpoints",
        endpoint_id,
        version=_SERVICE_ENDPOINT_API_VERSION,
        json=[
            ref.model_dump(mode="json", by_alias=True, exclude_none=True)
            for ref in project_references
        ],
    )
