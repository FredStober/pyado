"""OOP entry point for pyado.

Provides :class:`Client`, the top-level object used to connect to an Azure
DevOps organisation and obtain project, profile, and other resource wrappers.

Example usage::

    from pyado.oop import Client

    client = Client(
        org_url="https://dev.azure.com/myorg",
        token="<personal-access-token>",
    )
    proj = client.get_project("ICS")
    wi = proj.get_work_item(153)
    proj.get_repository("myrepo").get_pr(32).link_work_item(wi)
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator

from pyado import raw
from pyado.oop.project import Project
from pyado.raw import ApiCall, UserProfile
from pyado.raw._core import _ADO_URL_ADAPTER

__all__ = ["Client"]


class Client:
    """Entry point for the pyado OOP API.

    Holds credentials and organisation URL, and acts as the factory for all
    top-level resource objects.

    Attributes:
        _org_url: Organisation base URL, trailing slash stripped.
        _token: ADO personal access token.
        _base_api_call: Organisation-level API call used by project listing.
    """

    def __init__(self, org_url: str, token: str) -> None:
        """Construct a Client for the given ADO organisation.

        Args:
            org_url: Organisation root URL, e.g.
                ``"https://dev.azure.com/myorg"``.  A trailing slash is
                ignored.
            token: ADO personal access token (or OAuth token).
        """
        self._org_url = org_url.rstrip("/")
        self._token = token
        self._base_api_call = ApiCall(
            access_token=token,
            url=_ADO_URL_ADAPTER.validate_python(f"{self._org_url}/_apis"),
        )

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def iter_projects(self) -> Iterator[Project]:
        """Iterate over all projects in the organisation.

        Yields:
            Project for each ADO project in the organisation.
        """
        for info in raw.iter_projects(self._base_api_call):
            project_api_call = ApiCall(
                access_token=self._token,
                url=_ADO_URL_ADAPTER.validate_python(
                    f"{self._org_url}/{info.name}/_apis"
                ),
            )
            yield Project(project_api_call, info)

    def get_project(self, name: str) -> Project:
        """Return a wrapper for a project identified by name.

        Args:
            name: Project name (case-sensitive, as it appears in ADO).

        Returns:
            Project wrapping the matched project.

        Raises:
            ValueError: If no project with the given name is found.
        """
        for project in self.iter_projects():
            if project.get_name() == name:
                return project
        err_msg = f"Project {name!r} not found in organisation {self._org_url!r}"
        raise ValueError(err_msg)

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------

    def get_my_profile(self) -> UserProfile:
        """Return the profile of the currently authenticated user.

        Returns:
            UserProfile for the authenticated user.
        """
        profile_api_call = raw.get_profile_api_call(self._token)
        return raw.get_my_profile(profile_api_call)
