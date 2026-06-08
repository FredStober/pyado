"""OOP wrapper for Azure DevOps project resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import TYPE_CHECKING

from pyado import raw
from pyado.oop.boards import ProjectBoards
from pyado.oop.boards.team import Team
from pyado.oop.core.search import ProjectSearch
from pyado.oop.overview.dashboard import Dashboard
from pyado.oop.overview.wiki import Wiki
from pyado.oop.pipelines import ProjectPipelines
from pyado.oop.repos import ProjectRepos
from pyado.oop.settings import ProjectSettings
from pyado.raw import ApiCall, DashboardId, ProjectId, ProjectInfo

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.service import AzureDevOpsService

__all__ = ["Project"]


class Project:
    """An Azure DevOps project resource.

    **ADO concept:** a project is the *namespace* within an organisation that
    contains all other resources — repositories, pipelines, builds, work items,
    variable groups, teams, iteration/area hierarchies, etc.  ADO REST
    endpoints use the form ``{org}/{project}/_apis/…``.  The project is
    identified by a stable UUID (``ProjectId``) but is always addressed by
    name in the URL.  Raw endpoint: ``GET _apis/projects/{nameOrId}`` (docs:
    `core/Projects <https://learn.microsoft.com/rest/api/azure/devops/core/projects>`_).

    **Why it exists:** ``Project`` is the central hub of the OOP layer.  It
    owns the project-level ``ApiCall`` (the URL prefix shared by every
    sub-resource) and exposes five section objects that group related
    operations: :attr:`repos`, :attr:`boards`, :attr:`pipelines`,
    :attr:`search`, and :attr:`settings`.

    Instances are normally obtained from :meth:`Organization.get_project` or
    :meth:`Organization.iter_projects`.

    Project info is loaded lazily — the first access to :attr:`info` or
    :attr:`id` triggers a ``GET /projects/{name}`` call if ``info`` was not
    supplied at construction time. Call :meth:`refresh` to discard cached info
    and force a fresh fetch on next access.

    Attributes:
        _service: The owning AzureDevOpsService (cache and auth holder).
        _name: Project name (always known at construction).
        _api_call: Project-level API call built at construction; never changes.
        _info: Cached project data; ``None`` until first lazy fetch.
    """

    def __init__(
        self,
        service: "AzureDevOpsService",
        name: str,
        info: ProjectInfo | None = None,
    ) -> None:
        """Construct a Project wrapper.

        Args:
            service: The owning AzureDevOpsService.
            name: Project name (case-sensitive).
            info: Pre-fetched project data, or ``None`` to load lazily.
        """
        self._service = service
        self._name = name
        self._api_call = service.oop_api.make_project_api_call(name)
        self._info = info

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Project name — always known, no API call."""
        return self._name

    @property
    def id(self) -> ProjectId:
        """Project UUID (lazy-fetched if info was not supplied at construction)."""
        return self.info.id

    @property
    def info(self) -> ProjectInfo:
        """Project data — lazy-fetched on first access if not given at construction."""
        if self._info is None:
            self._info = raw.get_project(self._service.api_call, self._name)
        return self._info

    @property
    def api_call(self) -> ApiCall:
        """Project-level API call for direct use with pyado.raw functions."""
        return self._api_call

    @property
    def org(self) -> "Organization":
        """Organisation this project belongs to — zero-cost."""
        return self._service.org

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Discard cached project info and stale child-scope cache entries.

        The next access to :attr:`info` or :attr:`id` re-fetches from the API.
        All Repository and Pipeline objects cached under this project are also
        removed from the service cache so they are recreated fresh on next
        access.
        """
        self._service.oop_api.clear_cache_prefix(str(self._api_call.url) + "/")
        self._info = None

    # ------------------------------------------------------------------
    # Section properties
    # ------------------------------------------------------------------

    @property
    def repos(self) -> ProjectRepos:
        """The Repos section — repositories, pull requests, branches, tags."""
        return ProjectRepos(self)

    @property
    def boards(self) -> ProjectBoards:
        """The Boards section — work items, iterations, areas, teams."""
        return ProjectBoards(self)

    @property
    def pipelines(self) -> ProjectPipelines:
        """The Pipelines section — builds, runs, approvals, environments, agents."""
        return ProjectPipelines(self)

    @property
    def search(self) -> ProjectSearch:
        """Project-scoped search (code, work items, wiki, packages)."""
        return ProjectSearch(self)

    @property
    def settings(self) -> ProjectSettings:
        """The Settings section — project-level configuration."""
        return ProjectSettings(self)

    # ------------------------------------------------------------------
    # Teams
    # ------------------------------------------------------------------

    def iter_teams(self) -> Iterator[Team]:
        """Iterate over all teams in this project.

        Yields:
            Team for each team in the project.
        """
        yield from self.boards.iter_teams()

    def list_teams(self) -> list[Team]:
        """Return all teams in this project as a list."""
        return list(self.iter_teams())

    def get_default_team(self) -> Team:
        """Return the default team for this project.

        Uses the ``defaultTeam`` field from the project info when
        available; falls back to ``"{project_name} Team"`` if not.

        Returns:
            Team wrapping the project's default team.
        """
        default_team_info = self.info.default_team
        team_name = (
            default_team_info.name
            if default_team_info is not None
            else self._name + " Team"
        )
        return self.boards.get_team(team_name)

    # ------------------------------------------------------------------
    # Wikis
    # ------------------------------------------------------------------

    def iter_wikis(self) -> Iterator[Wiki]:
        """Iterate over all wikis in this project.

        Yields:
            Wiki for each wiki in the project.
        """
        for info in raw.iter_wikis(self._api_call):
            yield Wiki(self, info)

    def list_wikis(self) -> list[Wiki]:
        """Return all wikis in this project as a list."""
        return list(self.iter_wikis())

    # ------------------------------------------------------------------
    # Dashboards
    # ------------------------------------------------------------------

    def iter_dashboards(self, team: Team | None = None) -> Iterator[Dashboard]:
        """Iterate over all dashboards in this project.

        When *team* is given, only that team's dashboards are returned.
        When *team* is ``None``, dashboards from all teams are yielded.

        Args:
            team: Optional team to restrict the search to.

        Yields:
            Dashboard for each matching dashboard.
        """
        teams = [team] if team is not None else list(self.iter_teams())
        for t in teams:
            for info in raw.iter_dashboards(t.api_call):
                yield Dashboard(t, info)

    def list_dashboards(self, team: Team | None = None) -> list[Dashboard]:
        """Return dashboards in this project as a list.

        Args:
            team: Optional team to restrict the search to.

        Returns:
            List of Dashboard objects.
        """
        return list(self.iter_dashboards(team=team))

    def get_dashboard(
        self, dashboard_id: DashboardId, team: Team | None = None
    ) -> Dashboard:
        """Return a specific dashboard by ID.

        Args:
            dashboard_id: UUID of the dashboard.
            team: Team to look up the dashboard under.  When ``None``,
                the project's default team is used.

        Returns:
            Dashboard wrapping the requested dashboard.
        """
        if team is None:
            team = self.get_default_team()
        api = raw.get_dashboard_api_call(team.api_call, dashboard_id)
        info = raw.get_dashboard(api)
        return Dashboard(team, info)
