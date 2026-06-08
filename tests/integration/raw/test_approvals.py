"""Integration tests for sprint iteration and approval endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import random

from pyado import raw
from tests.integration.raw._support import _take, console


def test_sprint_iterations_read(
    project_api_call: raw.ApiCall,
    rng: random.Random,
) -> None:
    """Iterate sprint iterations with various timeframe filters."""
    console.print("\n=== SPRINT ITERATIONS (read) ===")

    timeframe_options: list[raw.SprintIterationTimeframe | None] = [
        None,
        raw.SprintIterationTimeframe.CURRENT,
    ]
    rng.shuffle(timeframe_options)

    for tf in timeframe_options[:3]:
        _take(raw.iter_sprint_iterations(project_api_call, tf), 5)


def test_approvals_read(
    project_api_call: raw.ApiCall,
    rng: random.Random,
) -> None:
    """List approvals with various status filters."""
    console.print("\n=== APPROVALS (read) ===")

    state_variants: list[raw.PipelineApprovalStatus | None] = [
        None,
        raw.PipelineApprovalStatus.PENDING,
        raw.PipelineApprovalStatus.APPROVED,
        raw.PipelineApprovalStatus.REJECTED,
        raw.PipelineApprovalStatus.CANCELED,
    ]
    rng.shuffle(state_variants)

    for state in state_variants[:3]:
        _take(raw.iter_approvals(project_api_call, state), 5)
    raw.list_approvals(project_api_call)
