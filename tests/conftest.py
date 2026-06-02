"""Shared fixtures for pyado test suite."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import json
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
import requests

from pyado import ApiCall

BASE_URL = "https://dev.azure.com/org/"
ACCESS_TOKEN = "test_token"
NOW_ISO = "2024-01-15T12:00:00+00:00"


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


def _make_mock_response(json_data: Any = None) -> MagicMock:
    """Create a minimal mock HTTP response.

    Returns:
        A MagicMock configured to behave as a requests.Response.
    """
    mock = MagicMock(spec=requests.Response)
    mock.raise_for_status.return_value = None
    if json_data is not None:
        mock.json.return_value = json_data
        mock.content = json.dumps(json_data).encode()
    else:
        mock.content = b""
        mock.json.side_effect = ValueError("empty")
    return mock


def make_build_record_dict(**overrides: Any) -> dict[str, Any]:
    """Create a minimal valid BuildRecordInfo dict.

    Returns:
        A dict with all required BuildRecordInfo fields populated.
    """
    record: dict[str, Any] = {
        "attempt": 1,
        "changeId": None,
        "currentOperation": None,
        "details": None,
        "finishTime": NOW_ISO,
        "id": str(uuid4()),
        "identifier": None,
        "lastModified": NOW_ISO,
        "log": None,
        "name": "Test Task",
        "refName": None,
        "parentId": None,
        "percentComplete": None,
        "previousAttempts": [],
        "result": None,
        "resultCode": None,
        "startTime": None,
        "state": "pending",
        "task": None,
        "type": "Task",
        "url": None,
        "workerName": None,
    }
    record.update(overrides)
    return record
