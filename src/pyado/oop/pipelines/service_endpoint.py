"""OOP wrapper for Azure DevOps service connection (endpoint) resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import TYPE_CHECKING
from uuid import UUID

from pyado import raw
from pyado.raw import ServiceEndpointInfo

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project

__all__ = ["ServiceEndpoint"]


class ServiceEndpoint:
    """An ADO service connection.

    Wraps a single ADO service endpoint (service connection).
    Instances are obtained from
    :meth:`ProjectPipelines.iter_service_endpoints`.

    Attributes:
        _project: The Project this service endpoint belongs to.
        _id: Service endpoint UUID (always known).
        _info: Cached service endpoint data; ``None`` after
            :meth:`refresh`.
    """

    def __init__(self, project: "Project", info: ServiceEndpointInfo) -> None:
        """Construct a ServiceEndpoint wrapper.

        Args:
            project: The Project this service endpoint belongs to.
            info: ServiceEndpointInfo returned by the ADO endpoints API.
        """
        self._project = project
        self._id = info.id
        self._info: ServiceEndpointInfo | None = info

    @property
    def id(self) -> UUID:
        """Service endpoint UUID — always known, no API call."""
        return self._id

    @property
    def name(self) -> str:
        """Service endpoint name."""
        return self.info.name

    @property
    def type(self) -> str:
        """Service endpoint type (e.g. ``"github"``, ``"azurerm"``)."""
        return self.info.type

    @property
    def url(self) -> str:
        """Service endpoint target URL."""
        return self.info.url

    @property
    def is_ready(self) -> bool:
        """Whether the service endpoint is ready for use."""
        return self.info.is_ready

    @property
    def is_shared(self) -> bool:
        """Whether the service endpoint is shared across projects."""
        return self.info.is_shared

    @property
    def authorization_scheme(self) -> str | None:
        """Authorization scheme (e.g. ``"Token"``, ``"UsernamePassword"``)."""
        return self.info.authorization_scheme

    @property
    def info(self) -> ServiceEndpointInfo:
        """Full service endpoint data as returned by the API.

        Fetched lazily by re-querying the endpoint list if
        :meth:`refresh` was called since the last access.

        Raises:
            KeyError: If no service endpoint with this ID is found in
                the project.
        """
        if self._info is None:
            for endpoint_info in raw.iter_service_endpoints(self._project.api_call):
                if endpoint_info.id == self._id:
                    self._info = endpoint_info
                    break
            if self._info is None:
                raise KeyError(self._id)
        return self._info

    @property
    def project(self) -> "Project":
        """Project this service endpoint belongs to — zero-cost."""
        return self._project

    @property
    def org(self) -> "Organization":
        """Organisation this service endpoint belongs to — zero-cost."""
        return self._project.org

    def refresh(self) -> None:
        """Discard cached service endpoint info.

        The next access to :attr:`info` re-fetches from the endpoint list.
        """
        self._info = None
