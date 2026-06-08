"""Integration tests for search API endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado import raw
from tests.integration.raw._support import console


def test_search_read(
    org_api_call: raw.ApiCall,
    project_name: str,
) -> None:
    """Search code, work items, wiki, and packages."""
    session = org_api_call.session
    org_name = (
        org_api_call.url.unicode_string()
        .rstrip("/")
        .removesuffix("/_apis")
        .rsplit("/", 1)[-1]
    )
    console.print("\n=== SEARCH (read) ===")

    search_api_call = raw.get_search_api_call(session, org_name)
    if not search_api_call:
        return

    list(
        raw.post_code_search(
            search_api_call,
            raw.CodeSearchRequest(
                search_text="def ", top=5, filters={"Project": [project_name]}
            ),
        )
    )
    list(
        raw.post_work_item_search(
            search_api_call,
            raw.SearchRequest(
                search_text="smoke",
                top=5,
                filters={"System.TeamProject": [project_name]},
            ),
        )
    )
    list(
        raw.post_wiki_search(
            search_api_call,
            raw.SearchRequest(
                search_text="smoke", top=5, filters={"Project": [project_name]}
            ),
        )
    )
    list(
        raw.post_package_search(
            search_api_call, raw.SearchRequest(search_text="pyado", top=5)
        )
    )
