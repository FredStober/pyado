"""Tests for pyado.oop ServiceEndpoint and ProjectPipelines service endpoint methods."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from pyado.oop.settings.service_endpoint import ServiceEndpoint
from pyado.raw import (
    ServiceEndpointAuthorization,
    ServiceEndpointCreateRequest,
    ServiceEndpointInfo,
    ServiceEndpointProjectReference,
    ServiceEndpointUpdateRequest,
)
from tests.oop.conftest import (
    PROJECT_ID,
    _make_project,
)

# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------

_PROJECT_ID_STR = str(PROJECT_ID)


def _endpoint_info(name: str = "GitHub Connection") -> ServiceEndpointInfo:
    return ServiceEndpointInfo.model_validate(
        {
            "id": str(uuid4()),
            "name": name,
            "type": "github",
            "url": "https://github.com",
            "isShared": False,
            "isReady": True,
            "authorization": {"scheme": "Token"},
        }
    )


def _make_endpoint(name: str = "GitHub Connection") -> ServiceEndpoint:
    return ServiceEndpoint(_make_project(), _endpoint_info(name))


def _make_update_request(
    endpoint_id: UUID, name: str = "Updated"
) -> ServiceEndpointUpdateRequest:
    return ServiceEndpointUpdateRequest(
        id=endpoint_id,
        name=name,
        type="github",
        url="https://github.com",
        authorization=ServiceEndpointAuthorization(scheme="Token"),
        service_endpoint_project_references=[
            ServiceEndpointProjectReference.model_validate(
                {
                    "projectReference": {
                        "id": _PROJECT_ID_STR,
                        "name": "TestProject",
                    },
                    "name": name,
                }
            )
        ],
    )


def _make_create_request(name: str = "NewConnection") -> ServiceEndpointCreateRequest:
    return ServiceEndpointCreateRequest(
        name=name,
        type="github",
        url="https://github.com",
        authorization=ServiceEndpointAuthorization(scheme="Token"),
        service_endpoint_project_references=[
            ServiceEndpointProjectReference.model_validate(
                {
                    "projectReference": {
                        "id": _PROJECT_ID_STR,
                        "name": "TestProject",
                    },
                    "name": name,
                }
            )
        ],
    )


# ---------------------------------------------------------------------------
# ServiceEndpoint class
# ---------------------------------------------------------------------------


class TestServiceEndpointProperties:
    def _make_ep(self) -> ServiceEndpoint:
        return _make_endpoint()

    def test_id_returns_uuid(self) -> None:
        info = _endpoint_info()
        ep = ServiceEndpoint(_make_project(), info)
        assert ep.id == info.id

    def test_name_returns_name(self) -> None:
        info = _endpoint_info("My GitHub")
        ep = ServiceEndpoint(_make_project(), info)
        assert ep.name == "My GitHub"

    def test_type_returns_type_string(self) -> None:
        ep = self._make_ep()
        assert ep.type == "github"

    def test_url_returns_url(self) -> None:
        ep = self._make_ep()
        assert ep.url == "https://github.com"

    def test_is_ready_returns_bool(self) -> None:
        ep = self._make_ep()
        assert ep.is_ready is True

    def test_is_shared_returns_bool(self) -> None:
        ep = self._make_ep()
        assert ep.is_shared is False

    def test_authorization_scheme_returns_scheme(self) -> None:
        ep = self._make_ep()
        assert ep.authorization_scheme == "Token"

    def test_authorization_scheme_none_when_absent(self) -> None:
        info = ServiceEndpointInfo.model_validate(
            {
                "id": str(uuid4()),
                "name": "NoAuth",
                "type": "external",
                "url": "https://example.com",
            }
        )
        ep = ServiceEndpoint(_make_project(), info)
        assert ep.authorization_scheme is None

    def test_info_returns_stored_info(self) -> None:
        info = _endpoint_info()
        ep = ServiceEndpoint(_make_project(), info)
        assert ep.info is info

    def test_project_back_reference(self) -> None:
        proj = _make_project()
        ep = ServiceEndpoint(proj, _endpoint_info())
        assert ep.project is proj

    def test_org_back_reference(self) -> None:
        proj = _make_project()
        ep = ServiceEndpoint(proj, _endpoint_info())
        assert ep.org is proj.org


class TestServiceEndpointRefresh:
    def test_refresh_clears_info(self) -> None:
        ep = ServiceEndpoint(_make_project(), _endpoint_info())
        ep.refresh()
        assert ep._info is None

    def test_info_re_fetches_after_refresh_matching_id(self) -> None:
        proj = _make_project()
        info = _endpoint_info()
        ep = ServiceEndpoint(proj, info)
        ep.refresh()
        with patch(
            "pyado.oop.settings.service_endpoint.raw.iter_service_endpoints"
        ) as mock_iter:
            mock_iter.return_value = iter([info])
            result = ep.info
        assert result is info

    def test_info_raises_key_error_when_not_found_after_refresh(self) -> None:
        proj = _make_project()
        info = _endpoint_info()
        ep = ServiceEndpoint(proj, info)
        ep.refresh()
        other_info = _endpoint_info("OtherEndpoint")
        with patch(
            "pyado.oop.settings.service_endpoint.raw.iter_service_endpoints"
        ) as mock_iter:
            mock_iter.return_value = iter([other_info])
            with pytest.raises(KeyError):
                _ = ep.info


class TestServiceEndpointUpdate:
    def test_update_refreshes_cached_info(self) -> None:
        info = _endpoint_info()
        proj = _make_project()
        ep = ServiceEndpoint(proj, info)
        updated_info = _endpoint_info("Updated")
        request = _make_update_request(info.id, "Updated")
        with patch(
            "pyado.oop.settings.service_endpoint.raw.put_service_endpoint",
            return_value=updated_info,
        ) as mock_put:
            ep.update(request)
        mock_put.assert_called_once_with(proj.org.api_call, info.id, request)
        assert ep._info is updated_info

    def test_update_uses_org_api_call(self) -> None:
        info = _endpoint_info()
        proj = _make_project()
        ep = ServiceEndpoint(proj, info)
        request = _make_update_request(info.id)
        captured: list[object] = []

        def _side_effect(
            api_call: object, *_a: object, **_kw: object
        ) -> ServiceEndpointInfo:
            captured.append(api_call)
            return _endpoint_info()

        with patch(
            "pyado.oop.settings.service_endpoint.raw.put_service_endpoint",
            side_effect=_side_effect,
        ):
            ep.update(request)
        assert captured[0] is proj.org.api_call


class TestServiceEndpointDelete:
    def test_delete_calls_raw_with_project_id(self) -> None:
        info = _endpoint_info()
        proj = _make_project()
        ep = ServiceEndpoint(proj, info)
        with patch(
            "pyado.oop.settings.service_endpoint.raw.delete_service_endpoint"
        ) as mock_del:
            ep.delete()
        mock_del.assert_called_once_with(proj.api_call, info.id, [str(proj.id)])

    def test_delete_uses_project_api_call(self) -> None:
        info = _endpoint_info()
        proj = _make_project()
        ep = ServiceEndpoint(proj, info)
        captured: list[object] = []
        with patch(
            "pyado.oop.settings.service_endpoint.raw.delete_service_endpoint",
            side_effect=lambda api_call, *_a, **_kw: captured.append(api_call),
        ):
            ep.delete()
        assert captured[0] is proj.api_call


class TestServiceEndpointShare:
    def test_share_calls_raw_with_org_api_call(self) -> None:
        info = _endpoint_info()
        proj = _make_project()
        ep = ServiceEndpoint(proj, info)
        ref = ServiceEndpointProjectReference.model_validate(
            {
                "projectReference": {"id": str(uuid4()), "name": "Other"},
                "name": "Shared",
            }
        )
        with patch(
            "pyado.oop.settings.service_endpoint.raw.patch_service_endpoint_share"
        ) as mock_share:
            ep.share([ref])
        mock_share.assert_called_once_with(proj.org.api_call, info.id, [ref])

    def test_share_uses_org_api_call(self) -> None:
        info = _endpoint_info()
        proj = _make_project()
        ep = ServiceEndpoint(proj, info)
        ref = ServiceEndpointProjectReference.model_validate(
            {
                "projectReference": {"id": str(uuid4()), "name": "Other"},
                "name": "Shared",
            }
        )
        captured: list[object] = []
        with patch(
            "pyado.oop.settings.service_endpoint.raw.patch_service_endpoint_share",
            side_effect=lambda api_call, *_a, **_kw: captured.append(api_call),
        ):
            ep.share([ref])
        assert captured[0] is proj.org.api_call


# ---------------------------------------------------------------------------
# ProjectPipelines service endpoint methods
# ---------------------------------------------------------------------------


class TestProjectPipelinesServiceEndpoints:
    def test_iter_service_endpoints_yields_wrappers(self) -> None:
        proj = _make_project()
        info = _endpoint_info()
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.iter_service_endpoints"
        ) as mock_iter:
            mock_iter.return_value = iter([info])
            result = list(proj.pipelines.iter_service_endpoints())
        assert len(result) == 1
        assert isinstance(result[0], ServiceEndpoint)
        assert result[0].name == info.name

    def test_iter_service_endpoints_empty(self) -> None:
        proj = _make_project()
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.iter_service_endpoints"
        ) as mock_iter:
            mock_iter.return_value = iter([])
            result = list(proj.pipelines.iter_service_endpoints())
        assert result == []

    def test_list_service_endpoints_delegates(self) -> None:
        proj = _make_project()
        pipelines = proj.pipelines
        with patch.object(pipelines, "iter_service_endpoints", return_value=iter([])):
            assert pipelines.list_service_endpoints() == []

    def test_get_service_endpoint_returns_matching(self) -> None:
        proj = _make_project()
        info = _endpoint_info("TargetConnection")
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.iter_service_endpoints",
            return_value=iter([info]),
        ):
            result = proj.pipelines.get_service_endpoint("TargetConnection")
        assert isinstance(result, ServiceEndpoint)
        assert result.name == "TargetConnection"

    def test_get_service_endpoint_raises_key_error_when_not_found(self) -> None:
        proj = _make_project()
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.iter_service_endpoints",
                return_value=iter([]),
            ),
            pytest.raises(KeyError),
        ):
            proj.pipelines.get_service_endpoint("Missing")

    def test_get_service_endpoint_raises_key_error_when_name_not_in_list(self) -> None:
        proj = _make_project()
        other_info = _endpoint_info("OtherConnection")
        with (
            patch(
                "pyado.oop.pipelines.project_pipelines.raw.iter_service_endpoints",
                return_value=iter([other_info]),
            ),
            pytest.raises(KeyError),
        ):
            proj.pipelines.get_service_endpoint("Missing")

    def test_get_service_endpoint_by_id_returns_wrapper(self) -> None:
        proj = _make_project()
        info = _endpoint_info("ByIdConnection")
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.get_service_endpoint",
            return_value=info,
        ) as mock_get:
            result = proj.pipelines.get_service_endpoint_by_id(info.id)
        mock_get.assert_called_once_with(proj.api_call, info.id)
        assert isinstance(result, ServiceEndpoint)
        assert result.id == info.id

    def test_create_service_endpoint_returns_wrapper(self) -> None:
        proj = _make_project()
        created_info = _endpoint_info("NewConnection")
        request = _make_create_request("NewConnection")
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.post_service_endpoint",
            return_value=created_info,
        ) as mock_post:
            result = proj.pipelines.create_service_endpoint(request)
        mock_post.assert_called_once_with(proj.org.api_call, request)
        assert isinstance(result, ServiceEndpoint)
        assert result.name == "NewConnection"

    def test_create_service_endpoint_uses_org_api_call(self) -> None:
        proj = _make_project()
        created_info = _endpoint_info()
        request = _make_create_request()
        captured: list[object] = []

        def _side_effect(
            api_call: object, *_a: object, **_kw: object
        ) -> ServiceEndpointInfo:
            captured.append(api_call)
            return created_info

        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.post_service_endpoint",
            side_effect=_side_effect,
        ):
            proj.pipelines.create_service_endpoint(request)
        assert captured[0] is proj.org.api_call
