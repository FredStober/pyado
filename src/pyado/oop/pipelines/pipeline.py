"""OOP wrapper for Azure DevOps pipeline resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from pyado import raw
from pyado.oop.pipelines import _build
from pyado.raw import (
    ApiCall,
    BuildStatus,
    PipelineApproval,
    PipelineApprovalStatus,
    PipelineInfo,
    PipelineResourcePermissions,
    PipelineResourceType,
    PipelineRunInfo,
    PipelineRunRequest,
    PipelineRunResult,
    PipelineRunState,
    VariableInfo,
)

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.pipelines.build import Build
    from pyado.oop.project import Project

__all__ = ["Pipeline", "PipelineRun"]


class PipelineRun:
    """A single Pipelines v2 run.

    **ADO concept:** a pipeline run is a single execution of a pipeline, as
    exposed by the newer Pipelines v2 API at
    ``pipelines/{pipelineId}/runs/{runId}`` (docs:
    `pipelines/Runs <https://learn.microsoft.com/rest/api/azure/devops/pipelines/runs>`_).
    The numeric ``runId`` is identical to the Build API's ``buildId`` — the
    same execution is accessible via both surfaces.

    **Why it exists as a separate class from Build:** the Pipelines v2 API
    exposes data that the Build API does not: ``finalYaml`` (the compiled
    YAML after template expansion), ``templateParameters``, and a cleaner
    state/result enum pair (``PipelineRunState`` + ``PipelineRunResult``).
    It is also the *natural companion to Pipeline* — obtaining a run through
    ``pipeline.iter_runs()`` returns a ``PipelineRun``, while navigating via
    ``project.pipelines.iter_builds()`` returns a
    :class:`~pyado.oop.pipelines.build.Build`.

    **ADO constraint:** the Pipelines v2 API has no cancel endpoint.
    Cancellation is routed through the Build API (``PATCH build/builds/{id}``
    with ``{status: "cancelling"}``); pyado does this automatically in
    :meth:`cancel`.

    Wraps a :class:`~pyado.raw.PipelineRunInfo` and holds a back-reference
    to the owning :class:`Pipeline`.  Instances are obtained from
    :meth:`Pipeline.iter_runs`, :meth:`Pipeline.get_run`, or
    :meth:`Pipeline.start_run`.

    Attributes:
        _pipeline: The Pipeline this run belongs to.
        _info: Run data returned from the API at construction time.
    """

    def __init__(self, pipeline: "Pipeline", info: PipelineRunInfo) -> None:
        """Construct a PipelineRun wrapper.

        Args:
            pipeline: The Pipeline that owns this run.
            info: Run data as returned from the API.
        """
        self._pipeline = pipeline
        self._run_id = info.id
        self._info: PipelineRunInfo | None = info

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def info(self) -> PipelineRunInfo:
        """Run data captured at construction time."""
        if self._info is None:
            self._info = raw.get_pipeline_run(
                self._pipeline.project.api_call,
                self._pipeline.id,
                self._run_id,
            )
        return self._info

    @property
    def id(self) -> int:
        """Numeric run ID."""
        return self._run_id

    @property
    def status(self) -> PipelineRunState:
        """Current run state (e.g. ``"inProgress"``, ``"completed"``)."""
        return self.info.state

    @property
    def result(self) -> PipelineRunResult | None:
        """Run result once completed (e.g. ``"succeeded"``, ``"failed"``).

        ``None`` while the run is still in progress.
        """
        return self.info.result

    @property
    def pipeline(self) -> "Pipeline":
        """Pipeline this run belongs to — zero-cost."""
        return self._pipeline

    @property
    def org(self) -> "Organization":
        """Organisation this run belongs to — zero-cost."""
        return self._pipeline.org

    @property
    def project(self) -> "Project":
        """Project this run belongs to — zero-cost."""
        return self._pipeline.project

    @property
    def api_call(self) -> ApiCall:
        """Project-level API call for direct use with pyado.raw pipeline functions.

        ADO's Pipelines REST API has no run-scoped base URL — every run
        endpoint is project-scoped (``{org}/{project}/_apis/pipelines/…``),
        with ``pipelineId`` and ``runId`` passed as additional path segments
        by the raw functions themselves.  Returning the project-level call is
        therefore correct and consistent with the raw layer.
        """
        return self._pipeline.project.api_call

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Discard cached run info.

        The next access to :attr:`info` re-fetches from the API.
        """
        self._info = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def cancel(self) -> "PipelineRun":
        """Request cancellation of this in-progress run.

        Updates the wrapper's cached info to reflect the cancelling state.

        Returns ``self`` (rather than a raw info object) so that callers can
        chain further method calls on the same wrapper.  This differs from
        :meth:`Build.cancel() <pyado.oop.pipelines.build.Build.cancel>`,
        which returns ``BuildDetails`` for the classic Build API — the two
        methods target different ADO endpoints and the return-type difference
        is intentional.

        Returns:
            ``self`` with state ``"canceling"``; transitions to
            ``"completed"`` with result ``"canceled"`` once the agent
            acknowledges.
        """
        self._info = self._pipeline.cancel_run(self._run_id)
        return self

    # ------------------------------------------------------------------
    # Approvals
    # ------------------------------------------------------------------

    def iter_approvals(
        self,
        state: PipelineApprovalStatus | None = None,
    ) -> Iterator[PipelineApproval]:
        """Iterate over environment approvals for this run.

        Scoped to this run's ID, so only approvals that belong to this
        specific run are returned.

        Args:
            state: Optional status filter (e.g.
                ``PipelineApprovalStatus.PENDING``).  When ``None``, approvals
                in all states are returned.

        Yields:
            PipelineApproval for each matching approval on this run.
        """
        yield from raw.iter_approvals(
            self._pipeline.project.api_call,
            state=state,
            pipeline_run_ids=[self._run_id],
        )

    def list_approvals(
        self,
        state: PipelineApprovalStatus | None = None,
    ) -> list[PipelineApproval]:
        """Return environment approvals for this run as a list."""
        return list(self.iter_approvals(state=state))


