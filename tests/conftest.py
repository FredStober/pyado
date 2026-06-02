"""Shared fixtures for pyado test suite."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Generator

import pytest

from pyado.api_call import ApiCall

BASE_URL = "https://dev.azure.com/org/"
ACCESS_TOKEN = "test_access_token"


@pytest.fixture(autouse=True)
def clear_session_cache() -> Generator[None, None, None]:
    """Clear lru_cache on _get_session before and after each test.

    Yields:
        None.
    """
    ApiCall._get_session.cache_clear()
    yield
    ApiCall._get_session.cache_clear()


@pytest.fixture
def api_call() -> ApiCall:
    """Return a minimal ApiCall instance.

    Returns:
        A minimal ApiCall instance for testing.
    """
    return ApiCall(access_token=ACCESS_TOKEN, url=BASE_URL)
