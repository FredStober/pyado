"""Integration tests for secure file endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado import raw
from tests.integration.raw._support import console


def test_secure_files_read(project_api_call: raw.ApiCall) -> None:
    """List secure files and fetch individual file details."""
    console.print("\n=== SECURE FILES (read) ===")

    files = list(raw.iter_secure_files(project_api_call))
    raw.list_secure_files(project_api_call)
    if files:
        sf = files[0]
        raw.get_secure_file_api_call(project_api_call, sf.id)
        raw.get_secure_file(project_api_call, sf.id)
