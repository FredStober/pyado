"""Integration tests for the work item mail endpoint (``wit/sendMail``)."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from uuid import UUID

from pyado import raw
from tests.integration.raw._support import console

_WIQL = (
    "SELECT [System.Id] FROM WorkItems"
    " WHERE [System.WorkItemType] = 'Task'"
    " ORDER BY [System.ChangedDate] DESC"
)


def test_work_item_mail(
    token: str,
    org_url: str,
    project_api_call: raw.ApiCall,
    run_ts: str,
) -> None:
    """Mail a temporary work item to the authenticated user only."""
    console.print("\n=== WORK ITEM (mail) ===")

    # get_connection_data appends ``_apis`` itself, so it needs the bare org URL.
    org_call = raw.ApiCall(session=raw.get_session(pat=token), url=org_url)
    me = UUID(raw.get_connection_data(org_call).authenticated_user.id)
    wi = raw.post_work_item(
        project_api_call,
        raw.WorkItemTypeName.TASK,
        [
            raw.JsonPatchAdd(
                path=f"/fields/{raw.WorkItemFieldName.TITLE}",
                value=f"[pyado-smoke-test][{run_ts}] Temporary mail task",
            ),
        ],
    )
    wi_api_call = raw.get_work_item_api_call(project_api_call, wi.id)
    try:
        # Select by work item ID.
        raw.post_send_mail(
            project_api_call,
            raw.WorkItemMailRequest(
                message=raw.WorkItemMailMessage(
                    subject=f"[pyado-smoke-test][{run_ts}] by id",
                    body="Plain text note.\nhttps://example.com",
                    to=raw.EmailRecipients(tf_ids=[me]),
                ),
                ids=[wi.id],
                fields=[raw.WorkItemFieldName.ID, raw.WorkItemFieldName.TITLE],
            ),
        )
        console.print(f"  mailed work item #{wi.id} by id")

        # Select by WIQL (static query; only checks that ADO accepts the request).
        raw.post_send_mail(
            project_api_call,
            raw.WorkItemMailRequest(
                message=raw.WorkItemMailMessage(
                    subject=f"[pyado-smoke-test][{run_ts}] by wiql",
                    body="WIQL selection.",
                    to=raw.EmailRecipients(tf_ids=[me]),
                ),
                wiql=_WIQL,
                fields=[raw.WorkItemFieldName.ID, raw.WorkItemFieldName.TITLE],
            ),
        )
        console.print(f"  mailed work item #{wi.id} by wiql")
    finally:
        raw.delete_work_item(wi_api_call)
