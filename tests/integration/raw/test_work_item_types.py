"""Integration tests for work item type endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado import raw
from tests.integration.raw._support import console


def test_work_item_types_read(
    project_api_call: raw.ApiCall,
) -> None:
    """List work item types, categories, states, and fields."""
    console.print("\n=== WORK ITEM TYPES (read) ===")
    work_item_types = list(raw.iter_work_item_types(project_api_call))
    assert work_item_types == raw.list_work_item_types(project_api_call)
    categories = list(raw.iter_work_item_type_categories(project_api_call))
    assert categories == raw.list_work_item_type_categories(project_api_call)
    if work_item_types:
        wit = work_item_types[0]
        states = list(raw.iter_work_item_type_states(project_api_call, wit.name))
        assert states == raw.list_work_item_type_states(project_api_call, wit.name)
        fields = list(raw.iter_work_item_type_fields(project_api_call, wit.name))
        assert fields == raw.list_work_item_type_fields(project_api_call, wit.name)
