"""ProjectBoards — the Boards section object for a project."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import date
from typing import TYPE_CHECKING, Any

from pyado import raw
from pyado.oop.boards import _work_item
from pyado.oop.boards.area import Area
from pyado.oop.boards.iteration import Iteration
from pyado.oop.boards.team import Team
from pyado.oop.boards.work_item import WorkItem
from pyado.oop.boards.work_item_type import WorkItemType
from pyado.raw import (
    ClassificationNodeAttributes,
    ClassificationNodeRequest,
    ClassificationNodeUrlType,
    SprintIterationId,
    SprintIterationInfo,
    SprintIterationTimeframe,
    TeamFieldValue,
    TextFormat,
    WorkItemBatchRequest,
    WorkItemExpand,
    WorkItemField,
    WorkItemId,
    WorkItemQuery,
    WorkItemQueryExpand,
    WorkItemRelation,
    WorkItemTypeCategoryInfo,
)

if TYPE_CHECKING:
    from pyado.oop.project import Project


class ProjectBoards:
    """The Boards section of a project.

    Accessed via ``project.boards``.  Exposes all work-item, iteration, area,
    team, and query operations that belong to the ADO Boards section.

    Attributes:
        _project: The owning Project.
    """

    def __init__(self, project: "Project") -> None:
        """Construct a ProjectBoards section.

        Args:
            project: The Project this section belongs to.
        """
        self._project = project

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
        wi_api_call = raw.get_work_item_api_call(self._project.api_call, work_item_id)
        expand = WorkItemExpand.RELATIONS
        info = raw.get_work_item(wi_api_call, expand=expand)
        return WorkItem(self._project, wi_api_call, info, expand)

    def iter_work_items(self, query: str) -> Iterator[WorkItem]:
        """Iterate over work items matching a WIQL query.

        Args:
            query: WIQL query string.  The ``SELECT`` list determines which
                fields are returned; use ``SELECT [System.Id]`` as a minimum.

        Yields:
            WorkItem for each work item returned by the query.
        """
        refs = raw.post_wiql(self._project.api_call, query)
        ids = [ref.id for ref in refs]
        for info in _work_item.iter_work_item_details(self._project.api_call, ids):
            wi_api_call = raw.get_work_item_api_call(self._project.api_call, info.id)
            yield WorkItem(self._project, wi_api_call, info, WorkItemExpand.RELATIONS)

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
            self._project.api_call,
            all_fields,
            relations,
            multiline_fields_format=multiline_fields_format,
        )
        wi_api_call = raw.get_work_item_api_call(self._project.api_call, created.id)
        expand = WorkItemExpand.RELATIONS
        info = raw.get_work_item(wi_api_call, expand=expand)
        return WorkItem(self._project, wi_api_call, info, expand)

    def get_work_items(
        self,
        ids: list[WorkItemId],
        *,
        expand: WorkItemExpand | None = WorkItemExpand.RELATIONS,
    ) -> list[WorkItem]:
        """Fetch multiple work items in a single API call.

        Prefer this over repeated :meth:`get_work_item` calls when you
        already have a list of IDs (e.g. from
        :meth:`~pyado.oop.pipelines.build.Build.iter_work_item_ids`).

        Args:
            ids: List of numeric work item IDs to fetch.
            expand: Expand mode controlling which extra data ADO includes
                (default: ``WorkItemExpand.RELATIONS``).  Pass ``None`` to
                fetch fields only.

        Returns:
            List of WorkItem objects, in the same order as *ids*.
        """
        infos = raw.post_work_items_batch(
            self._project.api_call, WorkItemBatchRequest(ids=ids, expand=expand)
        )
        result: list[WorkItem] = []
        for info in infos:
            wi_api_call = raw.get_work_item_api_call(self._project.api_call, info.id)
            result.append(WorkItem(self._project, wi_api_call, info, expand))
        return result

    def list_work_items(self, query: str) -> list[WorkItem]:
        """Return all work items matching a WIQL query as a list."""
        return list(self.iter_work_items(query))

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
        return raw.get_query_tree(self._project.api_call, depth=depth, expand=expand)

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
            self._project.api_call, folder_id, depth=depth, expand=expand
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
        info = raw.get_classification_node(
            self._project.api_call,
            path,
            node_type=ClassificationNodeUrlType.ITERATIONS,
            depth=depth,
        )
        return Iteration(self._project, info)

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
            self._project.api_call,
            ClassificationNodeRequest(name=name, attributes=attrs),
            parent_path,
            node_type=ClassificationNodeUrlType.ITERATIONS,
        )
        return Iteration(self._project, node)

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
            self._project._service.oop_api.make_team_api_call(  # noqa: SLF001
                self._project.name, team_name
            ),
            timeframe_filter=timeframe_filter,
        )

    def list_team_sprint_iterations(
        self,
        team_name: str,
        *,
        timeframe_filter: SprintIterationTimeframe | None = None,
    ) -> list[SprintIterationInfo]:
        """Return sprint iterations for a team as a list."""
        return list(
            self.iter_team_sprint_iterations(
                team_name, timeframe_filter=timeframe_filter
            )
        )

    def add_team_iteration(
        self,
        team_name: str,
        iteration_id: SprintIterationId,
    ) -> None:
        """Assign an existing iteration node to a team.

        Args:
            team_name: Name of the team within this project.
            iteration_id: UUID of the iteration classification node to assign.
        """
        raw.add_team_iteration(
            self._project._service.oop_api.make_team_api_call(  # noqa: SLF001
                self._project.name, team_name
            ),
            iteration_id,
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
        info = raw.get_classification_node(
            self._project.api_call,
            path,
            node_type=ClassificationNodeUrlType.AREAS,
            depth=depth,
        )
        return Area(self._project, info)

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
            self._project.api_call,
            ClassificationNodeRequest(name=name),
            parent_path,
            node_type=ClassificationNodeUrlType.AREAS,
        )
        return Area(self._project, node)

    def get_team_field_values(self, team_name: str) -> list[TeamFieldValue]:
        """Return the area-path field configuration for a team.

        Args:
            team_name: Name of the team within this project.

        Returns:
            List of TeamFieldValue entries describing the team's allowed
            area paths.
        """
        return raw.get_team_field_values(
            self._project._service.oop_api.make_team_api_call(  # noqa: SLF001
                self._project.name, team_name
            )
        )

    # ------------------------------------------------------------------
    # Teams
    # ------------------------------------------------------------------

    def iter_teams(self) -> Iterator[Team]:
        """Iterate over all teams in this project.

        Yields:
            Team for each team in the project.
        """
        for info in raw.iter_teams(self._project.org.api_call, self._project.name):
            yield Team(
                self._project,
                info,
                self._project._service,  # noqa: SLF001
            )

    def get_team(self, name: str) -> Team:
        """Return a specific team by name.

        Args:
            name: Team name (case-sensitive).

        Returns:
            Team wrapping the requested team.
        """
        info = raw.get_team(self._project.org.api_call, self._project.name, name)
        return Team(self._project, info, self._project._service)  # noqa: SLF001

    def get_team_by_id(self, team_id: str) -> Team:
        """Return a specific team by UUID string.

        Args:
            team_id: Team UUID string.

        Returns:
            Team wrapping the requested team.
        """
        info = raw.get_team(self._project.org.api_call, self._project.name, team_id)
        return Team(self._project, info, self._project._service)  # noqa: SLF001

    def list_teams(self) -> list[Team]:
        """Return all teams in the project as a list."""
        return list(self.iter_teams())

    # ------------------------------------------------------------------
    # Work item types
    # ------------------------------------------------------------------

    def iter_work_item_types(self) -> Iterator[WorkItemType]:
        """Iterate over all work item type definitions in this project.

        Yields:
            WorkItemType for each work item type definition.
        """
        for info in raw.iter_work_item_types(self._project.api_call):
            yield WorkItemType(self._project, info)

    def list_work_item_types(self) -> list[WorkItemType]:
        """Return all work item type definitions in this project as a list."""
        return list(self.iter_work_item_types())

    def get_work_item_type(self, name: str) -> WorkItemType:
        """Return a specific work item type by display name.

        Args:
            name: Work item type display name (e.g. ``"Bug"``).

        Returns:
            WorkItemType wrapping the requested work item type.

        Raises:
            KeyError: If no work item type with the given name exists.
        """
        for wit in self.iter_work_item_types():
            if wit.name == name:
                return wit
        raise KeyError(name)

    def iter_work_item_type_categories(self) -> Iterator[WorkItemTypeCategoryInfo]:
        """Iterate over work item type category definitions in this project.

        Yields:
            WorkItemTypeCategoryInfo for each category.
        """
        yield from raw.iter_work_item_type_categories(self._project.api_call)

    def list_work_item_type_categories(self) -> list[WorkItemTypeCategoryInfo]:
        """Return all work item type category definitions as a list."""
        return list(self.iter_work_item_type_categories())
