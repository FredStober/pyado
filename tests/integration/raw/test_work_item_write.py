"""Integration tests for work item write endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import random

from pyado import raw
from tests.integration.raw._support import _take, console


def test_work_item_write(
    project_api_call: raw.ApiCall,
    rng: random.Random,
    run_ts: str,
) -> None:
    """Create, update, comment, attach, and delete a work item."""
    console.print("\n=== WORK ITEM (write) ===")

    # raw.post_work_item — explicit JSON patch list
    wi = raw.post_work_item(
        project_api_call,
        raw.WorkItemTypeName.TASK,
        [
            raw.JsonPatchAdd(
                path=f"/fields/{raw.WorkItemFieldName.TITLE}",
                value=f"[pyado-smoke-test][{run_ts}] Temporary task",
            ),
            raw.JsonPatchAdd(
                path=f"/fields/{raw.WorkItemFieldName.DESCRIPTION}",
                value="Created by pyado smoke_test.py — safe to close/delete",
            ),
        ],
    )
    console.print(f"  created work item #{wi.id}")

    wi_api_call = raw.get_work_item_api_call(project_api_call, wi.id)

    title_variants = [
        f"[pyado-smoke-test] Updated title A (seed={rng.randint(1000, 9999)})",
        f"[pyado-smoke-test] Updated title B (seed={rng.randint(1000, 9999)})",
    ]
    for title in title_variants:
        raw.patch_work_item(
            wi_api_call,
            [
                raw.JsonPatchAdd(
                    path=f"/fields/{raw.WorkItemFieldName.TITLE}", value=title
                )
            ],
        )

    # Comments — html and markdown
    comment_formats = [raw.TextFormat.HTML, raw.TextFormat.MARKDOWN]
    rng.shuffle(comment_formats)
    for fmt in comment_formats:
        raw.post_work_item_comment(
            wi_api_call,
            f"Smoke test comment ({fmt}) seed={rng.randint(0, 99999)}",
            comment_format=fmt,
        )

    comments_after = _take(raw.iter_work_item_comments(wi_api_call), 10)
    # patch/delete first comment
    if comments_after:
        first_comment = comments_after[0]
        raw.patch_work_item_comment(
            wi_api_call, first_comment.id, "Updated by smoke test"
        )
        raw.delete_work_item_comment(wi_api_call, first_comment.id)

    # post_work_item_attachment_upload + get_work_item_attachment_bytes
    attachment_ref = raw.post_work_item_attachment_upload(
        project_api_call, "smoke.txt", b"hello from raw smoke test"
    )
    if attachment_ref:
        raw.get_work_item_attachment_bytes(project_api_call, str(attachment_ref.id))

    # iter_work_item_revisions
    _take(raw.iter_work_item_revisions(wi_api_call), 5)

    # Close work item
    raw.patch_work_item(
        wi_api_call,
        [
            raw.JsonPatchAdd(
                path=f"/fields/{raw.WorkItemFieldName.STATE}",
                value=raw.WorkItemState.CLOSED,
            )
        ],
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

    _soft_delete()
    if not delete_failed:
        # restore_work_item — bring the item back from the Recycle Bin
        raw.patch_recycle_bin_work_item(project_api_call, wi.id)
        # Final permanent delete
        raw.delete_work_item(wi_api_call)
