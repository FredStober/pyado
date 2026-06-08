"""Integration tests for WorkItem OOP class (read)."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado.oop import Project, WorkItem
from tests.integration.raw._support import _take, console


def test_work_item_read(proj: Project) -> None:
    """Exercise WorkItem read methods.

    Covers properties, comments, relations, attachments, and revisions.
    """
    console.print("\n=== WorkItem (read, existing) ===")
    wiql = (
        "SELECT [System.Id], [System.Title], [System.State] "
        "FROM WorkItems "
        "WHERE [System.TeamProject] = @project "
        "ORDER BY [System.Id] DESC"
    )
    wis = _take(proj.boards.iter_work_items(wiql), 1)
    if not wis:
        return

    wi: WorkItem = wis[0]
    proj.boards.get_work_item(wi.id)

    _ = wi.id
    _ = wi.title
    _ = wi.state
    _ = wi.type
    _ = wi.assigned_to
    _ = wi.area_path
    _ = wi.iteration_path
    wi.get_field("System.Title")
    _ = wi.info
    _ = wi.api_call
    _ = wi.project
    _ = wi.org
    wi.refresh()
    wi.list_tags()
    _take(wi.iter_comments(), 5)
    wi.list_comments()
    wi.get_parent()
    _take(wi.iter_linked_work_items(), 5)
    wi.list_linked_work_items()
    _take(wi.iter_children(), 5)
    wi.list_children()
    _take(wi.iter_relations(), 5)
    wi.list_relations()
    _take(wi.iter_artifact_links(), 5)
    wi.list_artifact_links()
    _take(wi.iter_attachments(), 5)
    wi.list_attachments()
    wi.get_child_ids()
    _take(wi.iter_revisions(), 3)
    wi.list_revisions()
    proj.boards.get_work_items([wi.id])
