"""OOP wrapper for Azure DevOps secure file resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import TYPE_CHECKING

from pyado import raw
from pyado.raw import (
    ApiCall,
    SecureFileId,
    SecureFileInfo,
)

if TYPE_CHECKING:
    from pyado.oop.organization import Organization
    from pyado.oop.project import Project

__all__ = ["SecureFile"]


class SecureFile:
    """An Azure DevOps secure file resource.

    **ADO concept:** a *secure file* is an encrypted file stored in the
    pipeline library (``distributedtask/securefiles/{id}``).  Common uses
    include signing certificates, provisioning profiles, and SSH keys.
    Secure files can be referenced in pipelines via the
    ``DownloadSecureFile`` task.

    **Why it exists:** bundles the secure file ID and info together so
    callers can inspect properties and delete the file without managing
    raw API calls.

    Instances are obtained from :meth:`PipelineLibrary.iter_secure_files` or
    :meth:`PipelineLibrary.get_secure_file`.

    Attributes:
        _project: The Project this secure file belongs to.
        _api_call: Secure-file-level ADO API call.
        _info: Cached secure file data.
    """

    def __init__(
        self,
        project: "Project",
        secure_file_api_call: ApiCall,
        info: SecureFileInfo,
    ) -> None:
        """Construct a SecureFile wrapper.

        Args:
            project: The Project that owns this secure file.
            secure_file_api_call: Secure-file-level ADO API call (from
                raw.get_secure_file_api_call).
            info: Secure file data as returned from the API.
        """
        self._project = project
        self._api_call = secure_file_api_call
        self._file_id = info.id
        self._info: SecureFileInfo | None = info

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def info(self) -> SecureFileInfo:
        """Secure file data captured at construction time."""
        if self._info is None:
            self._info = raw.get_secure_file(self._project.api_call, self._file_id)
        return self._info

    @property
    def id(self) -> SecureFileId:
        """UUID of the secure file."""
        return self.info.id

    @property
    def name(self) -> str:
        """Secure file name."""
        return self.info.name

    @property
    def api_call(self) -> ApiCall:
        """Secure-file-level API call for direct use with pyado.raw functions."""
        return self._api_call

    @property
    def project(self) -> "Project":
        """Project this secure file belongs to — zero-cost."""
        return self._project

    @property
    def org(self) -> "Organization":
        """Organisation this secure file belongs to — zero-cost."""
        return self._project.org

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Discard cached secure file info.

        The next access to :attr:`info` re-fetches from the API.
        """
        self._info = None

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def delete(self) -> None:
        """Delete this secure file from the project.

        The deletion is permanent and cannot be undone via the API.
        """
        raw.delete_secure_file(self._api_call)
