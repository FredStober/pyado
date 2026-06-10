"""Integration tests for Process OOP class."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado.oop import Organization, Process
from tests.integration.raw._support import console


def test_process_read(org: Organization) -> None:
    """List and fetch process templates via the OOP layer."""
    console.print("\n=== Process (read) ===")
    processes = org.list_processes()
    console.print(f"Found {len(processes)} process(es)")
    assert isinstance(processes, list)
    for proc in processes:
        assert isinstance(proc, Process)
        console.print(f"  {proc.name} ({proc.id})")

    if processes:
        fetched = org.get_process(processes[0].id)
        assert isinstance(fetched, Process)
        assert fetched.id == processes[0].id
        console.print(f"Fetched by ID: {fetched.name}")
