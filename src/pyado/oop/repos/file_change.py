"""OOP objects for file changes within a git push commit."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import base64
from pathlib import Path

from pyado.raw import (
    GitChangeType,
    GitPushChange,
    GitPushChangeItem,
    GitPushContentType,
    GitPushNewContent,
)

__all__ = ["AddFile", "DeleteFile", "EditFile", "RenameFile"]


def _make_content(source: str | bytes | Path) -> GitPushNewContent:
    """Resolve a content source to a GitPushNewContent model.

    str  → RAWTEXT (passed through as-is).
    bytes → BASE64ENCODED (base64-encoded).
    Path → read as bytes; decoded as UTF-8 text when possible, otherwise
           BASE64ENCODED (handles both text and binary files transparently).

    Returns:
        GitPushNewContent with the resolved content and encoding type.
    """
    # isinstance is required here to dispatch the user-facing str | bytes | Path union.
    if isinstance(source, Path):
        raw_bytes = source.read_bytes()
        try:
            return GitPushNewContent(content=raw_bytes.decode("utf-8"))
        except UnicodeDecodeError:
            encoded = base64.b64encode(raw_bytes).decode("ascii")
            return GitPushNewContent(
                content=encoded,
                content_type=GitPushContentType.BASE64ENCODED,
            )
    if isinstance(source, bytes):
        encoded = base64.b64encode(source).decode("ascii")
        return GitPushNewContent(
            content=encoded,
            content_type=GitPushContentType.BASE64ENCODED,
        )
    return GitPushNewContent(content=source)


class AddFile:
    """A file-add change for use in a push commit.

    Creates a new file at the given repository path.  The file must not
    already exist on the target branch; use :class:`EditFile` to update an
    existing file.

    Content can be supplied as a string (UTF-8 text), bytes (stored as
    Base64), or a local :class:`~pathlib.Path` whose contents are read
    eagerly on construction.  Binary paths are stored as Base64; text paths
    are stored as raw text.

    Attributes:
        _ado_path: Repository-root-relative destination path.
        _new_content: Resolved content model ready for the push payload.
    """

    def __init__(self, ado_path: str, content: str | bytes | Path) -> None:
        """Construct an AddFile change.

        Args:
            ado_path: Repository-root-relative path for the new file
                (e.g. ``"/src/foo.py"``).
            content: File content as a ``str``, ``bytes``, or a local
                :class:`~pathlib.Path` to read from.
        """
        self._ado_path = ado_path
        self._new_content = _make_content(content)

    def to_git_change(self) -> GitPushChange:
        """Return the equivalent :class:`~pyado.raw.GitPushChange` model."""
        return GitPushChange(
            change_type=GitChangeType.ADD,
            item=GitPushChangeItem(path=self._ado_path),
            new_content=self._new_content,
        )


class EditFile:
    """A file-edit change for use in a push commit.

    Replaces the full content of an existing file.  The file must already
    exist on the target branch; use :class:`AddFile` to create a new file.

    Content can be supplied as a string (UTF-8 text), bytes (stored as
    Base64), or a local :class:`~pathlib.Path` whose contents are read
    eagerly on construction.

    Attributes:
        _ado_path: Repository-root-relative path of the file to update.
        _new_content: Resolved content model ready for the push payload.
    """

    def __init__(self, ado_path: str, content: str | bytes | Path) -> None:
        """Construct an EditFile change.

        Args:
            ado_path: Repository-root-relative path of the file to update
                (e.g. ``"/src/foo.py"``).
            content: New file content as a ``str``, ``bytes``, or a local
                :class:`~pathlib.Path` to read from.
        """
        self._ado_path = ado_path
        self._new_content = _make_content(content)

    def to_git_change(self) -> GitPushChange:
        """Return the equivalent :class:`~pyado.raw.GitPushChange` model."""
        return GitPushChange(
            change_type=GitChangeType.EDIT,
            item=GitPushChangeItem(path=self._ado_path),
            new_content=self._new_content,
        )


class DeleteFile:
    """A file-delete change for use in a push commit.

    Removes an existing file from the repository.  The file must exist on
    the target branch.

    Attributes:
        _ado_path: Repository-root-relative path of the file to delete.
    """

    def __init__(self, ado_path: str) -> None:
        """Construct a DeleteFile change.

        Args:
            ado_path: Repository-root-relative path of the file to delete
                (e.g. ``"/old/file.py"``).
        """
        self._ado_path = ado_path

    def to_git_change(self) -> GitPushChange:
        """Return the equivalent :class:`~pyado.raw.GitPushChange` model."""
        return GitPushChange(
            change_type=GitChangeType.DELETE,
            item=GitPushChangeItem(path=self._ado_path),
        )


class RenameFile:
    """A file-rename change for use in a push commit.

    Moves a file to a new path without altering its content.  Both the
    source and destination paths must be valid on the target branch.

    Attributes:
        _old_ado_path: Current repository-root-relative path.
        _new_ado_path: Desired repository-root-relative path after rename.
    """

    def __init__(self, old_ado_path: str, new_ado_path: str) -> None:
        """Construct a RenameFile change.

        Args:
            old_ado_path: Current repository-root-relative path of the file
                (e.g. ``"/old/name.py"``).
            new_ado_path: Desired repository-root-relative path after the
                rename (e.g. ``"/new/name.py"``).
        """
        self._old_ado_path = old_ado_path
        self._new_ado_path = new_ado_path

    def to_git_change(self) -> GitPushChange:
        """Return the equivalent :class:`~pyado.raw.GitPushChange` model."""
        return GitPushChange(
            change_type=GitChangeType.RENAME,
            item=GitPushChangeItem(path=self._new_ado_path),
            source_server_item=self._old_ado_path,
        )
