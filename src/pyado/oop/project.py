"""OOP wrapper for Azure DevOps project resources.

Provides the :class:`Project` class, which wraps a single ADO project and
exposes its operations as methods rather than free functions.
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import Any

from pyado import high, raw
from pyado.oop.build import Build
from pyado.oop.pipeline import Pipeline
from pyado.oop.repository import Repository
from pyado.oop.work_item import WorkItem
from pyado.raw import (
    ApiCall,
    BuildStatus,
    PipelineApproval,
    PipelineDefinitionInfo,
    ProjectId,
    ProjectInfo,
    WorkItemField,
    WorkItemId,
    WorkItemRelation,
)

__all__ = ["Project"]


class Project:
    """An Azure DevOps project resource.

    Wraps a single ADO project and exposes its operations as instance methods.
    Instances are normally obtained from :meth:`Client.get_project` or
    :meth:`Client.iter_projects`.

    Attributes:
        _api_call: Project-level API call used by all operations.
        _info: The project data returned from the API at construction time.
    """

    def __init__(self, project_api_call: ApiCall, info: ProjectInfo) -> None:
        """Construct a Project wrapper.

        Args:
            project_api_call: Project-level ADO API call (URL points at
                ``https://dev.azure.com/{org}/{project}/_apis``).
            info: Project data as returned from the API.
        """
        self._api_call = project_api_call
        self._info = info

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_info(self) -> ProjectInfo:
        """Return the project data fetched at construction time.

        Returns:
            ProjectInfo snapshot captured when this object was created.
        """
        return self._info

    def get_id(self) -> ProjectId:
        """Return the project UUID.

        Returns:
            UUID of the project.
        """
        return self._info.id

    def get_name(self) -> str:
        """Return the project name.

        Returns:
            String name of the project.
        """
        return self._info.name

    # ------------------------------------------------------------------
    # Repositories
    # ------------------------------------------------------------------

    def iter_repositories(self) -> Iterator[Repository]:
        """Iterate over all repositories in the project.

        Yields:
            Repository for each repository in the project.
        """
        for info in raw.iter_repository_details(self._api_call):
            repo_api_call = raw.get_repository_api_call(self._api_call, info.id)
            yield Repository(self._api_call, repo_api_call, info)

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
            info = repo.get_info()
            if info.name == name_or_id or str(info.id) == name_or_id:
                return repo
        err_msg = f"Repository {name_or_id!r} not found in project {self._info.name!r}"
        raise ValueError(err_msg)

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
        info = raw.get_work_item(wi_api_call, expand_relations=True)
        return WorkItem(wi_api_call, self._api_call, info)

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
            yield WorkItem(wi_api_call, self._api_call, info)

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
        return WorkItem(wi_api_call, self._api_call, info)

    # ------------------------------------------------------------------
    # Builds
    # ------------------------------------------------------------------

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
        for info in raw.iter_builds(
            self._api_call,
            status_filter=status_filter,
        ):
            build_api_call = raw.get_build_api_call(self._api_call, info.id)
            yield Build(build_api_call, info)

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
        return Build(build_api_call, info)

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

        Yields:
            Pipeline for each pipeline definition.
        """
        for info in raw.iter_pipelines(self._api_call):
            yield Pipeline(self._api_call, info)

    def get_pipeline(self, pipeline_id: int) -> Pipeline:
        """Return a wrapper for a specific Pipelines v2 definition.

        Args:
            pipeline_id: Numeric ID of the pipeline.

        Returns:
            Pipeline wrapping the requested definition.
        """
        info = raw.get_pipeline(self._api_call, pipeline_id)
        return Pipeline(self._api_call, info)

    def iter_pending_approvals(self) -> Iterator[PipelineApproval]:
        """Iterate over pending pipeline approvals in the project.

        Yields:
            PipelineApproval for each pending approval gate.
        """
        yield from high.iter_pending_approvals(self._api_call)
