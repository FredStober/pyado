"""Integration tests for wiki endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado import raw
from tests.integration.raw._support import console

_TEST_PAGE_PATH = "/pyado-integration-test-page"


def test_wiki_read(project_api_call: raw.ApiCall) -> None:
    """List wikis and fetch wiki pages."""
    console.print("\n=== WIKI (read) ===")
    wikis = list(raw.iter_wikis(project_api_call))
    assert wikis == raw.list_wikis(project_api_call)
    if wikis:
        wiki = wikis[0]
        raw.get_wiki_pages(project_api_call, wiki.id)


def test_wiki_page_crud(project_api_call: raw.ApiCall) -> None:
    """Create, read, update and delete a wiki page."""
    console.print("\n=== WIKI (CRUD) ===")
    wikis = raw.list_wikis(project_api_call)
    if not wikis:
        console.print("No wikis found — skipping CRUD test")
        return
    wiki_id = wikis[0].id

    # Create
    created = raw.put_wiki_page(
        project_api_call, wiki_id, _TEST_PAGE_PATH, "# Integration test\nCreated."
    )
    assert created.path == _TEST_PAGE_PATH

    # Read
    fetched = raw.get_wiki_page(project_api_call, wiki_id, _TEST_PAGE_PATH)
    assert fetched.path == _TEST_PAGE_PATH
    assert fetched.id is not None
    page_id = fetched.id

    # Attachments (empty for new page)
    attachments = raw.get_wiki_page_attachments(project_api_call, wiki_id, page_id)
    assert isinstance(attachments, list)

    # Update (version 0 is the initial version for a newly created page)
    updated = raw.put_wiki_page(
        project_api_call,
        wiki_id,
        _TEST_PAGE_PATH,
        "# Integration test\nUpdated.",
        version=0,
    )
    assert updated.path == _TEST_PAGE_PATH

    # Delete
    deleted = raw.delete_wiki_page(
        project_api_call, wiki_id, _TEST_PAGE_PATH, version=1
    )
    assert deleted.path == _TEST_PAGE_PATH
