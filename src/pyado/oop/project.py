"""OOP wrapper for Azure DevOps project resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Callable, Iterator
from datetime import date
from typing import TYPE_CHECKING, Any, cast

from pyado import raw
from pyado.oop import _build, _work_item
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
    ClassificationNodeAttributes,
    ClassificationNodeRequest,
    ClassificationNodeUrlType,
    PipelineApproval,
    PipelineDefinitionInfo,
    PipelineId,
    ProjectId,
    ProjectInfo,
    PullRequestId,
    PullRequestSearchCriteria,
    PullRequestStatus,
    RepositoryId,
    SprintIterationId,
    SprintIterationInfo,
    SprintIterationTimeframe,
    TeamFieldValue,
    TextFormat,
    VariableGroupCreateRequest,
    VariableGroupId,
    VariableGroupProjectReference,
    WorkItemExpand,
    WorkItemField,
    WorkItemId,
    WorkItemQuery,
    WorkItemQueryExpand,
    WorkItemRelation,
    WorkItemsBatchRequest,
)

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

    def get_repository(self, name: str) -> Repository:
        """Return a wrapper for a repository by name.

        Args:
            name: Repository name (case-sensitive).

        Returns:
            Repository wrapping the matched repository.

        Raises:
            ValueError: If no repository with the given name is found.
        """
        for repo in self.iter_repositories():
            if repo.name == name:
                return repo
        err_msg = f"Repository {name!r} not found in project {self._name!r}"
        raise ValueError(err_msg)

    def get_repository_by_id(self, repo_id: RepositoryId) -> Repository:
        """Return a wrapper for a repository by UUID.

        Args:
            repo_id: Repository UUID.

        Returns:
            Repository wrapping the matched repository.

        Raises:
            ValueError: If no repository with the given ID is found.
        """
        for repo in self.iter_repositories():
            if repo.id == repo_id:
                return repo
        err_msg = f"Repository {repo_id!r} not found in project {self._name!r}"
        raise ValueError(err_msg)

    def iter_active_prs(self, *, expand: str | None = None) -> Iterator[PullRequest]:
        """Iterate over all active pull requests in the project.

        Convenience shortcut for
        ``iter_pull_requests(status=PullRequestStatus.ACTIVE)``.

        Args:
            expand: Optional ``$expand`` value (e.g. ``"labels"``,
                ``"reviewers"``).  Pass ``"labels"`` to avoid separate
                ``get_tags()`` calls per PR.

        Yields:
            PullRequest for each active PR, in API-returned order.
        """
        yield from self.iter_pull_requests(
            status=PullRequestStatus.ACTIVE, expand=expand
        )

    def get_pull_request(
        self,
        pr_id: PullRequestId,
        repo_id: RepositoryId | None = None,
    ) -> PullRequest:
        """Return a PR wrapper by ID.

        When *repo_id* is provided, the PR is fetched directly from the
        repository-scoped endpoint (one API call).  When omitted, a
        project-wide search is performed instead.

        Args:
            pr_id: Numeric pull request ID.
            repo_id: Optional repository UUID.  When supplied, the direct
                lookup path is used; when omitted the project-wide
                ``searchCriteria.pullRequestId`` search is used.

        Returns:
            PullRequest wrapping the matched PR.

        Raises:
            ValueError: If no PR with *pr_id* exists in this project.
        """
        if repo_id is not None:
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
            pr_api_call = raw.get_pull_request_api_call(self._api_call, repo_id, pr_id)
            info = raw.get_pull_request_details(pr_api_call)
            return PullRequest(repo, pr_api_call, info)
        items = list(
            raw.iter_pull_requests(
                self._api_call,
                search_criteria=PullRequestSearchCriteria(pull_request_id=pr_id),
            )
        )
        if not items:
            err_msg = f"PR {pr_id} not found in project {self._name!r}."
            raise ValueError(err_msg)
        item = items[0]
        found_repo_id = item.repository.id
        repo_api_call = raw.get_repository_api_call(self._api_call, found_repo_id)
        cache_key = str(repo_api_call.url)
        repo = self._service.oop_api.get_or_cache(
            cache_key,
            lambda: Repository(
                self,
                repo_api_call,
                raw.get_repository_info(repo_api_call),
                self._service,
            ),
        )
        pr_api_call = raw.get_pull_request_api_call(
            self._api_call, found_repo_id, pr_id
        )
        return PullRequest(repo, pr_api_call, item)

    def iter_pull_requests(
        self,
        status: PullRequestStatus | None = None,
        *,
        criteria: PullRequestSearchCriteria | None = None,
        expand: str | None = None,
    ) -> Iterator[PullRequest]:
        """Iterate over pull requests across all repositories in the project.

        Args:
            status: Filter by PR lifecycle status.  When ``None`` (default),
                all PRs are returned regardless of status.  Ignored when
                *criteria* is provided.
            criteria: Full search criteria; overrides *status* when provided.
            expand: Optional ``$expand`` value (e.g. ``"labels"``,
                ``"reviewers"``).

        Yields:
            PullRequest for each matching PR, in API-returned order.
        """
        effective_criteria = criteria or PullRequestSearchCriteria(status=status)
        for item in raw.iter_pull_requests(
            self._api_call, search_criteria=effective_criteria, expand=expand
        ):
            repo_id = item.repository.id
            repo_api_call = raw.get_repository_api_call(self._api_call, repo_id)
            cache_key = str(repo_api_call.url)

            def _make_repo(r: raw.ApiCall = repo_api_call) -> Repository:
                return Repository(self, r, raw.get_repository_info(r), self._service)

            repo: Repository = self._service.oop_api.get_or_cache(cache_key, _make_repo)
            pr_api_call = raw.get_pull_request_api_call(
                self._api_call, repo_id, item.pr_id
            )
            yield PullRequest(repo, pr_api_call, item, expand)

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
        expand = WorkItemExpand.RELATIONS
        info = raw.get_work_item(wi_api_call, expand=expand)
        return WorkItem(self, wi_api_call, info, expand)

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
        for info in _work_item.iter_work_item_details(self._api_call, ids):
            wi_api_call = raw.get_work_item_api_call(self._api_call, info.id)
            yield WorkItem(self, wi_api_call, info, WorkItemExpand.RELATIONS)

    def create_work_item(
        self,
        ticket_type: str,
        fields: dict[WorkItemField, Any],
        relations: list[WorkItemRelation] | None = None,
        *,
        multiline_fields_format: dict[WorkItemField, TextFormat] | None = None,
    ) -> WorkItem:
        """Create a new work item in the project.

        Args:
            ticket_type: ADO work item type name (e.g. ``"Task"``,
                ``"Bug"``, ``"User Story"``).
            fields: Mapping of field reference names to values.
                ``"System.WorkItemType"`` must not appear in *fields*; it is
                set automatically from *ticket_type*.
            relations: Optional list of work item relations to add.
            multiline_fields_format: Optional per-field format override
                (``"html"`` or ``"markdown"``).

        Returns:
            WorkItem wrapping the newly created work item.

        Raises:
            ValueError: If *fields* contains ``"System.WorkItemType"``.
        """
        if "System.WorkItemType" in fields:
            err_msg = (
                '"System.WorkItemType" must not appear in fields; '
                "pass the type as the ticket_type argument instead."
            )
            raise ValueError(err_msg)
        all_fields: dict[WorkItemField, Any] = {
            "System.WorkItemType": ticket_type,
            **fields,
        }
        created = _work_item.create_work_item(
            self._api_call,
            all_fields,
            relations,
            multiline_fields_format=multiline_fields_format,
        )
        wi_api_call = raw.get_work_item_api_call(self._api_call, created.id)
        expand = WorkItemExpand.RELATIONS
        info = raw.get_work_item(wi_api_call, expand=expand)
        return WorkItem(self, wi_api_call, info, expand)

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
        definition_id: int | None = None,
        status_filter: BuildStatus | None = None,
        branch_name: str | None = None,
        top: int | None = None,
    ) -> Iterator[Build]:
        """Iterate over builds in the project.

        Args:
            definition_id: Filter to a specific pipeline definition ID.
            status_filter: Filter by build status (e.g. ``"completed"``).
            branch_name: Filter by source branch ref name
                (e.g. ``"refs/heads/main"``).
            top: Maximum number of builds to return.

        Yields:
            Build for each matching build.
        """
        criteria = BuildSearchCriteria(
            definition_id=definition_id,
            status_filter=status_filter,
            branch_name=branch_name,
            top=top,
        )
        for info in raw.iter_builds(self._api_call, search_criteria=criteria):
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
        info = _build.start_build(
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

    def get_pipeline(self, name: str) -> Pipeline:
        """Return a wrapper for a Pipelines v2 definition by name.

        Iterates all pipeline definitions and returns the first whose name
        matches *name* exactly (case-sensitive).  Each pipeline is cached in
        the service via :meth:`iter_pipelines`.

        Args:
            name: Pipeline name (case-sensitive).

        Returns:
            Pipeline wrapping the matched definition.

        Raises:
            ValueError: If no pipeline with the given name is found.
        """
        for pipeline in self.iter_pipelines():
            if pipeline.name == name:
                return pipeline
        err_msg = f"Pipeline {name!r} not found in project {self._name!r}"
        raise ValueError(err_msg)

    def get_pipeline_by_id(self, pipeline_id: PipelineId) -> Pipeline:
        """Return a wrapper for a specific Pipelines v2 definition by numeric ID.

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
        yield from _build.iter_pending_approvals(self._api_call)

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
        _build.approve_pipeline(self._api_call, approval_id, comment=comment)

    def reject_pipeline(
        self,
        approval_id: str,
        *,
        comment: str = "",
    ) -> None:
        """Reject a pending pipeline environment approval.

        Args:
            approval_id: UUID string of the approval to reject.  Obtain it
                from :meth:`iter_pending_approvals`.
            comment: Optional comment to attach to the rejection.
        """
        _build.reject_pipeline(self._api_call, approval_id, comment=comment)

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

    def create_variable_group(
        self,
        name: str,
        variables: dict[str, Any],
        *,
        description: str | None = None,
        var_group_type: str = "Vsts",
    ) -> VariableGroup:
        """Create a new variable group in this project.

        Args:
            name: Name for the new variable group.
            variables: Initial variable mapping (name → VariableInfo).
            description: Optional description for the group.
            var_group_type: ADO type string (default: ``"Vsts"``).

        Returns:
            VariableGroup wrapping the newly created group.
        """
        project_ref = VariableGroupProjectReference.model_validate(
            {
                "name": name,
                "projectReference": {
                    "id": str(self.id),
                    "name": self._name,
                },
            }
        )
        info = raw.post_variable_group(
            self._api_call,
            VariableGroupCreateRequest(
                name=name,
                variables=variables,
                variable_group_project_references=[project_ref],
                description=description,
                type=var_group_type,
            ),
        )
        vg_api_call = raw.get_variable_group_api_call(self._api_call, info.id)
        return VariableGroup(self, vg_api_call, info)

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
            self._api_call,
            path,
            node_type=ClassificationNodeUrlType.ITERATIONS,
            depth=depth,
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
        return self._service.oop_api.make_team_api_call(self._name, team_name)

    def iter_team_sprint_iterations(
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
    ) -> Iteration:
        """Create a new iteration node under a parent path.

        Args:
            name: Name of the new iteration node.
            parent_path: Path of the parent node within the iteration tree, or
                ``None`` to create at the root.
            start_date: Optional start date for the iteration.
            finish_date: Optional end date for the iteration.

        Returns:
            Iteration wrapping the newly created iteration node.
        """
        attrs = None
        if start_date or finish_date:
            attrs = ClassificationNodeAttributes.model_validate(
                {
                    "startDate": start_date.isoformat() + "T00:00:00Z"
                    if start_date
                    else None,
                    "finishDate": finish_date.isoformat() + "T00:00:00Z"
                    if finish_date
                    else None,
                }
            )
        node = raw.create_classification_node(
            self._api_call,
            ClassificationNodeRequest(name=name, attributes=attrs),
            parent_path,
            node_type=ClassificationNodeUrlType.ITERATIONS,
        )
        return Iteration(self, node)

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
        info: ClassificationNode = raw.get_classification_node(
            self._api_call, path, node_type=ClassificationNodeUrlType.AREAS, depth=depth
        )
        return Area(self, info)

    def create_area(
        self,
        name: str,
        parent_path: str | None = None,
    ) -> Area:
        """Create a new area node under a parent path.

        Args:
            name: Name of the new area node.
            parent_path: Path of the parent node within the area tree, or
                ``None`` to create at the root.

        Returns:
            Area wrapping the newly created area node.
        """
        node = raw.create_classification_node(
            self._api_call,
            ClassificationNodeRequest(name=name),
            parent_path,
            node_type=ClassificationNodeUrlType.AREAS,
        )
        return Area(self, node)

    # ------------------------------------------------------------------
    # Batch work items
    # ------------------------------------------------------------------

    def get_work_items(
        self,
        ids: list[WorkItemId],
        *,
        expand: WorkItemExpand | None = WorkItemExpand.RELATIONS,
    ) -> list[WorkItem]:
        """Fetch multiple work items in a single API call.

        Prefer this over repeated :meth:`get_work_item` calls when you
        already have a list of IDs (e.g. from
        :meth:`Build.iter_work_item_ids`).

        Args:
            ids: List of numeric work item IDs to fetch.
            expand: Expand mode controlling which extra data ADO includes
                (default: ``WorkItemExpand.RELATIONS``).  Pass ``None`` to
                fetch fields only.

        Returns:
            List of WorkItem objects, in the same order as *ids*.
        """
        infos = raw.post_work_items_batch(
            self._api_call, WorkItemsBatchRequest(ids=ids, expand=expand)
        )
        result: list[WorkItem] = []
        for info in infos:
            wi_api_call = raw.get_work_item_api_call(self._api_call, info.id)
            result.append(WorkItem(self, wi_api_call, info, expand))
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
            yield Team(self, info, self._service)

    def get_team(self, name: str) -> Team:
        """Return a specific team by name.

        Args:
            name: Team name (case-sensitive).

        Returns:
            Team wrapping the requested team.
        """
        info = raw.get_team(self.org.api_call, self.name, name)
        return Team(self, info, self._service)

    def get_team_by_id(self, team_id: str) -> Team:
        """Return a specific team by UUID string.

        The ADO ``GET /teams/{teamId}`` endpoint accepts both a name string
        and a UUID at the same URL, so the underlying raw call is identical
        to :meth:`get_team`.  This method is kept as a distinct entry point
        so that call-sites which hold a UUID can express that intent clearly
        without conflating it with a name lookup.

        Args:
            team_id: Team UUID string.

        Returns:
            Team wrapping the requested team.
        """
        info = raw.get_team(self.org.api_call, self.name, team_id)
        return Team(self, info, self._service)

    def list_repositories(self) -> list[Repository]:
        """Return all repositories in this project as a list."""
        return list(self.iter_repositories())

    def list_active_prs(self, *, expand: str | None = None) -> list[PullRequest]:
        """Return all active pull requests in this project as a list."""
        return list(self.iter_active_prs(expand=expand))

    def list_pull_requests(
        self,
        status: PullRequestStatus | None = None,
        *,
        criteria: PullRequestSearchCriteria | None = None,
        expand: str | None = None,
    ) -> list[PullRequest]:
        """Return all pull requests matching the given criteria as a list."""
        return list(
            self.iter_pull_requests(status=status, criteria=criteria, expand=expand)
        )

    def list_work_items(self, query: str) -> list[WorkItem]:
        """Return all work items matching a WIQL query as a list."""
        return list(self.iter_work_items(query))

    def list_builds(
        self,
        *,
        definition_id: int | None = None,
        status_filter: BuildStatus | None = None,
        branch_name: str | None = None,
        top: int | None = None,
    ) -> list[Build]:
        """Return all builds matching the given criteria as a list."""
        return list(
            self.iter_builds(
                definition_id=definition_id,
                status_filter=status_filter,
                branch_name=branch_name,
                top=top,
            )
        )

    def list_pipeline_definitions(self) -> list[PipelineDefinitionInfo]:
        """Return all pipeline definitions as a list."""
        return list(self.iter_pipeline_definitions())

    def list_pipelines(self) -> list[Pipeline]:
        """Return all pipelines in this project as a list."""
        return list(self.iter_pipelines())

    def list_pending_approvals(self) -> list[PipelineApproval]:
        """Return all pending approvals in this project as a list."""
        return list(self.iter_pending_approvals())

    def list_variable_groups(self) -> list[VariableGroup]:
        """Return all variable groups in this project as a list."""
        return list(self.iter_variable_groups())

    def list_team_sprint_iterations(
        self,
        team_name: str,
        *,
        timeframe_filter: SprintIterationTimeframe | None = None,
    ) -> list[SprintIterationInfo]:
        """Return all team sprint iterations as a list."""
        return list(
            self.iter_team_sprint_iterations(
                team_name, timeframe_filter=timeframe_filter
            )
        )

    def list_teams(self) -> list[Team]:
        """Return all teams in this project as a list."""
        return list(self.iter_teams())
