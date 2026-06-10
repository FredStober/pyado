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
    ServiceEndpointAuthorization,
    ServiceEndpointCreateRequest,
    ServiceEndpointId,
    ServiceEndpointInfo,
    ServiceEndpointProjectReference,
    ServiceEndpointUpdateRequest,
    delete_service_endpoint,
    get_service_endpoint,
    iter_service_endpoints,
    list_service_endpoints,
    patch_service_endpoint_share,
    post_service_endpoint,
    put_service_endpoint,
)
from tests.conftest import _make_mock_response

_ENDPOINT_ID = "11111111-2222-3333-4444-555555555555"
_PROJECT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

_ENDPOINT_PAYLOAD = {
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


class TestGetServiceEndpoint:
    @staticmethod
    def test_returns_service_endpoint_info(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_ENDPOINT_PAYLOAD)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            result = get_service_endpoint(api_call, UUID(_ENDPOINT_ID))
        assert isinstance(result, ServiceEndpointInfo)
        assert result.id == UUID(_ENDPOINT_ID)
        assert result.name == "MyServiceConnection"
        assert result.type == "azurerm"
        assert result.authorization_scheme == "WorkloadIdentityFederation"
        called_url: str = mock_req.call_args.kwargs["url"]
        assert _ENDPOINT_ID in called_url

    @staticmethod
    def test_endpoint_id_appears_in_url(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_ENDPOINT_PAYLOAD)
        endpoint_id = UUID(_ENDPOINT_ID)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            get_service_endpoint(api_call, endpoint_id)
        called_url: str = mock_req.call_args.kwargs["url"]
        assert str(endpoint_id) in called_url


class TestPostServiceEndpoint:
    @staticmethod
    def _make_request() -> ServiceEndpointCreateRequest:
        return ServiceEndpointCreateRequest(
            name="MyConnection",
            type="azurerm",
            url="https://management.azure.com/",
            authorization=ServiceEndpointAuthorization(
                scheme="WorkloadIdentityFederation",
                parameters={},
            ),
            service_endpoint_project_references=[
                ServiceEndpointProjectReference.model_validate(
                    {
                        "projectReference": {"id": _PROJECT_ID, "name": "MyProject"},
                        "name": "MyConnection",
                    }
                )
            ],
        )

    @staticmethod
    def test_returns_service_endpoint_info(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_ENDPOINT_PAYLOAD)
        request = TestPostServiceEndpoint._make_request()
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = post_service_endpoint(api_call, request)
        assert isinstance(result, ServiceEndpointInfo)
        assert result.id == UUID(_ENDPOINT_ID)

    @staticmethod
    def test_sends_json_body(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_ENDPOINT_PAYLOAD)
        request = TestPostServiceEndpoint._make_request()
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            post_service_endpoint(api_call, request)
        sent_json = mock_req.call_args.kwargs["json"]
        assert sent_json["name"] == "MyConnection"
        assert sent_json["type"] == "azurerm"
        assert "serviceEndpointProjectReferences" in sent_json


class TestPutServiceEndpoint:
    @staticmethod
    def _make_request() -> ServiceEndpointUpdateRequest:
        return ServiceEndpointUpdateRequest(
            id=UUID(_ENDPOINT_ID),
            name="UpdatedConnection",
            type="azurerm",
            url="https://management.azure.com/",
            authorization=ServiceEndpointAuthorization(
                scheme="WorkloadIdentityFederation",
                parameters={},
            ),
            service_endpoint_project_references=[
                ServiceEndpointProjectReference.model_validate(
                    {
                        "projectReference": {"id": _PROJECT_ID, "name": "MyProject"},
                        "name": "UpdatedConnection",
                    }
                )
            ],
        )

    @staticmethod
    def test_returns_updated_info(api_call: ApiCall) -> None:
        updated_payload = {**_ENDPOINT_PAYLOAD, "name": "UpdatedConnection"}
        mock_resp = _make_mock_response(updated_payload)
        request = TestPutServiceEndpoint._make_request()
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = put_service_endpoint(api_call, UUID(_ENDPOINT_ID), request)
        assert isinstance(result, ServiceEndpointInfo)
        assert result.name == "UpdatedConnection"

    @staticmethod
    def test_endpoint_id_in_url(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_ENDPOINT_PAYLOAD)
        request = TestPutServiceEndpoint._make_request()
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            put_service_endpoint(api_call, UUID(_ENDPOINT_ID), request)
        called_url: str = mock_req.call_args.kwargs["url"]
        assert _ENDPOINT_ID in called_url

    @staticmethod
    def test_sends_json_body(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(_ENDPOINT_PAYLOAD)
        request = TestPutServiceEndpoint._make_request()
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            put_service_endpoint(api_call, UUID(_ENDPOINT_ID), request)
        sent_json = mock_req.call_args.kwargs["json"]
        assert sent_json["id"] == _ENDPOINT_ID
        assert "serviceEndpointProjectReferences" in sent_json


class TestDeleteServiceEndpoint:
    @staticmethod
    def test_sends_delete_request(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        endpoint_id = UUID(_ENDPOINT_ID)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_service_endpoint(api_call, endpoint_id, [_PROJECT_ID])
        assert mock_req.call_args.args[0] == "DELETE"

    @staticmethod
    def test_project_ids_in_query_params(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        endpoint_id = UUID(_ENDPOINT_ID)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_service_endpoint(api_call, endpoint_id, [_PROJECT_ID])
        params = mock_req.call_args.kwargs["params"]
        assert params["projectIds"] == _PROJECT_ID

    @staticmethod
    def test_multiple_project_ids_joined(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        other_project = "ffffffff-eeee-dddd-cccc-bbbbbbbbbbbb"
        endpoint_id = UUID(_ENDPOINT_ID)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_service_endpoint(api_call, endpoint_id, [_PROJECT_ID, other_project])
        params = mock_req.call_args.kwargs["params"]
        assert params["projectIds"] == f"{_PROJECT_ID},{other_project}"

    @staticmethod
    def test_endpoint_id_in_url(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        endpoint_id = UUID(_ENDPOINT_ID)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_service_endpoint(api_call, endpoint_id, [_PROJECT_ID])
        called_url: str = mock_req.call_args.kwargs["url"]
        assert _ENDPOINT_ID in called_url


class TestPatchServiceEndpointShare:
    @staticmethod
    def _make_ref(
        project_id: str = _PROJECT_ID, name: str = "Shared"
    ) -> ServiceEndpointProjectReference:
        return ServiceEndpointProjectReference.model_validate(
            {
                "projectReference": {"id": project_id, "name": "OtherProject"},
                "name": name,
            }
        )

    @staticmethod
    def test_sends_patch_request(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        endpoint_id: ServiceEndpointId = UUID(_ENDPOINT_ID)
        ref = TestPatchServiceEndpointShare._make_ref()
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            patch_service_endpoint_share(api_call, endpoint_id, [ref])
        assert mock_req.call_args.args[0] == "PATCH"

    @staticmethod
    def test_sends_list_of_project_references(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        endpoint_id: ServiceEndpointId = UUID(_ENDPOINT_ID)
        ref = TestPatchServiceEndpointShare._make_ref()
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            patch_service_endpoint_share(api_call, endpoint_id, [ref])
        sent_json = mock_req.call_args.kwargs["json"]
        assert isinstance(sent_json, list)
        assert len(sent_json) == 1
        assert sent_json[0]["name"] == "Shared"
        assert "projectReference" in sent_json[0]

    @staticmethod
    def test_endpoint_id_in_url(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        endpoint_id: ServiceEndpointId = UUID(_ENDPOINT_ID)
        ref = TestPatchServiceEndpointShare._make_ref()
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            patch_service_endpoint_share(api_call, endpoint_id, [ref])
        called_url: str = mock_req.call_args.kwargs["url"]
        assert _ENDPOINT_ID in called_url
