"""Tests for pyado.raw.core.download."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import MagicMock, patch

import pytest
import requests

from pyado.raw import get_ado_url_bytes
from tests.conftest import _make_mock_response


def test_downloads_bytes_from_ado_host() -> None:
    """Fetches bytes from an Azure DevOps host with the given session."""
    response = _make_mock_response()
    response.content = b"PNG"
    with patch.object(requests.Session, "request", return_value=response) as m:
        data = get_ado_url_bytes(
            requests.Session(), "https://dev.azure.com/o/p/_apis/wit/attachments/x"
        )
    assert data == b"PNG"
    assert m.call_args.kwargs["url"] == (
        "https://dev.azure.com/o/p/_apis/wit/attachments/x"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example.com/x.png",
        "https://dev.azure.com.evil.example.com/x",
        "http://dev.azure.com/o/x",
        "file:///etc/passwd",
    ],
)
def test_rejects_foreign_or_insecure_urls(url: str) -> None:
    """Refuses non-https and non-Azure DevOps hosts before any request."""
    session = MagicMock(spec=requests.Session)
    with pytest.raises(ValueError, match="Refusing"):
        get_ado_url_bytes(session, url)
    session.request.assert_not_called()
