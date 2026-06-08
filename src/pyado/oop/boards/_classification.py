"""Shared helpers for classification node (area / iteration) operations."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

__all__: list[str] = []

# ADO sometimes includes the tree-root type segment ("Area" or "Iteration")
# as the second path component for nodes created at the root of the tree.
# The raw API expects a path relative to the type root, so this segment must
# be skipped when present.
_TYPE_SEGMENTS: frozenset[str] = frozenset({"Area", "Iteration"})


def _relative_path(full_path: str | None) -> str | None:
    r"""Strip the leading project-name prefix from a classification node path.

    ADO returns paths like ``"\\\\ProjectName\\\\Team A"`` or, for nodes
    created at the type root, ``"\\\\ProjectName\\\\Area\\\\Team A"``.
    The raw API expects only the relative portion, e.g. ``"Team A"``.

    Args:
        full_path: Full path string from the API response, or None.

    Returns:
        Relative path string, or None for a root node.
    """
    if not full_path:
        return None
    parts = full_path.lstrip("\\").split("\\")
    # parts[0] is the project name.  parts[1] may be the tree-type root
    # segment ("Area" or "Iteration") that ADO includes in the full path for
    # nodes created at the tree root.  Skip it when present so the returned
    # path matches what the raw API URL expects.
    start = 2 if len(parts) > 1 and parts[1] in _TYPE_SEGMENTS else 1
    relative = "\\".join(parts[start:])
    return relative or None
