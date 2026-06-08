"""Shared fixtures for integration tests (require a live ADO instance)."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import datetime
import pathlib
import random

import pytest

from pyado import raw
from tests.integration.raw._support import _load_config

_CFG_PATH = pathlib.Path("test.json")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Skip all integration tests when test.json is not present."""
    if _CFG_PATH.exists():
        return
    skip = pytest.mark.skip(reason="test.json not found — no ADO credentials available")
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(skip)


@pytest.fixture(scope="session")
def ado_config() -> tuple[str, str, str]:
    """Return (org_url, project_name, access_token) from test.json."""
    return _load_config()


@pytest.fixture(scope="session")
def token(ado_config: tuple[str, str, str]) -> str:
    """Return the ADO access token."""
    _, _, tok = ado_config
    return tok


@pytest.fixture(scope="session")
def org_url(ado_config: tuple[str, str, str]) -> str:
    """Return the ADO organisation URL."""
    url, _, _ = ado_config
    return url


@pytest.fixture(scope="session")
def project_name(ado_config: tuple[str, str, str]) -> str:
    """Return the ADO project name."""
    _, name, _ = ado_config
    return name


@pytest.fixture(scope="session")
def org_api_call(token: str, org_url: str) -> raw.ApiCall:
    """Return an org-level ApiCall."""
    session = raw.get_session(pat=token)
    return raw.ApiCall(session=session, url=f"{org_url}/_apis")


@pytest.fixture(scope="session")
def project_api_call(
    token: str,
    org_url: str,
    project_name: str,
) -> raw.ApiCall:
    """Return a project-level ApiCall."""
    session = raw.get_session(pat=token)
    return raw.ApiCall(session=session, url=f"{org_url}/{project_name}/_apis")


@pytest.fixture(scope="session")
def rng() -> random.Random:
    """Return a seeded random number generator."""
    return random.Random(42)


@pytest.fixture(scope="session")
def run_ts() -> str:
    """Return a UTC timestamp string for use in test artifact names."""
    return datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S")
