"""OOP wrapper for Azure DevOps pipeline resources.

Provides the :class:`Pipeline` class, which wraps a single ADO pipeline
(Pipelines v2) and exposes its operations as methods rather than free
functions.
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import Any

from pyado import raw
from pyado.raw import (
    ApiCall,
    PipelineInfo,
    PipelineRunInfo,
    PipelineRunRequest,
)

__all__ = ["Pipeline"]


class Pipeline:
    """An Azure DevOps pipeline resource (Pipelines v2).

    Wraps a single ADO pipeline and exposes its operations as instance
    methods.  Instances are normally obtained from
    :meth:`Project.get_pipeline` or :meth:`Project.iter_pipelines`.

    Attributes:
        _project_api_call: Project-level API call used for run operations.
        _info: The pipeline data returned from the API at construction time.
    """

    def __init__(self, project_api_call: ApiCall, info: PipelineInfo) -> None:
        """Construct a Pipeline wrapper.

        Args:
            project_api_call: Project-level ADO API call.
            info: Pipeline data as returned from the API.
        """
        self._project_api_call = project_api_call
        self._info = info

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_info(self) -> PipelineInfo:
        """Return the pipeline data fetched at construction time.

        Returns:
            PipelineInfo snapshot captured when this object was created.
        """
        return self._info

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    def iter_runs(self) -> Iterator[PipelineRunInfo]:
        """Iterate over all runs of the pipeline.

        Yields:
            PipelineRunInfo for each run, in API-returned order.
        """
        yield from raw.iter_pipeline_runs(self._project_api_call, self._info.id)

    def get_run(self, run_id: int) -> PipelineRunInfo:
        """Return the details of a single pipeline run.

        Args:
            run_id: Numeric ID of the pipeline run.

        Returns:
            PipelineRunInfo for the requested run.
        """
        return raw.get_pipeline_run(self._project_api_call, self._info.id, run_id)

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
        return raw.post_pipeline_run(self._project_api_call, self._info.id, request)
