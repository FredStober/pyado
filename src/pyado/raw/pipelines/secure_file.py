"""Azure DevOps distributed task secure file API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from datetime import datetime
from typing import TypeAlias
from uuid import UUID

from pyado.raw._core import AdoBaseModel, ApiCall

__all__ = [
    "SecureFileId",
    "SecureFileInfo",
    "delete_secure_file",
    "get_secure_file",
    "get_secure_file_api_call",
    "iter_secure_files",
    "list_secure_files",
]

SecureFileId: TypeAlias = UUID

_SECURE_FILE_API_VERSION = "7.1"


class SecureFileInfo(AdoBaseModel):
    """Minimal representation of an ADO secure file."""

    id: SecureFileId
    name: str
    created_on: datetime | None = None
    modified_on: datetime | None = None
    created_by: str | None = None
    modified_by: str | None = None


def get_secure_file_api_call(
    project_api_call: ApiCall,
    file_id: SecureFileId,
) -> ApiCall:
    """Build a secure-file-scoped API call.

    Args:
        project_api_call: Project-level ADO API call.
        file_id: UUID of the secure file.

    Returns:
        An ApiCall pointing at the secure file resource.
    """
    return project_api_call.build_call(
        "distributedtask",
        "securefiles",
        file_id,
        version=_SECURE_FILE_API_VERSION,
    )


def iter_secure_files(
    project_api_call: ApiCall,
) -> Iterator[SecureFileInfo]:
    """Iterate over all secure files in a project.

    Args:
        project_api_call: Project-level ADO API call.

    Yields:
        SecureFileInfo for each secure file in the project.
    """
    result = project_api_call.get(
        "distributedtask",
        "securefiles",
        version=_SECURE_FILE_API_VERSION,
    )
    for item in result.get("value", []):
        yield SecureFileInfo.model_validate(item)


def list_secure_files(
    project_api_call: ApiCall,
) -> list[SecureFileInfo]:
    """Return all secure files in a project as a list."""
    return list(iter_secure_files(project_api_call))


def get_secure_file(
    project_api_call: ApiCall,
    file_id: SecureFileId,
) -> SecureFileInfo:
    """Return a single secure file by ID.

    Args:
        project_api_call: Project-level ADO API call.
        file_id: UUID of the secure file.

    Returns:
        SecureFileInfo for the requested secure file.
    """
    result = project_api_call.get(
        "distributedtask",
        "securefiles",
        file_id,
        version=_SECURE_FILE_API_VERSION,
    )
    return SecureFileInfo.model_validate(result)


def delete_secure_file(secure_file_api_call: ApiCall) -> None:
    """Delete a secure file.

    Args:
        secure_file_api_call: Secure-file-level ADO API call (from
            get_secure_file_api_call).
    """
    secure_file_api_call.delete()
