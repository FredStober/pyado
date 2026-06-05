"""Smoke tests for work item and classification node endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import contextlib
import random

from pyado import raw
from pyado.raw import ClassificationNodePatchRequest, ClassificationNodeRequest
from pyado.raw.smoke_test._runner import _DIM, _RESET, _skip, _take, console, run


def _test_work_items_read(
    project_api_call: raw.ApiCall,
    rng: random.Random,
) -> None:
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
    wi_refs = run(
        "post_wiql",
        lambda q=wiql_queries[0]: raw.post_wiql(project_api_call, q),
    )
    run(
        "post_wiql [alternate query]",
        lambda q=wiql_queries[1]: raw.post_wiql(project_api_call, q),
    )

    wi_ids = [ref.id for ref in (wi_refs or [])[:10]]
    if wi_ids:
        console.print(f"  {_DIM}work item ids: {wi_ids}{_RESET}")
    if not wi_ids:
        for label in (
            "post_work_items_batch",
            "get_work_item",
            "iter_work_item_comments",
        ):
            _skip(label, "WIQL returned no work items")
        return

    fields_variants: list[list[str] | None] = [
        None,
        ["System.Id", "System.Title"],
        ["System.Id", "System.Title", "System.State", "System.WorkItemType"],
        ["System.Id", "System.Title", "System.Description", "System.AssignedTo"],
    ]
    rng.shuffle(fields_variants)
    for fields in fields_variants[:3]:
        run(
            f"post_work_items_batch [fields={fields!r}]",
            lambda f=fields, ids=wi_ids[:5]: raw.post_work_items_batch(
                project_api_call,
                raw.WorkItemsBatchRequest(
                    ids=ids,
                    fields=f,
                    expand="relations" if f is None else None,
                ),
            ),
        )

    wi_id = rng.choice(wi_ids)
    console.print(f"  {_DIM}selected work item: #{wi_id}{_RESET}")
    wi_api_call = raw.get_work_item_api_call(project_api_call, wi_id)
    for expand in rng.sample([raw.WorkItemExpand.RELATIONS, None], 2):
        label = "True" if expand is not None else "False"
        run(
            f"get_work_item [id={wi_id}, expand_relations={label}]",
            lambda e=expand, api=wi_api_call: raw.get_work_item(api, expand=e),
        )

    run(
        f"iter_work_item_comments [id={wi_id}]",
        lambda api=wi_api_call: _take(raw.list_work_item_comments(api), 20),
    )


def _test_work_item_extras_read(
    project_api_call: raw.ApiCall,
    rng: random.Random,
) -> None:
    console.print("\n=== WORK ITEM EXTRAS (read) ===")
    wi_refs = raw.post_wiql(
        project_api_call,
        "SELECT [System.Id] FROM WorkItems ORDER BY [System.ChangedDate] DESC",
    )
    wi_ids = [ref.id for ref in (wi_refs or [])[:5]]
    if not wi_ids:
        for label in ("iter_work_item_revisions",):
            _skip(label, "no work items found")
        return

    wi_id = rng.choice(wi_ids)
    wi_api_call = raw.get_work_item_api_call(project_api_call, wi_id)
    run(
        f"iter_work_item_revisions [id={wi_id}]",
        lambda api=wi_api_call: _take(raw.list_work_item_revisions(api), 5),
    )


def _test_work_item_write(
    project_api_call: raw.ApiCall,
    rng: random.Random,
    run_ts: str,
) -> None:
    console.print("\n=== WORK ITEM (write) ===")

    # raw.post_work_item — explicit JSON patch list
    wi = run(
        "post_work_item [create Task]",
        lambda: raw.post_work_item(
            project_api_call,
            "Task",
            [
                raw.JsonPatchAdd(
                    path="/fields/System.Title",
                    value=f"[pyado-smoke-test][{run_ts}] Temporary task",
                ),
                raw.JsonPatchAdd(
                    path="/fields/System.Description",
                    value="Created by pyado smoke_test.py — safe to close/delete",
                ),
            ],
        ),
    )
    if wi is not None:
        console.print(f"  {_DIM}created work item #{wi.id}{_RESET}")
    if wi is None:
        _skip("patch_work_item", "work item creation failed")
        _skip("post_work_item_comment", "work item creation failed")
        return

    wi_api_call = raw.get_work_item_api_call(project_api_call, wi.id)

    title_variants = [
        f"[pyado-smoke-test] Updated title A (seed={rng.randint(1000, 9999)})",
        f"[pyado-smoke-test] Updated title B (seed={rng.randint(1000, 9999)})",
    ]
    for title in title_variants:
        run(
            "patch_work_item [update title]",
            lambda t=title: raw.patch_work_item(
                wi_api_call,
                [raw.JsonPatchAdd(path="/fields/System.Title", value=t)],
            ),
        )

    # Comments — html and markdown
    comment_formats = ["html", "markdown"]
    rng.shuffle(comment_formats)
    for fmt in comment_formats:
        run(
            f"post_work_item_comment [{fmt}]",
            lambda f=fmt: raw.post_work_item_comment(
                wi_api_call,
                f"Smoke test comment ({f}) seed={rng.randint(0, 99999)}",
                comment_format=f,
            ),
        )

    comments_after = run(
        "iter_work_item_comments [after add]",
        lambda: _take(raw.iter_work_item_comments(wi_api_call), 10),
    )
    # patch/delete first comment
    if comments_after:
        first_comment = comments_after[0]
        run(
            f"patch_work_item_comment [id={first_comment.id}]",
            lambda cid=first_comment.id: raw.patch_work_item_comment(
                wi_api_call, cid, "Updated by smoke test"
            ),
        )
        run(
            f"delete_work_item_comment [id={first_comment.id}]",
            lambda cid=first_comment.id: raw.delete_work_item_comment(wi_api_call, cid),
        )
    else:
        _skip("patch_work_item_comment", "no comments to update")
        _skip("delete_work_item_comment", "no comments to delete")

    # post_work_item_attachment_upload + get_work_item_attachment_bytes
    attachment_ref = run(
        "post_work_item_attachment_upload",
        lambda: raw.post_work_item_attachment_upload(
            project_api_call, "smoke.txt", b"hello from raw smoke test"
        ),
    )
    if attachment_ref:
        run(
            "get_work_item_attachment_bytes",
            lambda ref=attachment_ref: raw.get_work_item_attachment_bytes(
                project_api_call, str(ref.id)
            ),
        )
    else:
        _skip("get_work_item_attachment_bytes", "attachment upload failed")

    # iter_work_item_revisions
    run(
        "iter_work_item_revisions [after updates]",
        lambda: _take(raw.iter_work_item_revisions(wi_api_call), 5),
    )

    # Close work item
    run(
        "patch_work_item [close]",
        lambda: raw.patch_work_item(
            wi_api_call,
            [raw.JsonPatchAdd(path="/fields/System.State", value="Closed")],
        ),
    )

    # delete_work_item (soft delete) → restore_work_item → delete again (permanent)
    delete_failed = False

    def _soft_delete() -> None:
        nonlocal delete_failed
        try:
            raw.delete_work_item(wi_api_call)
        except Exception:
            delete_failed = True
            raise

    run("delete_work_item [soft]", _soft_delete)
    if not delete_failed:
        # restore_work_item — bring the item back from the Recycle Bin
        run(
            "restore_work_item",
            lambda: raw.restore_work_item(project_api_call, wi.id),
        )
        # Final permanent delete
        run("delete_work_item [permanent]", lambda: raw.delete_work_item(wi_api_call))
    else:
        _skip("restore_work_item", "soft delete failed")
        _skip("delete_work_item [permanent]", "soft delete failed")


def _test_query_classification_read(
    project_api_call: raw.ApiCall,
) -> None:
    console.print("\n=== QUERY TREE & CLASSIFICATION NODES (read) ===")
    run("get_query_tree", lambda: raw.get_query_tree(project_api_call))
    query_tree = raw.get_query_tree(project_api_call)
    if query_tree:
        run(
            f"get_query_folder [id={query_tree[0].id}]",
            lambda fid=query_tree[0].id: raw.get_query_folder(project_api_call, fid),
        )
    else:
        _skip("get_query_folder", "no query folders returned")

    run(
        "get_classification_node [iterations]",
        lambda: raw.get_classification_node(
            project_api_call, node_type="iterations", depth=2
        ),
    )
    run(
        "get_classification_node [areas]",
        lambda: raw.get_classification_node(
            project_api_call, node_type="areas", depth=2
        ),
    )


def _test_classification_write(
    project_api_call: raw.ApiCall,
    rng: random.Random,
) -> None:
    console.print("\n=== CLASSIFICATION NODES (write) ===")

    iter_name = f"smoke-iter-{rng.randint(10000, 99999)}"
    area_name = f"smoke-area-{rng.randint(10000, 99999)}"

    # Pre-cleanup: delete any leftover nodes from previous runs (e.g. if a prior
    # session created but never deleted them).  Ignore errors — the nodes may not
    # exist.
    for cn_name, cn_type in [
        (iter_name, "iterations"),
        (iter_name + "-patched", "iterations"),
        (area_name, "areas"),
        (area_name + "-patched", "areas"),
    ]:
        with contextlib.suppress(Exception):
            raw.delete_classification_node(project_api_call, cn_name, node_type=cn_type)

    # create_classification_node — iteration
    created_iter = run(
        f"create_classification_node [iterations, name={iter_name!r}]",
        lambda: raw.create_classification_node(
            project_api_call,
            ClassificationNodeRequest(name=iter_name),
            node_type="iterations",
        ),
    )
    if created_iter:
        run(
            f"patch_classification_node [iterations, name={iter_name!r}]",
            lambda: raw.patch_classification_node(
                project_api_call,
                iter_name,
                ClassificationNodePatchRequest(name=iter_name + "-patched"),
                node_type="iterations",
            ),
        )
        run(
            f"delete_classification_node [iterations, name={iter_name + '-patched'!r}]",
            lambda: raw.delete_classification_node(
                project_api_call,
                iter_name + "-patched",
                node_type="iterations",
            ),
        )

    # create_classification_node — area
    created_area = run(
        f"create_classification_node [areas, name={area_name!r}]",
        lambda: raw.create_classification_node(
            project_api_call,
            ClassificationNodeRequest(name=area_name),
            node_type="areas",
        ),
    )
    if created_area:
        run(
            f"patch_classification_node [areas, name={area_name!r}]",
            lambda: raw.patch_classification_node(
                project_api_call,
                area_name,
                ClassificationNodePatchRequest(name=area_name + "-patched"),
                node_type="areas",
            ),
        )
        run(
            f"delete_classification_node [areas, name={area_name + '-patched'!r}]",
            lambda: raw.delete_classification_node(
                project_api_call,
                area_name + "-patched",
                node_type="areas",
            ),
        )
