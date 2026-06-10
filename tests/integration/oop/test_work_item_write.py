"""Integration tests for WorkItem OOP class (write)."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import uuid

from pyado.oop import Build, Project, PullRequest, Repository, WorkItem
from pyado.raw import WorkItemRelationType, WorkItemTypeName
from tests.integration.raw._support import _take


def _exercise_wi_links(
    wi: WorkItem,
    wi2: WorkItem | None,
    build: Build | None,
    repo: Repository | None,
    existing_pr: PullRequest | None,
) -> None:
    """Exercise link/relation write methods on a work item."""
    if wi2:
        wi.add_link(wi2, WorkItemRelationType.RELATED)
        list(wi.iter_linked_work_items())
        list(wi.iter_relations())
        wi.remove_work_item_links(wi2)

    if build:
        wi.link_build(build)

    if repo and repo.default_branch:
        head_commits = list(repo.iter_commits(top=1))
        if head_commits:
            wi.link_commit(repo, head_commits[0].sha)
            list(wi.iter_artifact_links())
            artifact_links = list(wi.iter_artifact_links())
            if artifact_links:
                wi.remove_link(artifact_links[0])

    if existing_pr:
        wi.link_pull_request(existing_pr)


def test_write_work_item(
    proj: Project,
    repo: Repository | None,
    build: Build | None,
    existing_pr: PullRequest | None,
) -> None:
    """Create a work item, exercise all write methods, then delete it."""
    tag_name = f"oop-smoke-{uuid.uuid4().hex[:8]}"

    wi: WorkItem | None = proj.boards.create_work_item(
        WorkItemTypeName.TASK,
        {
            "System.Title": f"[oop-smoke] OOP smoke test task {uuid.uuid4().hex[:6]}",
            "System.Description": "Created by smoke_test_oop.py — safe to delete.",
        },
    )
    if wi is None:
        return

    wi.update({"System.Title": (wi.title or "") + " (updated)"})
    wi.move(iteration_path=wi.iteration_path)
    wi.add_tag(tag_name)
    wi.list_tags()
    wi.remove_tag(tag_name)
    comment = wi.add_comment("<p>OOP smoke comment</p>")
    if comment:
        wi.update_comment(comment.id, "<p>updated</p>")
        wi.remove_comment(comment.id)
    attachment_ref = wi.add_attachment("smoke.txt", b"hello from oop smoke test")
    if attachment_ref is not None:
        wi.download_attachment(attachment_ref)
    _take(wi.iter_attachments(), 5)

    # Create a second WI to link to
    wi2: WorkItem | None = proj.boards.create_work_item(
        WorkItemTypeName.TASK,
        {"System.Title": f"[oop-smoke] Link target {uuid.uuid4().hex[:6]}"},
    )
    # create_child
    child_wi: WorkItem | None = wi.create_child(
        WorkItemTypeName.TASK, f"[oop-smoke] Child task {uuid.uuid4().hex[:6]}"
    )
    if child_wi:
        wi.list_child_ids()
        child_wi.delete()

    _exercise_wi_links(wi, wi2, build, repo, existing_pr)

    # Soft-delete the created WIs
    if wi2:
        wi2.delete()
    wi.delete()
    wi.restore()
    wi.delete()
