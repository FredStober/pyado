"""Module with AzureDevOps exceptions."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

__all__ = [
    "AzureDevOpsAuthError",
    "AzureDevOpsBadRequestError",
    "AzureDevOpsConflictError",
    "AzureDevOpsError",
    "AzureDevOpsHttpError",
    "AzureDevOpsNotFoundError",
]


class AzureDevOpsError(Exception):
    """Base class for all Azure DevOps errors raised by pyado."""


class AzureDevOpsHttpError(AzureDevOpsError):
    """An HTTP error response from the Azure DevOps REST API.

    Attributes:
        status_code: The HTTP status code returned by the API.
        message: The error message extracted from the response body.
    """

    def __init__(self, status_code: int, message: str) -> None:
        """Construct the error.

        Args:
            status_code: HTTP status code.
            message: Human-readable error message from the API.
        """
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class AzureDevOpsAuthError(AzureDevOpsHttpError):
    """HTTP 401 or 403 from the Azure DevOps API (authentication/authorisation)."""


class AzureDevOpsNotFoundError(AzureDevOpsHttpError):
    """HTTP 404 from the Azure DevOps API (resource not found)."""


class AzureDevOpsConflictError(AzureDevOpsHttpError):
    """HTTP 409 from the Azure DevOps API (conflict with current state)."""


class AzureDevOpsBadRequestError(AzureDevOpsHttpError):
    """HTTP 400 from the Azure DevOps API (malformed or invalid request)."""
