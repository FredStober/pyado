"""OOP wrapper for Azure DevOps pipeline resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from pyado import raw
from pyado.raw import (
    ApiCall,
    PipelineInfo,
    PipelineResourcePermissions,
    PipelineResourceType,
    PipelineRunInfo,
    PipelineRunRequest,
)

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project

__all__ = ["Pipeline"]


class Pipeline:
    """An Azure DevOps pipeline resource (Pipelines v2).

    Wraps a single ADO pipeline and exposes its operations as instance
    methods.  Instances are obtained from :meth:`Project.get_pipeline`,
    :meth:`Project.iter_pipelines`, or as a zero-cost back-reference via
    :attr:`Build.pipeline`.

    The ``id`` and ``name`` are always known at construction.  The full
    :attr:`info` payload is loaded lazily and cached; call :meth:`refresh` to
    discard it so the next access re-fetches from the API.

    Attributes:
        _project: The Project this pipeline belongs to.
        _id: Numeric pipeline ID.
        _name: Pipeline name.
        _info: Cached pipeline data; ``None`` until first lazy fetch.
    """

    def __init__(
        self,
        project: "Project",
        pipeline_id: int,
        name: str,
        info: PipelineInfo | None = None,
    ) -> None:
        """Construct a Pipeline wrapper.

        Args:
            project: The Project that owns this pipeline.
            pipeline_id: Numeric pipeline ID.
            name: Pipeline name.
            info: Pre-fetched pipeline data, or ``None`` to load lazily.
        """
        self._project = project
        self._id = pipeline_id
        self._name = name
        self._info = info

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> int:
        """Numeric pipeline ID — always known, no API call."""
        return self._id

    @property
    def name(self) -> str:
        """Pipeline name — always known, no API call."""
        return self._name

    @property
    def info(self) -> PipelineInfo:
        """Full pipeline data (lazy-fetched on first access if not supplied)."""
        if self._info is None:
            self._info = raw.get_pipeline(self._project.api_call, self._id)
        return self._info

    @property
    def api_call(self) -> ApiCall:
        """Project-level API call for direct use with pyado.raw functions.

        ADO pipelines are project-scoped, so the pipeline-level API call is
        the same as the owning project's API call.
        """
        return self._project.api_call

    @property
    def project(self) -> "Project":
        """Project this pipeline belongs to — zero-cost."""
        return self._project

    @property
    def org(self) -> "Organization":
        """Organisation this pipeline belongs to — zero-cost."""
        return self._project.org

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Discard cached pipeline info.

        The next access to :attr:`info` re-fetches from the API.
        """
        self._info = None

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    def iter_runs(self) -> Iterator[PipelineRunInfo]:
        """Iterate over all runs of the pipeline.

        Yields:
            PipelineRunInfo for each run, in API-returned order.
        """
        yield from raw.iter_pipeline_runs(self._project.api_call, self._id)

    def get_run(self, run_id: int) -> PipelineRunInfo:
        """Return the details of a single pipeline run.

        Args:
            run_id: Numeric ID of the pipeline run.

        Returns:
            PipelineRunInfo for the requested run.
        """
        return raw.get_pipeline_run(self._project.api_call, self._id, run_id)

    def start_run(
        self,
        *,
        resources: dict[str, Any] | None = None,
        variables: dict[str, Any] | None = None,
        template_parameters: dict[str, str] | None = None,
        stages_to_skip: list[str] | None = None,
    ) -> PipelineRunInfo:
        """Trigger a new run of the pipeline.

        Args:
            resources: Optional pipeline resources override dict.
            variables: Optional pipeline variable overrides dict.
            template_parameters: Optional template parameter overrides.
            stages_to_skip: List of stage names to skip during the run.

        Returns:
            PipelineRunInfo for the newly triggered run.
        """
        request: PipelineRunRequest | None = None
        if any(
            arg is not None
            for arg in (resources, variables, template_parameters, stages_to_skip)
        ):
            request = PipelineRunRequest(
                resources=resources,
                variables=variables,
                template_parameters=template_parameters,
                stages_to_skip=stages_to_skip,
            )
        return raw.post_pipeline_run(self._project.api_call, self._id, request)

    # ------------------------------------------------------------------
    # Resource permissions
    # ------------------------------------------------------------------

    def authorize_resource(
        self,
        resource_type: PipelineResourceType,
        resource_id: str,
        *,
        authorized: bool = True,
    ) -> PipelineResourcePermissions:
        """Authorize (or de-authorize) a resource for this pipeline.

        Note: ADO pipeline permission grants are **additive** — this call can
        never remove an authorization that was granted by another pipeline or
        via the portal.  Read the current permissions from ADO before deciding
        to call this method.

        Args:
            resource_type: The type of resource to authorize.
            resource_id: String ID of the resource.
            authorized: ``True`` to grant access (default); ``False`` to
                revoke.

        Returns:
            PipelineResourcePermissions reflecting the updated state.
        """
        return raw.post_pipeline_permission(
            self._project.api_call,
            resource_type,
            resource_id,
            self._id,
            authorized=authorized,
        )

    def get_latest_run(self) -> PipelineRunInfo | None:
        """Return the most recent pipeline run, or ``None`` if none exist.

        Returns:
            PipelineRunInfo for the newest run, or ``None``.
        """
        return next(
            iter(raw.iter_pipeline_runs(self._project.api_call, self._id)), None
        )
