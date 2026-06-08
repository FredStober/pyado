"""Integration tests for wiki endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado import raw
from tests.integration.raw._support import console


def test_wiki_read(project_api_call: raw.ApiCall) -> None:
    """List wikis and fetch wiki pages."""
    console.print("\n=== WIKI (read) ===")
    wikis = list(raw.iter_wikis(project_api_call))
    assert wikis == raw.list_wikis(project_api_call)
    if wikis:
        wiki = wikis[0]
        raw.get_wiki_pages(project_api_call, wiki.id)
