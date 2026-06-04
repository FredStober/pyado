"""OOP wrapper for Azure DevOps project resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Callable, Iterator
from datetime import date
from typing import TYPE_CHECKING, Any, cast

from pyado import high, raw
from pyado.oop.area import Area
from pyado.oop.build import Build
from pyado.oop.iteration import Iteration
from pyado.oop.pipeline import Pipeline
from pyado.oop.pull_request import PullRequest
from pyado.oop.repository import Repository
from pyado.oop.team import Team
from pyado.oop.variable_group import VariableGroup
from pyado.oop.work_item import WorkItem
from pyado.raw import (
    ApiCall,
    BuildSearchCriteria,
    BuildStatus,
    ClassificationNode,
    PipelineApproval,
    PipelineDefinitionInfo,
    ProjectId,
    ProjectInfo,
    SprintIterationId,
    SprintIterationInfo,
    SprintIterationTimeframe,
    TeamFieldValue,
    VariableGroupId,
    WorkItemExpand,
    WorkItemField,
    WorkItemId,
    WorkItemQuery,
    WorkItemQueryExpand,
    WorkItemRelation,
    WorkItemsBatchRequest,
)
from pyado.raw._core import _ADO_URL_ADAPTER

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.service import AzureDevOpsService

__all__ = ["Project"]


class Project:
    """An Azure DevOps project resource.

    Wraps a single ADO project and exposes its operations as instance methods.
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
        """Project data (lazy-fetched on first access if not supplied at construction)."""
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
    # Repositories
    # ------------------------------------------------------------------

    def iter_repositories(self) -> Iterator[Repository]:
        """Iterate over all repositories in the project.

        Each yielded Repository is cached in the service so that repeated
        access returns the same instance.

        Yields:
            Repository for each repository in the project.
        """
        for info in raw.iter_repository_details(self._api_call):
            repo_api_call = raw.get_repository_api_call(self._api_call, info.id)
            cache_key = str(repo_api_call.url)
            repo: Repository = self._service.oop_api.get_or_cache(
                cache_key,
                cast(
                    "Callable[[], Repository]",
                    lambda i=info, a=repo_api_call: Repository(
                        self, a, i, self._service
                    ),
                ),
            )
            yield repo

    def get_repository(self, name_or_id: str) -> Repository:
        """Return a wrapper for a repository by name or UUID string.

        Args:
            name_or_id: Repository name (case-sensitive) or its UUID as a
                string.

        Returns:
            Repository wrapping the matched repository.

        Raises:
            ValueError: If no repository with the given name or ID is found.
        """
        for repo in self.iter_repositories():
            if repo.name == name_or_id or str(repo.id) == name_or_id:
                return repo
        err_msg = f"Repository {name_or_id!r} not found in project {self._name!r}"
        raise ValueError(err_msg)

    def iter_active_prs(self) -> Iterator[PullRequest]:
        """Iterate over all active pull requests in the project.

        Yields:
            PullRequest for each active PR, in API-returned order.
        """
        for item in high.iter_active_prs(self._api_call):
            repo_id = item.repository.id
            repo_api_call = raw.get_repository_api_call(self._api_call, repo_id)
            cache_key = str(repo_api_call.url)
            repo: Repository = self._service.oop_api.get_or_cache(
                cache_key,
                lambda: Repository(
                    self,
                    repo_api_call,
                    raw.get_repository_info(repo_api_call),
                    self._service,
                ),
            )
            pr_api_call = raw.get_pr_api_call(self._api_call, repo_id, item.pr_id)
            yield PullRequest(repo, pr_api_call, item)

    # ------------------------------------------------------------------
    # Work items
    # ------------------------------------------------------------------

    def get_work_item(self, work_item_id: WorkItemId) -> WorkItem:
        """Return a wrapper for a specific work item.

        Args:
            work_item_id: Numeric ID of the work item.

        Returns:
            WorkItem wrapping the requested work item.
        """
        wi_api_call = raw.get_work_item_api_call(self._api_call, work_item_id)
        info = raw.get_work_item(wi_api_call, expand=WorkItemExpand.RELATIONS)
        return WorkItem(self, wi_api_call, info)

    def iter_work_items(self, query: str) -> Iterator[WorkItem]:
        """Iterate over work items matching a WIQL query.

        Args:
            query: WIQL query string.  The ``SELECT`` list determines which
                fields are returned; use ``SELECT [System.Id]`` as a minimum.

        Yields:
            WorkItem for each work item returned by the query.
        """
        refs = raw.post_wiql(self._api_call, query)
        ids = [ref.id for ref in refs]
        for info in high.iter_work_item_details(self._api_call, ids):
            wi_api_call = raw.get_work_item_api_call(self._api_call, info.id)
            yield WorkItem(self, wi_api_call, info)

    def create_work_item(
        self,
        ticket_type: str,
        fields: dict[WorkItemField, Any],
        relations: list[WorkItemRelation] | None = None,
    ) -> WorkItem:
        """Create a new work item in the project.

        Args:
            ticket_type: ADO work item type name (e.g. ``"Task"``,
                ``"Bug"``, ``"User Story"``).
            fields: Mapping of field reference names to values.
                ``"System.WorkItemType"`` is set automatically from
                *ticket_type* and must not appear in *fields*.
            relations: Optional list of work item relations to add.

        Returns:
            WorkItem wrapping the newly created work item.
        """
        all_fields: dict[WorkItemField, Any] = {
            "System.WorkItemType": ticket_type,
            **fields,
        }
        info = high.create_work_item(self._api_call, all_fields, relations)
        wi_api_call = raw.get_work_item_api_call(self._api_call, info.id)
        return WorkItem(self, wi_api_call, info)

    # ------------------------------------------------------------------
    # Builds
    # ------------------------------------------------------------------

    def get_build(self, build_id: int) -> Build:
        """Return a wrapper for a specific build run.

        Args:
            build_id: Numeric ID of the build.

        Returns:
            Build wrapping the requested build.
        """
        build_api_call = raw.get_build_api_call(self._api_call, build_id)
        info = raw.get_build_details(build_api_call)
        return Build(self, build_api_call, info, self._service)

    def iter_builds(
        self,
        *,
        status_filter: BuildStatus | None = None,
    ) -> Iterator[Build]:
        """Iterate over builds in the project.

        Args:
            status_filter: Filter by build status (e.g. ``"completed"``).

        Yields:
            Build for each matching build.
        """
        criteria = BuildSearchCriteria(status_filter=status_filter)
        for info in raw.iter_builds(self._api_call, criteria):
            build_api_call = raw.get_build_api_call(self._api_call, info.id)
            yield Build(self, build_api_call, info, self._service)

    def start_build(
        self,
        definition_id: int,
        *,
        source_branch: str | None = None,
        source_version: str | None = None,
        parameters: dict[str, str] | None = None,
    ) -> Build:
        """Queue a new build against a pipeline definition.

        Args:
            definition_id: Numeric ID of the pipeline definition to run.
            source_branch: Override the source branch for the build.
            source_version: Override the commit SHA to build.
            parameters: Optional key/value build parameters dict.

        Returns:
            Build wrapping the newly queued build.
        """
        info = high.start_build(
            self._api_call,
            definition_id,
            source_branch=source_branch,
            source_version=source_version,
            parameters=parameters,
        )
        build_api_call = raw.get_build_api_call(self._api_call, info.id)
        return Build(self, build_api_call, info, self._service)

    # ------------------------------------------------------------------
    # Pipelines
    # ------------------------------------------------------------------

    def iter_pipeline_definitions(self) -> Iterator[PipelineDefinitionInfo]:
        """Iterate over classic (build) pipeline definitions in the project.

        Yields:
            PipelineDefinitionInfo for each definition.
        """
        yield from raw.iter_pipeline_definitions(self._api_call)

    def iter_pipelines(self) -> Iterator[Pipeline]:
        """Iterate over Pipelines v2 definitions in the project.

        Each yielded Pipeline is cached in the service.

        Yields:
            Pipeline for each pipeline definition.
        """
        for info in raw.iter_pipelines(self._api_call):
            cache_key = str(self._api_call.url) + "/pipelines/" + str(info.id)
            pipeline: Pipeline = self._service.oop_api.get_or_cache(
                cache_key,
                cast(
                    "Callable[[], Pipeline]",
                    lambda i=info: Pipeline(self, i.id, i.name, i),
                ),
            )
            yield pipeline

    def get_pipeline(self, pipeline_id: int) -> Pipeline:
        """Return a wrapper for a specific Pipelines v2 definition.

        The pipeline is cached in the service.

        Args:
            pipeline_id: Numeric ID of the pipeline.

        Returns:
            Pipeline wrapping the requested definition.
        """
        cache_key = str(self._api_call.url) + "/pipelines/" + str(pipeline_id)

        def factory() -> Pipeline:
            info = raw.get_pipeline(self._api_call, pipeline_id)
            return Pipeline(self, info.id, info.name, info)

        return self._service.oop_api.get_or_cache(cache_key, factory)

    def iter_pending_approvals(self) -> Iterator[PipelineApproval]:
        """Iterate over pending pipeline approvals in the project.

        Yields:
            PipelineApproval for each pending approval gate.
        """
        yield from high.iter_pending_approvals(self._api_call)

    def approve_pipeline(
        self,
        approval_id: str,
        *,
        comment: str = "",
    ) -> None:
        """Approve a pending pipeline environment approval.

        Args:
            approval_id: UUID string of the approval to approve.  Obtain it
                from :meth:`iter_pending_approvals`.
            comment: Optional comment to attach to the approval.
        """
        high.approve_pipeline(self._api_call, approval_id, comment=comment)

    # ------------------------------------------------------------------
    # Variable groups
    # ------------------------------------------------------------------

    def iter_variable_groups(self) -> Iterator[VariableGroup]:
        """Iterate over variable groups in the project.

        Yields:
            VariableGroup for each variable group in the project.
        """
        for info in raw.iter_variable_group_details(self._api_call):
            vg_api_call = raw.get_variable_group_api_call(self._api_call, info.id)
            yield VariableGroup(self, vg_api_call, info)

    def get_variable_group(self, name: str) -> VariableGroup:
        """Return a wrapper for a variable group by name.

        Args:
            name: Name of the variable group (case-sensitive).

        Returns:
            VariableGroup wrapping the matched group.

        Raises:
            ValueError: If no variable group with the given name is found.
        """
        for vg in self.iter_variable_groups():
            if vg.name == name:
                return vg
        err_msg = f"Variable group {name!r} not found in project {self._name!r}"
        raise ValueError(err_msg)

    def get_variable_group_by_id(self, group_id: VariableGroupId) -> VariableGroup:
        """Return a wrapper for a specific variable group by numeric ID.

        Args:
            group_id: Numeric ID of the variable group.

        Returns:
            VariableGroup wrapping the requested group.

        Raises:
            ValueError: If no variable group with the given ID is found.
        """
        for vg in self.iter_variable_groups():
            if vg.id == group_id:
                return vg
        err_msg = f"Variable group {group_id!r} not found in project {self._name!r}"
        raise ValueError(err_msg)

    # ------------------------------------------------------------------
    # WIT queries
    # ------------------------------------------------------------------

    def get_query_tree(
        self,
        *,
        depth: int = 2,
        expand: WorkItemQueryExpand = WorkItemQueryExpand.ALL,
    ) -> list[WorkItemQuery]:
        """Return the root-level query folders for the project.

        ADO exposes two root folders — "My Queries" and "Shared Queries".
        Use :meth:`get_query_folder` with a folder's ``id`` to drill into
        a specific folder.

        Args:
            depth: Number of folder levels to expand below the root folders
                (default: 2).
            expand: Which fields to include in the response.

        Returns:
            List of WorkItemQuery objects, one per root folder.
        """
        return raw.get_query_tree(self._api_call, depth=depth, expand=expand)

    def get_query_folder(
        self,
        folder_id: str,
        *,
        depth: int = 1,
        expand: WorkItemQueryExpand = WorkItemQueryExpand.ALL,
    ) -> WorkItemQuery:
        """Return a specific query folder by ID.

        Args:
            folder_id: UUID of the query folder.
            depth: Number of folder levels to expand (default: 1).
            expand: Which fields to include in the response.

        Returns:
            WorkItemQuery representing the requested folder.
        """
        return raw.get_query_folder(
            self._api_call, folder_id, depth=depth, expand=expand
        )

    # ------------------------------------------------------------------
    # Iterations
    # ------------------------------------------------------------------

    def get_iteration_node(
        self,
        path: str | None = None,
        *,
        depth: int = 1,
    ) -> Iteration:
        """Return the iteration classification node tree for the project.

        Args:
            path: Path within the iteration tree (e.g. ``"Sprint 1"``), or
                ``None`` for the root.
            depth: Number of child levels to fetch below the node (default: 1).

        Returns:
            Iteration wrapping the requested node, with children populated to
            *depth* levels.
        """
        info: ClassificationNode = raw.get_classification_node(
            self._api_call, path, depth=depth
        )
        return Iteration(self, info)

    def _make_team_api_call(self, team_name: str) -> ApiCall:
        """Build a team-scoped API call for *team_name*.

        ADO team-scoped endpoints use ``{org}/{project}/{team}/_apis/...``,
        so the team name must sit *before* ``/_apis``.  Using
        ``self._api_call.build_call(team_name)`` would produce the wrong
        form ``{project}/_apis/{team}/...``.

        Returns:
            ApiCall targeting ``{org}/{project}/{team}/_apis``.
        """
        proj_base = self._api_call.url.unicode_string().removesuffix("/_apis")
        return ApiCall(
            access_token=self._api_call.access_token,
            url=_ADO_URL_ADAPTER.validate_python(f"{proj_base}/{team_name}/_apis"),
        )

    def iter_sprint_iterations(
        self,
        team_name: str,
        *,
        timeframe_filter: SprintIterationTimeframe | None = None,
    ) -> Iterator[SprintIterationInfo]:
        """Iterate over sprint iterations for a team.

        Args:
            team_name: Name of the team within this project.
            timeframe_filter: When provided, restricts results to a specific
                timeframe.  ADO only supports
                ``SprintIterationTimeframe.CURRENT``.

        Yields:
            SprintIterationInfo for each sprint iteration.
        """
        yield from raw.iter_sprint_iterations(
            self._make_team_api_call(team_name), timeframe_filter=timeframe_filter
        )

    def get_team_field_values(self, team_name: str) -> list[TeamFieldValue]:
        """Return the area-path field configuration for a team.

        Args:
            team_name: Name of the team within this project.

        Returns:
            List of TeamFieldValue entries describing the team's allowed
            area paths.
        """
        return raw.get_team_field_values(self._make_team_api_call(team_name))

    def add_team_iteration(
        self,
        team_name: str,
        iteration_id: SprintIterationId,
    ) -> None:
        """Assign an existing iteration node to a team.

        Args:
            team_name: Name of the team within this project.
            iteration_id: UUID of the iteration classification node to assign.
                Obtain it from :meth:`get_iteration_node` or
                :meth:`create_iteration`.
        """
        raw.add_team_iteration(self._make_team_api_call(team_name), iteration_id)

    def create_iteration(
        self,
        name: str,
        parent_path: str | None = None,
        *,
        start_date: date | None = None,
        finish_date: date | None = None,
    ) -> str:
        """Create a new iteration node under a parent path.

        Args:
            name: Name of the new iteration node.
            parent_path: Path of the parent node within the iteration tree, or
                ``None`` to create at the root.
            start_date: Optional start date for the iteration.
            finish_date: Optional end date for the iteration.

        Returns:
            GUID identifier string of the created node.
        """
        return raw.create_classification_node(
            self._api_call,
            name,
            parent_path,
            start_date=start_date,
            finish_date=finish_date,
        )

    # ------------------------------------------------------------------
    # Areas
    # ------------------------------------------------------------------

    def get_area_node(
        self,
        path: str | None = None,
        *,
        depth: int = 1,
    ) -> Area:
        """Return the area classification node tree for the project.

        Args:
            path: Path within the area tree (e.g. ``"Team A"``), or ``None``
                for the root.
            depth: Number of child levels to fetch below the node (default: 1).

        Returns:
            Area wrapping the requested node, with children populated to
            *depth* levels.
        """
        info: ClassificationNode = raw.get_area_node(self._api_call, path, depth=depth)
        return Area(self, info)

    def create_area(
        self,
        name: str,
        parent_path: str | None = None,
    ) -> str:
        """Create a new area node under a parent path.

        Args:
            name: Name of the new area node.
            parent_path: Path of the parent node within the area tree, or
                ``None`` to create at the root.

        Returns:
            GUID identifier string of the created node.
        """
        return raw.create_area_node(self._api_call, name, parent_path)

    # ------------------------------------------------------------------
    # Batch work items
    # ------------------------------------------------------------------

    def get_work_items(self, ids: list[WorkItemId]) -> list[WorkItem]:
        """Fetch multiple work items in a single API call.

        Prefer this over repeated :meth:`get_work_item` calls when you
        already have a list of IDs (e.g. from
        :meth:`Build.iter_work_item_ids`).

        Args:
            ids: List of numeric work item IDs to fetch.

        Returns:
            List of WorkItem objects, in the same order as *ids*.
        """
        infos = raw.post_work_items_batch(
            self._api_call, WorkItemsBatchRequest(ids=ids)
        )
        result: list[WorkItem] = []
        for info in infos:
            wi_api_call = raw.get_work_item_api_call(self._api_call, info.id)
            result.append(WorkItem(self, wi_api_call, info))
        return result

    # ------------------------------------------------------------------
    # Teams
    # ------------------------------------------------------------------

    def iter_teams(self) -> Iterator[Team]:
        """Iterate over all teams in this project.

        Yields:
            Team for each team in the project.
        """
        for info in raw.iter_teams(self.org.api_call, self.name):
            yield Team(self, info)

    def get_team(self, name_or_id: str) -> Team:
        """Return a specific team by name or UUID.

        Args:
            name_or_id: Team name or UUID string.

        Returns:
            Team wrapping the requested team.
        """
        info = raw.get_team(self.org.api_call, self.name, name_or_id)
        return Team(self, info)
