"""Integration tests for work item read endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import random

from pyado import raw
from tests.integration.raw._support import _take, console


def test_work_items_read(
    project_api_call: raw.ApiCall,
    rng: random.Random,
) -> None:
    """Run WIQL queries, batch fetch, and read a single work item with comments."""
    console.print("\n=== WORK ITEMS (read) ===")

    wiql_queries = [
        (
            "SELECT [System.Id] FROM WorkItems"
            " WHERE [System.WorkItemType] = 'Task'"
            " ORDER BY [System.ChangedDate] DESC"
        ),
        (
            "SELECT [System.Id] FROM WorkItems"
            " WHERE [System.State] = 'Active'"
            " ORDER BY [System.ChangedDate] DESC"
        ),
        "SELECT [System.Id] FROM WorkItems ORDER BY [System.ChangedDate] DESC",
        (
            "SELECT [System.Id] FROM WorkItems"
            " WHERE [System.WorkItemType] = 'Bug'"
            " ORDER BY [System.ChangedDate] DESC"
        ),
        (
            "SELECT [System.Id] FROM WorkItems"
            " WHERE [System.WorkItemType] IN ('Task', 'Bug', 'User Story')"
            " ORDER BY [System.Id] DESC"
        ),
    ]
    rng.shuffle(wiql_queries)
    wi_refs = raw.post_wiql(project_api_call, wiql_queries[0])
    raw.post_wiql(project_api_call, wiql_queries[1])

    wi_ids = [ref.id for ref in (wi_refs or [])[:10]]
    if wi_ids:
        console.print(f"  work item ids: {wi_ids}")
    if not wi_ids:
        return

    fields_variants: list[list[str] | None] = [
        None,
        [raw.WorkItemFieldName.ID, raw.WorkItemFieldName.TITLE],
        [
            raw.WorkItemFieldName.ID,
            raw.WorkItemFieldName.TITLE,
            raw.WorkItemFieldName.STATE,
            raw.WorkItemFieldName.WORK_ITEM_TYPE,
        ],
        [
            raw.WorkItemFieldName.ID,
            raw.WorkItemFieldName.TITLE,
            raw.WorkItemFieldName.DESCRIPTION,
            raw.WorkItemFieldName.ASSIGNED_TO,
        ],
    ]
    rng.shuffle(fields_variants)
    for fields in fields_variants[:3]:
        raw.post_work_items_batch(
            project_api_call,
            raw.WorkItemBatchRequest(
                ids=wi_ids[:5],
                fields=fields,
                expand=raw.WorkItemExpand.RELATIONS if fields is None else None,
            ),
        )

    wi_id = rng.choice(wi_ids)
    console.print(f"  selected work item: #{wi_id}")
    wi_api_call = raw.get_work_item_api_call(project_api_call, wi_id)
    for expand in rng.sample([raw.WorkItemExpand.RELATIONS, None], 2):
        raw.get_work_item(wi_api_call, expand=expand)

    _take(raw.list_work_item_comments(wi_api_call), 20)


def test_work_item_extras_read(
    project_api_call: raw.ApiCall,
    rng: random.Random,
) -> None:
    """Fetch work item revisions."""
    console.print("\n=== WORK ITEM EXTRAS (read) ===")
    wi_refs = raw.post_wiql(
        project_api_call,
        "SELECT [System.Id] FROM WorkItems ORDER BY [System.ChangedDate] DESC",
    )
    wi_ids = [ref.id for ref in (wi_refs or [])[:5]]
    if not wi_ids:
        return

    wi_id = rng.choice(wi_ids)
    wi_api_call = raw.get_work_item_api_call(project_api_call, wi_id)
    _take(raw.list_work_item_revisions(wi_api_call), 5)
