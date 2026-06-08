"""Tests for pyado.raw.service_endpoint — service endpoint wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch
from uuid import UUID

import pydantic
import pytest
import requests

from pyado.raw import (
    ApiCall,
    ServiceEndpointInfo,
    iter_service_endpoints,
    list_service_endpoints,
)
from tests.conftest import _make_mock_response

_ENDPOINT_ID = "11111111-2222-3333-4444-555555555555"


class TestListServiceEndpoints:
    @staticmethod
    def test_returns_list_of_service_endpoints(api_call: ApiCall) -> None:
        payload = {
            "count": 1,
            "value": [
                {
                    "id": _ENDPOINT_ID,
                    "name": "MyServiceConnection",
                    "type": "azurerm",
                    "url": "https://management.azure.com/",
                    "isShared": False,
                    "isReady": True,
                    "owner": "Library",
                    "description": "Azure RM connection",
                    "authorization": {"scheme": "WorkloadIdentityFederation"},
                }
            ],
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_service_endpoints(api_call)
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], ServiceEndpointInfo)
        assert results[0].id == UUID(_ENDPOINT_ID)
        assert results[0].name == "MyServiceConnection"
        assert results[0].type == "azurerm"
        assert results[0].is_ready is True
        assert results[0].is_shared is False
        assert results[0].authorization_scheme == "WorkloadIdentityFederation"

    @staticmethod
    def test_authorization_scheme_is_none_when_not_present(
        api_call: ApiCall,
    ) -> None:
        payload = {
            "value": [
                {
                    "id": _ENDPOINT_ID,
                    "name": "Endpoint",
                    "type": "generic",
                    "url": "https://example.com/",
                }
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_service_endpoints(api_call)
        assert results[0].authorization_scheme is None

    @staticmethod
    def test_returns_empty_list_when_no_endpoints(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"count": 0, "value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_service_endpoints(api_call)
        assert results == []


class TestServiceEndpointInfoValidator:
    @staticmethod
    def test_non_dict_data_passes_through() -> None:
        with pytest.raises(pydantic.ValidationError):
            ServiceEndpointInfo.model_validate([])


class TestIterServiceEndpoints:
    @staticmethod
    def test_yields_service_endpoints(api_call: ApiCall) -> None:
        payload = {
            "value": [
                {
                    "id": _ENDPOINT_ID,
                    "name": "NuGet",
                    "type": "externalnugetfeed",
                    "url": "https://nuget.org/",
                    "authorization": {"scheme": "Token"},
                }
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(iter_service_endpoints(api_call))
        assert len(results) == 1
        assert results[0].authorization_scheme == "Token"
