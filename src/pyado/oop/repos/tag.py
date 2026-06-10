"""OOP wrapper for an Azure DevOps git tag."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import TYPE_CHECKING

from pyado import raw
from pyado.exceptions import AzureDevOpsNotFoundError
from pyado.raw import AnnotatedTagInfo, CommitId, GitRef

if TYPE_CHECKING:
    from pyado.oop.repos.commit import Commit
    from pyado.oop.repos.repository import Repository

__all__ = ["Tag"]


class Tag:
    """A git tag in an Azure DevOps repository.

    Wraps a :class:`~pyado.raw.GitRef` for a ``refs/tags/…`` ref and
    exposes tag-specific convenience methods.  Instances are obtained
    from :meth:`Repository.iter_git_tags` or
    :meth:`ProjectRepos.iter_git_tags`.

    Attributes:
        _repo: The Repository this tag belongs to.
        _ref: The underlying GitRef data.
    """

    def __init__(self, repo: "Repository", ref: GitRef) -> None:
        """Construct a Tag wrapper.

        Args:
            repo: The Repository that contains this tag.
            ref: GitRef for the tag (name should start with ``"refs/tags/"``).
        """
        self._repo = repo
        self._ref = ref

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def ref(self) -> GitRef:
        """Underlying GitRef data."""
        return self._ref

    @property
    def name(self) -> str:
        """Short tag name (``refs/tags/`` prefix stripped)."""
        return self._ref.name.removeprefix("refs/tags/")

    @property
    def full_name(self) -> str:
        """Full ref name (e.g. ``"refs/tags/v1.0"``)."""
        return self._ref.name

    @property
    def commit_id(self) -> CommitId:
        """Commit SHA the tag points at."""
        return self._ref.object_id

    @property
    def repo(self) -> "Repository":
        """Repository this tag belongs to — zero-cost."""
        return self._repo

    # ------------------------------------------------------------------
    # Methods
    # ------------------------------------------------------------------

    def get_commit(self) -> "Commit":
        """Return the commit this tag points at.

        For lightweight tags the ``objectId`` in the ref is already the commit
        SHA.  For annotated tags it is the tag-object SHA; in that case the
        method fetches the annotated tag to dereference it to the actual commit.

        Returns:
            :class:`~pyado.oop.repos.commit.Commit` the tag targets.

        Raises:
            AzureDevOpsNotFoundError: If the commit or annotated tag object
                cannot be resolved.
        """
        try:
            return self._repo.get_commit(self.commit_id)
        except AzureDevOpsNotFoundError:
            tag_info = raw.get_annotated_tag(self._repo.api_call, self.commit_id)
            if tag_info.tagged_object is None:
                raise
            return self._repo.get_commit(tag_info.tagged_object.object_id)

    def get_annotated_info(self) -> AnnotatedTagInfo | None:
        """Return the annotated tag metadata, or ``None`` for lightweight tags.

        Fetches the tag object from ADO to retrieve the tagger identity,
        timestamp, and annotation message.  Lightweight tags point directly
        to a commit rather than to a tag object; ADO returns 404 for them,
        so this method returns ``None`` in that case.

        Returns:
            AnnotatedTagInfo with tagger, message, and tagged-object details,
            or ``None`` if this is a lightweight tag.
        """
        try:
            return raw.get_annotated_tag(self._repo.api_call, self.commit_id)
        except AzureDevOpsNotFoundError:
            return None

    def delete(self) -> None:
        """Delete this tag from the repository.

        Uses the stored commit SHA as the optimistic-concurrency guard.
        """
        self._repo.delete_git_tag(self.name, self.commit_id)
