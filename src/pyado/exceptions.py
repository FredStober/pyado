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
    "AzureDevOpsThrottledError",
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


class AzureDevOpsThrottledError(AzureDevOpsHttpError):
    """HTTP 429 from the Azure DevOps API (rate limited).

    Attributes:
        retry_after_seconds: Value of the response's ``Retry-After``
            header, in seconds, or None if the server did not send
            one. Callers should wait at least this long before
            retrying.
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        retry_after_seconds: float | None = None,
    ) -> None:
        """Construct the error.

        Args:
            status_code: HTTP status code (429).
            message: Human-readable error message from the API.
            retry_after_seconds: Server-provided cooldown, if any.
        """
        super().__init__(status_code, message)
        self.retry_after_seconds = retry_after_seconds
