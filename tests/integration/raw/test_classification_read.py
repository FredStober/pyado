"""Integration tests for classification node and query tree read endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado import raw
from tests.integration.raw._support import console


def test_query_classification_read(
    project_api_call: raw.ApiCall,
) -> None:
    """Fetch the query tree and classification nodes for iterations and areas."""
    console.print("\n=== QUERY TREE & CLASSIFICATION NODES (read) ===")
    raw.get_query_tree(project_api_call)
    query_tree = raw.get_query_tree(project_api_call)
    if query_tree:
        raw.get_query_folder(project_api_call, query_tree[0].id)

    raw.get_classification_node(
        project_api_call, node_type=raw.ClassificationNodeUrlType.ITERATIONS, depth=2
    )
    raw.get_classification_node(
        project_api_call, node_type=raw.ClassificationNodeUrlType.AREAS, depth=2
    )
