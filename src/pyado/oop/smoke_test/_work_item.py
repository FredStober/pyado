"""Smoke tests for WorkItem."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import uuid

from pyado.oop import Build, Project, PullRequest, Repository, WorkItem
from pyado.oop.smoke_test._runner import _skip, _take, console, run
from pyado.raw import WorkItemRelationType


def _test_work_item_read(proj: Project) -> WorkItem | None:
    console.print("\n=== WorkItem (read, existing) ===")
    wiql = (
        "SELECT [System.Id], [System.Title], [System.State] "
        "FROM WorkItems "
        "WHERE [System.TeamProject] = @project "
        "ORDER BY [System.Id] DESC"
    )
    wis = run(
        "proj.iter_work_items(wiql)", lambda: _take(proj.iter_work_items(wiql), 1)
    )
    if not wis:
        _skip("work item read tests", "no work items found")
        return None

    wi: WorkItem = wis[0]
    run("proj.get_work_item(id)", lambda wi_id=wi.id: proj.get_work_item(wi_id))

    run("wi.id", lambda: wi.id)
    run("wi.title", lambda: wi.title)
    run("wi.state", lambda: wi.state)
    run("wi.type", lambda: wi.type)
    run("wi.assigned_to", lambda: wi.assigned_to)
    run("wi.area_path", lambda: wi.area_path)
    run("wi.iteration_path", lambda: wi.iteration_path)
    run("wi.get_field('System.Title')", lambda: wi.get_field("System.Title"))
    run("wi.info", lambda: wi.info)
    run("wi.api_call", lambda: wi.api_call)
    run("wi.project (back-nav)", lambda: wi.project)
    run("wi.org (back-nav)", lambda: wi.org)
    run("wi.refresh()", wi.refresh)
    run("wi.list_tags()", wi.list_tags)
    run("wi.iter_comments()", lambda: _take(wi.iter_comments(), 5))
    run("wi.list_comments()", wi.list_comments)
    run("wi.get_parent()", wi.get_parent)
    run("wi.iter_linked_work_items()", lambda: _take(wi.iter_linked_work_items(), 5))
    run("wi.list_linked_work_items()", wi.list_linked_work_items)
    run(
        "wi.iter_children()",
        lambda: _take(wi.iter_children(), 5),
    )
    run("wi.list_children()", wi.list_children)
    run("wi.iter_relations()", lambda: _take(wi.iter_relations(), 5))
    run("wi.list_relations()", wi.list_relations)
    run("wi.iter_artifact_links()", lambda: _take(wi.iter_artifact_links(), 5))
    run("wi.list_artifact_links()", wi.list_artifact_links)
    run("wi.iter_attachments()", lambda: _take(wi.iter_attachments(), 5))
    run("wi.list_attachments()", wi.list_attachments)
    run("wi.get_child_ids()", wi.get_child_ids)
    run("wi.iter_revisions()", lambda: _take(wi.iter_revisions(), 3))
    run("wi.list_revisions()", wi.list_revisions)
    run("proj.get_work_items([id])", lambda: proj.get_work_items([wi.id]))
    return wi


def _exercise_wi_links(
    wi: WorkItem,
    wi2: WorkItem | None,
    build: Build | None,
    repo: Repository | None,
    existing_pr: "PullRequest | None",
) -> None:
    """Exercise link/relation write methods on a work item."""
    if wi2:
        run(
            "wi.add_link(RELATED → wi2)",
            lambda: wi.add_link(wi2, WorkItemRelationType.RELATED),
        )
        run("wi.iter_linked_work_items()", lambda: list(wi.iter_linked_work_items()))
        run("wi.iter_relations() after add_link", lambda: list(wi.iter_relations()))
        run("wi.remove_work_item_links(wi2)", lambda: wi.remove_work_item_links(wi2))

    if build:
        run("wi.link_build()", lambda: wi.link_build(build))

    if repo and repo.default_branch:
        head_commits = list(repo.iter_commits(top=1))
        if head_commits:
            run(
                "wi.link_commit()",
                lambda sha=head_commits[0].sha: wi.link_commit(repo, sha),
            )
            run(
                "wi.iter_artifact_links() after link",
                lambda: list(wi.iter_artifact_links()),
            )
            artifact_links = list(wi.iter_artifact_links())
            if artifact_links:
                run(
                    "wi.remove_link(artifact_link)",
                    lambda rel=artifact_links[0]: wi.remove_link(rel),
                )

    if existing_pr:
        run(
            "wi.link_pull_request(existing_pr)",
            lambda: wi.link_pull_request(existing_pr),
        )


def _test_write_work_item(
    proj: Project,
    repo: Repository | None,
    build: Build | None,
    existing_pr: "PullRequest | None" = None,
) -> WorkItem | None:
    """Create a test work item, exercise all write methods, then delete it."""
    console.print("\n=== WorkItem (write) ===")
    tag_name = f"oop-smoke-{uuid.uuid4().hex[:8]}"

    wi: WorkItem | None = run(
        "proj.create_work_item(Task)",
        lambda: proj.create_work_item(
            "Task",
            {
                "System.Title": (
                    f"[oop-smoke] OOP smoke test task {uuid.uuid4().hex[:6]}"
                ),
                "System.Description": "Created by smoke_test_oop.py — safe to delete.",
            },
        ),
    )
    if wi is None:
        return None

    run(
        "wi.update(title)", lambda: wi.update({"System.Title": wi.title + " (updated)"})
    )
    run(
        "wi.move(iteration_path=None)",
        lambda: wi.move(iteration_path=wi.iteration_path),
    )
    run("wi.add_tag()", lambda: wi.add_tag(tag_name))
    run("wi.list_tags() after add", wi.list_tags)
    run("wi.remove_tag()", lambda: wi.remove_tag(tag_name))
    comment = run(
        "wi.add_comment()", lambda: wi.add_comment("<p>OOP smoke comment</p>")
    )
    if comment:
        run(
            "wi.update_comment()",
            lambda cid=comment.id: wi.update_comment(cid, "<p>updated</p>"),
        )
        run("wi.delete_comment()", lambda cid=comment.id: wi.delete_comment(cid))
    attachment_ref = run(
        "wi.add_attachment()",
        lambda: wi.add_attachment("smoke.txt", b"hello from oop smoke test"),
    )
    if attachment_ref is not None:
        run(
            "wi.get_attachment_bytes(ref)",
            lambda ref=attachment_ref: wi.get_attachment_bytes(ref),
        )
    run("wi.iter_attachments() after add", lambda: _take(wi.iter_attachments(), 5))

    # Create a second WI to link to
    wi2: WorkItem | None = run(
        "proj.create_work_item(Task) [sibling for link]",
        lambda: proj.create_work_item(
            "Task",
            {"System.Title": f"[oop-smoke] Link target {uuid.uuid4().hex[:6]}"},
        ),
    )
    # create_child
    child_wi: WorkItem | None = run(
        "wi.create_child(Task)",
        lambda: wi.create_child(
            "Task",
            f"[oop-smoke] Child task {uuid.uuid4().hex[:6]}",
        ),
    )
    if child_wi:
        run("wi.get_child_ids() after create_child", wi.get_child_ids)
        run("child_wi.delete()", child_wi.delete)

    _exercise_wi_links(wi, wi2, build, repo, existing_pr)

    # Soft-delete the created WIs
    if wi2:
        run("wi2.delete()", wi2.delete)
    run("wi.delete()", wi.delete)

    return wi
