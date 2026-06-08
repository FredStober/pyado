"""Tests for work item type and category additions to pyado.raw.boards.work_item."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch

import requests

from pyado.raw import (
    ApiCall,
    WorkItemFieldInfo,
    WorkItemStateInfo,
    WorkItemTypeCategoryInfo,
    WorkItemTypeIcon,
    WorkItemTypeInfo,
    iter_work_item_type_categories,
    iter_work_item_type_fields,
    iter_work_item_type_states,
    iter_work_item_types,
    list_work_item_type_categories,
    list_work_item_type_fields,
    list_work_item_type_states,
    list_work_item_types,
)
from tests.conftest import _make_mock_response


class TestListWorkItemTypes:
    @staticmethod
    def test_returns_list_of_work_item_types(api_call: ApiCall) -> None:
        payload = {
            "count": 2,
            "value": [
                {
                    "name": "Bug",
                    "referenceName": "Microsoft.VSTS.WorkItemTypes.Bug",
                    "description": "Tracks a defect",
                    "color": "CC293D",
                    "isDisabled": False,
                },
                {
                    "name": "Task",
                    "referenceName": "Microsoft.VSTS.WorkItemTypes.Task",
                    "description": "Tracks a unit of work",
                    "color": "F2CB1D",
                    "isDisabled": False,
                },
            ],
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_work_item_types(api_call)
        assert isinstance(results, list)
        assert len(results) == 2
        assert isinstance(results[0], WorkItemTypeInfo)
        assert results[0].name == "Bug"
        assert results[0].reference_name == "Microsoft.VSTS.WorkItemTypes.Bug"
        assert results[0].color == "CC293D"
        assert results[0].is_disabled is False

    @staticmethod
    def test_returns_empty_list_when_no_types(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"count": 0, "value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_work_item_types(api_call)
        assert results == []

    @staticmethod
    def test_optional_fields_default_correctly(api_call: ApiCall) -> None:
        payload = {
            "value": [
                {
                    "name": "Feature",
                    "referenceName": "Microsoft.VSTS.WorkItemTypes.Feature",
                }
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_work_item_types(api_call)
        assert not results[0].description
        assert results[0].color is None
        assert results[0].icon is None

    @staticmethod
    def test_icon_parsed_as_object(api_call: ApiCall) -> None:
        payload = {
            "value": [
                {
                    "name": "Bug",
                    "referenceName": "Microsoft.VSTS.WorkItemTypes.Bug",
                    "icon": {
                        "id": "icon_insect",
                        "url": "https://dev.azure.com/_apis/wit/workItemIcons/icon_insect",
                    },
                }
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_work_item_types(api_call)
        assert isinstance(results[0].icon, WorkItemTypeIcon)
        assert results[0].icon.id == "icon_insect"

    @staticmethod
    def test_reference_name_optional(api_call: ApiCall) -> None:
        payload = {
            "value": [
                {
                    "name": "Bug",
                }
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_work_item_types(api_call)
        assert not results[0].reference_name


class TestIterWorkItemTypes:
    @staticmethod
    def test_yields_work_item_types(api_call: ApiCall) -> None:
        payload = {
            "value": [
                {"name": "Epic", "referenceName": "Microsoft.VSTS.WorkItemTypes.Epic"}
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(iter_work_item_types(api_call))
        assert len(results) == 1
        assert isinstance(results[0], WorkItemTypeInfo)


class TestListWorkItemTypeStates:
    @staticmethod
    def test_returns_list_of_states(api_call: ApiCall) -> None:
        payload = {
            "count": 3,
            "value": [
                {
                    "name": "Active",
                    "color": "007ACC",
                    "stateCategory": "InProgress",
                    "order": 1,
                },
                {
                    "name": "Resolved",
                    "color": "FF9D00",
                    "stateCategory": "Resolved",
                    "order": 2,
                },
                {
                    "name": "Closed",
                    "color": "339933",
                    "stateCategory": "Completed",
                    "order": 3,
                },
            ],
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_work_item_type_states(api_call, "Bug")
        assert isinstance(results, list)
        assert len(results) == 3
        assert isinstance(results[0], WorkItemStateInfo)
        assert results[0].name == "Active"
        assert results[0].state_category == "InProgress"
        assert results[0].order == 1

    @staticmethod
    def test_returns_empty_list_when_no_states(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"count": 0, "value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_work_item_type_states(api_call, "Bug")
        assert results == []


class TestIterWorkItemTypeStates:
    @staticmethod
    def test_yields_states(api_call: ApiCall) -> None:
        payload = {
            "count": 1,
            "value": [
                {
                    "name": "Active",
                    "color": "007ACC",
                    "stateCategory": "InProgress",
                    "order": 1,
                }
            ],
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(iter_work_item_type_states(api_call, "Bug"))
        assert len(results) == 1
        assert isinstance(results[0], WorkItemStateInfo)


class TestListWorkItemTypeFields:
    @staticmethod
    def test_returns_list_of_fields(api_call: ApiCall) -> None:
        payload = {
            "count": 2,
            "value": [
                {
                    "name": "Title",
                    "referenceName": "System.Title",
                    "type": "string",
                    "readOnly": False,
                    "required": True,
                },
                {
                    "name": "Priority",
                    "referenceName": "Microsoft.VSTS.Common.Priority",
                    "type": "integer",
                    "readOnly": False,
                    "required": False,
                    "defaultValue": "2",
                },
            ],
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_work_item_type_fields(api_call, "Bug")
        assert isinstance(results, list)
        assert len(results) == 2
        assert isinstance(results[0], WorkItemFieldInfo)
        assert results[0].name == "Title"
        assert results[0].required is True
        assert results[1].default_value == "2"

    @staticmethod
    def test_returns_empty_list_when_no_fields(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"count": 0, "value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_work_item_type_fields(api_call, "Task")
        assert results == []


class TestIterWorkItemTypeFields:
    @staticmethod
    def test_yields_fields(api_call: ApiCall) -> None:
        payload = {
            "count": 1,
            "value": [
                {
                    "name": "Title",
                    "referenceName": "System.Title",
                    "type": "string",
                    "readOnly": False,
                    "required": True,
                }
            ],
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(iter_work_item_type_fields(api_call, "Bug"))
        assert len(results) == 1
        assert isinstance(results[0], WorkItemFieldInfo)


class TestListWorkItemTypeCategories:
    @staticmethod
    def test_returns_list_of_categories(api_call: ApiCall) -> None:
        payload = {
            "count": 1,
            "value": [
                {
                    "name": "Bug Category",
                    "referenceName": "Microsoft.BugCategory",
                    "defaultWorkItemType": {
                        "name": "Bug",
                        "referenceName": "Microsoft.VSTS.WorkItemTypes.Bug",
                    },
                    "workItemTypes": [
                        {
                            "name": "Bug",
                            "referenceName": "Microsoft.VSTS.WorkItemTypes.Bug",
                        }
                    ],
                }
            ],
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_work_item_type_categories(api_call)
        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], WorkItemTypeCategoryInfo)
        assert results[0].name == "Bug Category"
        assert results[0].reference_name == "Microsoft.BugCategory"
        assert results[0].default_work_item_type is not None
        assert results[0].default_work_item_type.name == "Bug"
        assert len(results[0].work_item_types) == 1

    @staticmethod
    def test_returns_empty_list_when_no_categories(api_call: ApiCall) -> None:
        payload: dict[str, object] = {"count": 0, "value": []}
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_work_item_type_categories(api_call)
        assert results == []

    @staticmethod
    def test_category_without_default_work_item_type(api_call: ApiCall) -> None:
        payload = {
            "value": [
                {
                    "name": "Hidden Types",
                    "referenceName": "Microsoft.HiddenCategory",
                    "workItemTypes": [],
                }
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_work_item_type_categories(api_call)
        assert results[0].default_work_item_type is None
        assert results[0].work_item_types == []

    @staticmethod
    def test_category_type_refs_without_reference_name(api_call: ApiCall) -> None:
        # ADO omits referenceName in embedded type refs within category results.
        payload = {
            "value": [
                {
                    "name": "Bug Category",
                    "referenceName": "Microsoft.BugCategory",
                    "defaultWorkItemType": {
                        "name": "Bug",
                        "url": "https://dev.azure.com/org/proj/_apis/wit/workItemTypes/Bug",
                    },
                    "workItemTypes": [
                        {
                            "name": "Bug",
                            "url": "https://dev.azure.com/org/proj/_apis/wit/workItemTypes/Bug",
                        }
                    ],
                }
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list_work_item_type_categories(api_call)
        assert results[0].default_work_item_type is not None
        assert results[0].default_work_item_type.name == "Bug"
        assert not results[0].default_work_item_type.reference_name
        assert len(results[0].work_item_types) == 1
        assert not results[0].work_item_types[0].reference_name


class TestIterWorkItemTypeCategories:
    @staticmethod
    def test_yields_categories(api_call: ApiCall) -> None:
        payload = {
            "value": [
                {
                    "name": "RequirementCategory",
                    "referenceName": "Microsoft.RequirementCategory",
                }
            ]
        }
        mock_resp = _make_mock_response(payload)
        with patch.object(requests.Session, "request", return_value=mock_resp):
            results = list(iter_work_item_type_categories(api_call))
        assert len(results) == 1
        assert isinstance(results[0], WorkItemTypeCategoryInfo)
