"""Integration tests for service endpoint endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado import raw
from tests.integration.raw._support import console


def test_service_endpoint_read(
    project_api_call: raw.ApiCall,
) -> None:
    """List service endpoints."""
    console.print("\n=== SERVICE ENDPOINT (read) ===")
    endpoints = list(raw.iter_service_endpoints(project_api_call))
    assert endpoints == raw.list_service_endpoints(project_api_call)
