"""Integration tests for Build OOP class (write)."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import uuid

from pyado.oop import Build


def test_write_build_tags(build: Build | None) -> None:
    """Exercise Build.add_tag() and remove_tag()."""
    if build is None:
        return
    smoke_tag = f"oop-smoke-{uuid.uuid4().hex[:6]}"
    build.add_tag(smoke_tag)
    list(build.iter_tags())
    build.remove_tag(smoke_tag)
