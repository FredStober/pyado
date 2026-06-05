"""Smoke tests for sprint-iteration and approval endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import random

from pyado import raw
from pyado.raw.smoke_test._runner import _take, console, run


def _test_sprint_iterations_read(
    project_api_call: raw.ApiCall,
    rng: random.Random,
) -> None:
    console.print("\n=== SPRINT ITERATIONS (read) ===")

    timeframe_options: list[str | None] = [None, "current"]
    rng.shuffle(timeframe_options)

    for tf in timeframe_options[:3]:
        label = f"iter_sprint_iterations [timeframe={tf!r}]"
        run(
            label,
            lambda t=tf: _take(raw.iter_sprint_iterations(project_api_call, t), 5),
        )


def _test_approvals_read(
    project_api_call: raw.ApiCall,
    rng: random.Random,
) -> None:
    console.print("\n=== APPROVALS (read) ===")

    state_variants: list[raw.PipelineApprovalStatus | None] = [
        None,
        "pending",
        "approved",
        "rejected",
        "canceled",
    ]
    rng.shuffle(state_variants)

    for state in state_variants[:3]:
        run(
            f"iter_approvals [state={state!r}]",
            lambda s=state: _take(raw.iter_approvals(project_api_call, s), 5),
        )
    run(
        "list_approvals",
        lambda: raw.list_approvals(project_api_call),
    )