class Pipeline:
    """An Azure DevOps pipeline resource (Pipelines v2).

    **ADO concept:** a pipeline is the *definition* of a CI/CD process,
    stored as a YAML file in a repository (or as a classic GUI definition).
    It is exposed by two APIs:

    * **Pipelines v2 API** — ``pipelines/{id}`` (docs:
      `pipelines/Pipelines <https://learn.microsoft.com/rest/api/azure/devops/pipelines/pipelines>`_).
      This class uses this surface.
    * **Build API** — ``build/definitions/{id}`` — older surface with more
      fields (triggers, retention, variables), represented as
      :class:`~pyado.raw.PipelineDefinitionInfo`.

    The numeric ``id`` is the same in both APIs.

    **Why it exists:** ``Pipeline`` is the factory for
    :class:`PipelineRun` objects and owns resource-permission management
    (:meth:`authorize_resource`).  Caching through the service guarantees
    that ``build.pipeline is other_build.pipeline`` when both were produced
    by the same definition — even if the two ``Build`` objects were obtained
    from different call paths.  The ``id`` and ``name`` are always known
    (embedded in :class:`~pyado.raw.BuildDetails`), so a ``Pipeline``
    wrapper is available with zero API calls as soon as a ``Build`` is
    fetched; the full :attr:`info` is loaded lazily on first access.

    Wraps a single ADO pipeline and exposes its operations as instance
    methods.  Instances are obtained from
    :meth:`ProjectPipelines.get_pipeline`,
    :meth:`ProjectPipelines.iter_pipelines`, or as a zero-cost back-reference
    via :attr:`Build.pipeline`.

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

    def iter_runs(self, *, top: int | None = None) -> Iterator[PipelineRun]:
        """Iterate over all runs of the pipeline.

        Args:
            top: Maximum number of runs to return.  When ``None`` the API
                default is used.

        Yields:
            PipelineRun for each run, in API-returned order (newest first).
        """
        for info in raw.iter_pipeline_runs(self._project.api_call, self._id, top=top):
            yield PipelineRun(self, info)

    def iter_builds(
        self,
        *,
        status_filter: BuildStatus | None = None,
        branch_name: str | None = None,
        top: int | None = None,
    ) -> "Iterator[Build]":
        """Iterate over builds for this pipeline via the Build API.

        Provides richer filtering than :meth:`iter_runs` (status, branch, top).
        Delegates to :func:`~pyado.raw.iter_builds` with this pipeline's
        definition ID pre-filled.

        Args:
            status_filter: Filter by build status (e.g. ``BuildStatus.COMPLETED``).
            branch_name: Filter by source branch ref name
                (e.g. ``"refs/heads/main"``).
            top: Maximum number of builds to return.

        Yields:
            :class:`~pyado.oop.pipelines.build.Build` for each matching build.
        """
        yield from self._project.pipelines.iter_builds(
            definition_id=self._id,
            status_filter=status_filter,
            branch_name=branch_name,
            top=top,
        )

    def get_run(self, run_id: int) -> PipelineRun:
        """Return a wrapper for a single pipeline run.

        Args:
            run_id: Numeric ID of the pipeline run.

        Returns:
            PipelineRun wrapping the requested run.
        """
        info = raw.get_pipeline_run(self._project.api_call, self._id, run_id)
        return PipelineRun(self, info)

    def start_run(
        self,
        *,
        resources: dict[str, Any] | None = None,
        variables: dict[str, VariableInfo] | None = None,
        template_parameters: dict[str, str] | None = None,
        stages_to_skip: list[str] | None = None,
    ) -> PipelineRun:
        """Trigger a new run of the pipeline.

        Args:
            resources: Optional pipeline resources override dict.
            variables: Optional pipeline variable overrides dict.
            template_parameters: Optional template parameter overrides.
            stages_to_skip: List of stage names to skip during the run.

        Returns:
            PipelineRun wrapping the newly triggered run.
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
        info = raw.post_pipeline_run(self._project.api_call, self._id, request)
        return PipelineRun(self, info)

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
        return raw.patch_pipeline_permission(
            self._project.api_call,
            resource_type,
            resource_id,
            self._id,
            authorized=authorized,
        )

    def cancel_run(self, run_id: int) -> PipelineRunInfo:
        """Request cancellation of an in-progress pipeline run.

        Args:
            run_id: Numeric ID of the run to cancel (same as the build ID
                for Pipelines v2 runs).

        Returns:
            PipelineRunInfo with state ``"canceling"``; transitions to
            ``"completed"`` with result ``"canceled"`` once the agent
            acknowledges.
        """
        return _build.cancel_pipeline_run(self._project.api_call, self._id, run_id)

    def get_latest_run(self) -> PipelineRun | None:
        """Return the most recent pipeline run, or ``None`` if none exist.

        Returns:
            PipelineRun for the newest run, or ``None``.
        """
        info = next(
            iter(raw.iter_pipeline_runs(self._project.api_call, self._id)), None
        )
        return PipelineRun(self, info) if info is not None else None

    def list_runs(self, *, top: int | None = None) -> list[PipelineRun]:
        """Return all runs for this pipeline as a list."""
        return list(self.iter_runs(top=top))

    def list_builds(
        self,
        *,
        status_filter: "BuildStatus | None" = None,
        branch_name: str | None = None,
        top: int | None = None,
    ) -> "list[Build]":
        """Return all builds for this pipeline as a list."""
        return list(
            self.iter_builds(
                status_filter=status_filter, branch_name=branch_name, top=top
            )
        )
