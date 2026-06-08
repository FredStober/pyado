"""Azure DevOps service endpoint API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import Any, TypeAlias
from uuid import UUID

from pydantic import model_validator

from pyado.raw._core import AdoBaseModel, ApiCall

__all__ = [
    "ServiceEndpointId",
    "ServiceEndpointInfo",
    "iter_service_endpoints",
    "list_service_endpoints",
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
