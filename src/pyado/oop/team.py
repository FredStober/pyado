"""OOP wrapper for Azure DevOps team resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import TYPE_CHECKING

from pyado import raw
from pyado.raw import (
    ApiCall,
    SprintIterationId,
    SprintIterationInfo,
    SprintIterationTimeframe,
    TeamFieldValue,
)
from pyado.raw._core import _ADO_URL_ADAPTER
from pyado.raw.team import TeamInfo

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project

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

    def __init__(self, project: "Project", info: TeamInfo) -> None:
        """Construct a Team wrapper.

        Args:
            project: The Project this team belongs to.
            info: TeamInfo returned by the ADO teams endpoint.
        """
        self._project = project
        self._info = info

    @property
    def info(self) -> TeamInfo:
        """Full team data as returned by the API."""
        return self._info

    @property
    def id(self) -> str:
        """Team UUID string."""
        return self._info.id

    @property
    def name(self) -> str:
        """Team name."""
        return self._info.name

    @property
    def api_call(self) -> ApiCall:
        """Team-level API call for use with raw teamsettings functions.

        ADO team-scoped endpoints use the URL form
        ``{org}/{project}/{team}/_apis/...``, so the team name must sit
        *before* ``/_apis``, not after it.
        """
        proj_base = self._project.api_call.url.unicode_string().removesuffix("/_apis")
        return ApiCall(
            access_token=self._project.api_call.access_token,
            url=_ADO_URL_ADAPTER.validate_python(
                f"{proj_base}/{self._info.name}/_apis"
            ),
        )

    @property
    def project(self) -> "Project":
        """Project this team belongs to — zero-cost."""
        return self._project

    @property
    def org(self) -> "Organization":
        """Organisation this team belongs to — zero-cost."""
        return self._project.org

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
