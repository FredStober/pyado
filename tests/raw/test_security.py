"""Tests for pyado.raw.core.security — namespace ACL wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import Any
from unittest.mock import patch

import requests

from pyado.raw._core import ApiCall
from pyado.raw.core.security import (
    AceEntry,
    delete_namespace_acl,
    get_identities_by_descriptor,
    get_identities_by_subject_descriptor,
    get_namespace_acl,
    get_namespace_actions,
    get_namespace_names,
    post_namespace_acl,
)
from tests.conftest import _make_mock_response

_NS_ID = "2e9eb7ed-3c0a-47d4-87c1-0ffdd275fd87"
_TOKEN = "repoV2/proj-guid/repo-guid"
_DESCRIPTOR = "aad.dXNlcjEyMw=="
_STORAGE_KEY = "Microsoft.TeamFoundation.Identity;S-1-9-1234"
_SUBJECT_DESC = "aad.dXNlcjEyMw"


class TestGetNamespaceNames:
    @staticmethod
    def test_returns_name_to_guid_map(api_call: ApiCall) -> None:
        payload: dict[str, Any] = {
            "value": [
                {"name": "Git Repositories", "namespaceId": _NS_ID},
                {"name": "Build", "namespaceId": "build-ns-guid"},
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_namespace_names(api_call)
        assert result["git repositories"] == _NS_ID
        assert result["build"] == "build-ns-guid"

    @staticmethod
    def test_skips_entries_missing_name_or_guid(api_call: ApiCall) -> None:
        payload: dict[str, Any] = {
            "value": [
                {"name": "Valid", "namespaceId": _NS_ID},
                {"name": "NoGuid"},
                {"namespaceId": "no-name-guid"},
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_namespace_names(api_call)
        assert len(result) == 1
        assert "valid" in result

    @staticmethod
    def test_returns_empty_when_no_response(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_namespace_names(api_call)
        assert result == {}


class TestGetNamespaceActions:
    @staticmethod
    def test_returns_name_to_bit_map(api_call: ApiCall) -> None:
        payload: dict[str, Any] = {
            "value": [
                {
                    "actions": [
                        {"name": "GenericRead", "bit": 1},
                        {"name": "ForcePush", "bit": 8},
                    ]
                }
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_namespace_actions(api_call, _NS_ID)
        assert result["GenericRead"] == 1
        assert result["ForcePush"] == 8

    @staticmethod
    def test_normalises_upper_snake_to_pascal(api_call: ApiCall) -> None:
        payload: dict[str, Any] = {
            "value": [
                {
                    "actions": [
                        {"name": "GENERIC_READ", "bit": 1},
                        {"name": "WORK_ITEM_DELETE", "bit": 4},
                    ]
                }
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_namespace_actions(api_call, _NS_ID)
        assert result["GenericRead"] == 1
        assert result["WorkItemDelete"] == 4

    @staticmethod
    def test_returns_empty_when_no_ns_list(api_call: ApiCall) -> None:
        payload: dict[str, Any] = {"value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_namespace_actions(api_call, _NS_ID)
        assert result == {}


class TestGetIdentitiesBySubjectDescriptor:
    @staticmethod
    def test_returns_subject_to_storage_key_map(api_call: ApiCall) -> None:
        payload: dict[str, Any] = {
            "value": [
                {
                    "subjectDescriptor": _SUBJECT_DESC,
                    "descriptor": _STORAGE_KEY,
                }
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_identities_by_subject_descriptor(api_call, [_SUBJECT_DESC])
        assert result[_SUBJECT_DESC] == _STORAGE_KEY

    @staticmethod
    def test_skips_items_missing_fields(api_call: ApiCall) -> None:
        payload: dict[str, Any] = {
            "value": [
                {"subjectDescriptor": _SUBJECT_DESC},
                {"descriptor": _STORAGE_KEY},
                {},
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_identities_by_subject_descriptor(api_call, [_SUBJECT_DESC])
        assert result == {}

    @staticmethod
    def test_returns_empty_when_no_descriptors(api_call: ApiCall) -> None:
        result = get_identities_by_subject_descriptor(api_call, [])
        assert result == {}


class TestGetIdentitiesByDescriptor:
    @staticmethod
    def test_returns_storage_key_to_subject_map(api_call: ApiCall) -> None:
        payload: dict[str, Any] = {
            "value": [
                {
                    "descriptor": _STORAGE_KEY,
                    "subjectDescriptor": _SUBJECT_DESC,
                }
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_identities_by_descriptor(api_call, [_STORAGE_KEY])
        assert result[_STORAGE_KEY] == _SUBJECT_DESC

    @staticmethod
    def test_skips_items_missing_fields(api_call: ApiCall) -> None:
        payload: dict[str, Any] = {
            "value": [
                {"descriptor": _STORAGE_KEY},
                {"subjectDescriptor": _SUBJECT_DESC},
                {},
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_identities_by_descriptor(api_call, [_STORAGE_KEY])
        assert result == {}

    @staticmethod
    def test_returns_empty_when_no_keys(api_call: ApiCall) -> None:
        result = get_identities_by_descriptor(api_call, [])
        assert result == {}


class TestGetNamespaceAcl:
    @staticmethod
    def test_returns_ace_entries(api_call: ApiCall) -> None:
        payload: dict[str, Any] = {
            "value": [
                {
                    "acesDictionary": {
                        _DESCRIPTOR: {
                            "descriptor": _DESCRIPTOR,
                            "allow": 3,
                            "deny": 0,
                        }
                    }
                }
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_namespace_acl(api_call, _NS_ID, _TOKEN)
        assert len(result) == 1
        assert isinstance(result[0], AceEntry)
        assert result[0].descriptor == _DESCRIPTOR
        assert result[0].allow == 3
        assert result[0].deny == 0

    @staticmethod
    def test_returns_empty_when_no_response(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_namespace_acl(api_call, _NS_ID, _TOKEN)
        assert result == []

    @staticmethod
    def test_returns_empty_when_empty_value(api_call: ApiCall) -> None:
        payload: dict[str, Any] = {"value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            result = get_namespace_acl(api_call, _NS_ID, _TOKEN)
        assert result == []


class TestPostNamespaceAcl:
    @staticmethod
    def test_sends_two_requests_when_aces_present(api_call: ApiCall) -> None:
        aces = [AceEntry(descriptor=_DESCRIPTOR, allow=3, deny=0)]
        mock_resp = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            post_namespace_acl(api_call, _NS_ID, _TOKEN, aces)
        assert mock_req.call_count == 2

    @staticmethod
    def test_sends_one_request_when_no_aces(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            post_namespace_acl(api_call, _NS_ID, _TOKEN, [])
        assert mock_req.call_count == 1


class TestDeleteNamespaceAcl:
    @staticmethod
    def test_sends_delete_request(api_call: ApiCall) -> None:
        mock_resp = _make_mock_response(None)
        with patch.object(
            requests.Session, "request", return_value=mock_resp
        ) as mock_req:
            delete_namespace_acl(api_call, _NS_ID, _TOKEN)
        assert mock_req.call_args.args[0] == "DELETE"
