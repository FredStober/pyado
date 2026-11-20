"""Authenticated download of Azure DevOps-hosted URLs."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import cast
from urllib.parse import urlparse

import requests

from pyado.raw._core import _ADO_URL_ADAPTER, ApiCall

__all__ = ["get_ado_url_bytes"]

_ALLOWED_HOST_SUFFIXES = (".azure.com", ".visualstudio.com")


def get_ado_url_bytes(session: requests.Session, url: str) -> bytes:
    """Download an absolute Azure DevOps URL using the authenticated session.

    Work item descriptions, comments and wiki pages embed absolute URLs
    (inline images, attachments).  This helper fetches them with the session's
    credentials.  To avoid leaking the credentials to third parties the URL
    host must belong to Azure DevOps (``*.azure.com`` / ``*.visualstudio.com``).

    Args:
        session: Authenticated session (from :func:`~pyado.raw.get_session`).
        url: Absolute ``https`` URL to download.

    Returns:
        The response body.

    Raises:
        ValueError: If the URL is not an ``https`` URL on an Azure DevOps host.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host.endswith(_ALLOWED_HOST_SUFFIXES):
        error_message = f"Refusing to send credentials to non-Azure DevOps URL: {url}"
        raise ValueError(error_message)
    api_call = ApiCall(session=session, url=_ADO_URL_ADAPTER.validate_python(url))
    return cast("bytes", api_call.get_raw())
