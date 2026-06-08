"""Integration tests for classification node write endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import contextlib
import random

from pyado import raw
from pyado.raw import ClassificationNodePatchRequest, ClassificationNodeRequest
from tests.integration.raw._support import console


def test_classification_write(
    project_api_call: raw.ApiCall,
    rng: random.Random,
) -> None:
    """Create, patch, and delete classification nodes for iterations and areas."""
    console.print("\n=== CLASSIFICATION NODES (write) ===")

    iter_name = f"smoke-iter-{rng.randint(10000, 99999)}"
    area_name = f"smoke-area-{rng.randint(10000, 99999)}"

    # Pre-cleanup: delete any leftover nodes from previous runs (e.g. if a prior
    # session created but never deleted them).  Ignore errors — the nodes may not
    # exist.
    for cn_name, cn_type in [
        (iter_name, raw.ClassificationNodeUrlType.ITERATIONS),
        (iter_name + "-patched", raw.ClassificationNodeUrlType.ITERATIONS),
        (area_name, raw.ClassificationNodeUrlType.AREAS),
        (area_name + "-patched", raw.ClassificationNodeUrlType.AREAS),
    ]:
        with contextlib.suppress(Exception):
            raw.delete_classification_node(project_api_call, cn_name, node_type=cn_type)

    # create_classification_node — iteration
    created_iter = raw.create_classification_node(
        project_api_call,
        ClassificationNodeRequest(name=iter_name),
        node_type=raw.ClassificationNodeUrlType.ITERATIONS,
    )
    if created_iter:
        raw.patch_classification_node(
            project_api_call,
            iter_name,
            ClassificationNodePatchRequest(name=iter_name + "-patched"),
            node_type=raw.ClassificationNodeUrlType.ITERATIONS,
        )
        raw.delete_classification_node(
            project_api_call,
            iter_name + "-patched",
            node_type=raw.ClassificationNodeUrlType.ITERATIONS,
        )

    # create_classification_node — area
    created_area = raw.create_classification_node(
        project_api_call,
        ClassificationNodeRequest(name=area_name),
        node_type=raw.ClassificationNodeUrlType.AREAS,
    )
    if created_area:
        raw.patch_classification_node(
            project_api_call,
            area_name,
            ClassificationNodePatchRequest(name=area_name + "-patched"),
            node_type=raw.ClassificationNodeUrlType.AREAS,
        )
        raw.delete_classification_node(
            project_api_call,
            area_name + "-patched",
            node_type=raw.ClassificationNodeUrlType.AREAS,
        )
