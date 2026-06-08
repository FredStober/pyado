"""Integration tests for profile and VSSPS endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import pytest

from pyado.exceptions import AzureDevOpsAuthError
from tests.integration.raw._support import _test_profile


def test_profile(token: str, org_url: str) -> None:
    """Profile and VSSPS API round-trip."""
    try:
        _test_profile(token, org_url)
    except AzureDevOpsAuthError:
        pytest.skip(reason="PAT lacks vso.profile scope")
