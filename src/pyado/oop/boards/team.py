"""OOP wrapper for Azure DevOps team resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import TYPE_CHECKING

from pyado import raw
from pyado.oop.overview.dashboard import Dashboard
from pyado.raw import (
    ApiCall,
    DashboardId,
    SprintIterationId,
    SprintIterationInfo,
    SprintIterationTimeframe,
    TeamFieldValue,
    TeamMember,
)
from pyado.raw.boards.team import TeamInfo

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project
    from pyado.oop.service import AzureDevOpsService

__all__ = ["Team"]


class Team:
    """An Azure DevOps team within a project.

    Wraps a single ADO team and exposes its properties.  Instances are
    obtained from :meth:`Project.iter_teams` or :meth:`Project.get_team`.

    The :attr:`api_call` property returns a team-level call suitable for
    raw functions such as :func:`~pyado.raw.get_team_field_values` and
    :func:`~pyado.raw.add_team_iteration`.

    Attributes:
        _project: The Project this team belongs to.
        _info: TeamInfo data returned by the API.
    """

    def __init__(
        self,
        project: "Project",
        info: TeamInfo,
        service: "AzureDevOpsService",
    ) -> None:
        """Construct a Team wrapper.

        Args:
            project: The Project this team belongs to.
            info: TeamInfo returned by the ADO teams endpoint.
            service: The owning AzureDevOpsService (for API call construction).
        """
        self._project = project
        self._id = info.id
        self._name = info.name
        self._info: TeamInfo | None = info
        self._service = service

    @property
    def info(self) -> TeamInfo:
        """Full team data as returned by the API."""
        if self._info is None:
            self._info = raw.get_team(
                self._project.org.api_call, self._project.name, self._id
            )
        return self._info

    @property
    def id(self) -> str:
        """Team UUID string."""
        return self._id

    @property
    def name(self) -> str:
        """Team name."""
        return self._name

    @property
    def api_call(self) -> ApiCall:
        """Team-level API call for use with raw teamsettings functions.

        ADO team-scoped endpoints use the URL form
        ``{org}/{project}/{team}/_apis/...``, so the team name must sit
        *before* ``/_apis``, not after it.
        """
        return self._service.oop_api.make_team_api_call(self._project.name, self._name)

    @property
    def project(self) -> "Project":
        """Project this team belongs to — zero-cost."""
        return self._project

    @property
    def org(self) -> "Organization":
        """Organisation this team belongs to — zero-cost."""
        return self._project.org

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Discard cached team info.

        The next access to :attr:`info` re-fetches from the API.
        """
        self._info = None

    # ------------------------------------------------------------------
    # Sprint iterations
    # ------------------------------------------------------------------

    def iter_sprint_iterations(
        self,
        *,
        timeframe_filter: SprintIterationTimeframe | None = None,
    ) -> Iterator[SprintIterationInfo]:
        """Iterate over sprint iterations for this team.

        Args:
            timeframe_filter: When provided, restricts results to a specific
                timeframe.  ADO only supports
                ``SprintIterationTimeframe.CURRENT``.

        Yields:
            SprintIterationInfo for each sprint iteration.
        """
        yield from raw.iter_sprint_iterations(
            self.api_call, timeframe_filter=timeframe_filter
        )

    def get_field_values(self) -> list[TeamFieldValue]:
        """Return the area-path field configuration for this team.

        Returns:
            List of TeamFieldValue entries describing the team's allowed
            area paths.
        """
        return raw.get_team_field_values(self.api_call)

    def add_iteration(self, iteration_id: SprintIterationId) -> None:
        """Assign an existing iteration node to this team.

        Args:
            iteration_id: UUID of the iteration classification node to assign.
        """
        raw.add_team_iteration(self.api_call, iteration_id)

    def remove_iteration(self, iteration_id: SprintIterationId) -> None:
        """Remove an iteration from this team's sprint backlog.

        Args:
            iteration_id: UUID of the iteration classification node to remove.
        """
        raw.delete_team_iteration(self.api_call, iteration_id)

    # ------------------------------------------------------------------
    # Members
    # ------------------------------------------------------------------

    def iter_members(self) -> Iterator[TeamMember]:
        """Iterate over all members of this team.

        Yields:
            :class:`~pyado.raw.TeamMember` for each team member.
        """
        yield from raw.iter_team_members(
            self._project.org.api_call, self._project.name, self._id
        )

    def list_sprint_iterations(
        self,
        *,
        timeframe_filter: SprintIterationTimeframe | None = None,
    ) -> list[SprintIterationInfo]:
        """Return all sprint iterations for this team as a list."""
        return list(self.iter_sprint_iterations(timeframe_filter=timeframe_filter))

    def list_members(self) -> list[TeamMember]:
        """Return all members of this team as a list."""
        return list(self.iter_members())

    # ------------------------------------------------------------------
    # Dashboards
    # ------------------------------------------------------------------

    def iter_dashboards(self) -> Iterator[Dashboard]:
        """Iterate over all dashboards for this team.

        Yields:
            Dashboard for each dashboard belonging to this team.
        """
        for info in raw.iter_dashboards(self.api_call):
            yield Dashboard(self, info)

    def list_dashboards(self) -> list[Dashboard]:
        """Return all dashboards for this team as a list."""
        return list(self.iter_dashboards())

    def get_dashboard(self, dashboard_id: DashboardId) -> Dashboard:
        """Return a specific dashboard by ID.

        Args:
            dashboard_id: UUID of the dashboard.

        Returns:
            Dashboard wrapping the requested dashboard.
        """
        api = raw.get_dashboard_api_call(self.api_call, dashboard_id)
        info = raw.get_dashboard(api)
        return Dashboard(self, info)
