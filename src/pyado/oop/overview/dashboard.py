"""OOP wrapper for Azure DevOps team dashboard resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import TYPE_CHECKING

from pyado import raw
from pyado.raw import ApiCall, DashboardId, DashboardInfo, WidgetInfo

if TYPE_CHECKING:
    from pyado.oop.boards.team import Team
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project

__all__ = ["Dashboard"]


class Dashboard:
    """An ADO team dashboard.

    Wraps a single ADO team dashboard and exposes its properties and
    widgets.  Instances are obtained from :meth:`Team.iter_dashboards`,
    :meth:`Team.get_dashboard`, :meth:`Project.iter_dashboards`, or
    :meth:`Project.get_dashboard`.

    Attributes:
        _team: The Team this dashboard belongs to.
        _id: Dashboard UUID (always known).
        _info: Cached dashboard data; ``None`` after :meth:`refresh`.
    """

    def __init__(self, team: "Team", info: DashboardInfo) -> None:
        """Construct a Dashboard wrapper.

        Args:
            team: The Team that owns this dashboard.
            info: DashboardInfo returned by the ADO dashboard endpoint.
        """
        self._team = team
        self._id = info.id
        self._info: DashboardInfo | None = info

    @property
    def id(self) -> DashboardId:
        """Dashboard UUID — always known, no API call."""
        return self._id

    @property
    def name(self) -> str:
        """Dashboard name."""
        return self.info.name

    @property
    def widgets(self) -> list[WidgetInfo]:
        """Widget list — populated only after a full detail fetch."""
        return self.info.widgets

    @property
    def info(self) -> DashboardInfo:
        """Full dashboard data as returned by the API.

        Fetched lazily from the API if :meth:`refresh` was called since
        the last access.
        """
        if self._info is None:
            self._info = raw.get_dashboard(self.api_call)
        return self._info

    @property
    def api_call(self) -> ApiCall:
        """Dashboard-level API call for direct use with pyado.raw functions."""
        return raw.get_dashboard_api_call(self._team.api_call, self._id)

    @property
    def team(self) -> "Team":
        """Team this dashboard belongs to — zero-cost."""
        return self._team

    @property
    def project(self) -> "Project":
        """Project this dashboard belongs to — zero-cost."""
        return self._team.project

    @property
    def org(self) -> "Organization":
        """Organisation this dashboard belongs to — zero-cost."""
        return self._team.org

    def refresh(self) -> None:
        """Discard cached dashboard info.

        The next access to :attr:`info` re-fetches from the API.
        """
        self._info = None
