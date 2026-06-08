"""Tests for pyado.oop ServiceEndpoint and ProjectPipelines service endpoint methods."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import patch
from uuid import uuid4

import pytest

from pyado.oop.pipelines.service_endpoint import ServiceEndpoint
from pyado.raw import ServiceEndpointInfo
from tests.oop.conftest import (
    _make_project,
)

# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# ServiceEndpoint class
# ---------------------------------------------------------------------------


class TestServiceEndpointProperties:
    def _make_endpoint(self) -> ServiceEndpoint:
        return ServiceEndpoint(_make_project(), _endpoint_info())

    def test_id_returns_uuid(self) -> None:
        info = _endpoint_info()
        ep = ServiceEndpoint(_make_project(), info)
        assert ep.id == info.id

    def test_name_returns_name(self) -> None:
        info = _endpoint_info("My GitHub")
        ep = ServiceEndpoint(_make_project(), info)
        assert ep.name == "My GitHub"

    def test_type_returns_type_string(self) -> None:
        ep = self._make_endpoint()
        assert ep.type == "github"

    def test_url_returns_url(self) -> None:
        ep = self._make_endpoint()
        assert ep.url == "https://github.com"

    def test_is_ready_returns_bool(self) -> None:
        ep = self._make_endpoint()
        assert ep.is_ready is True

    def test_is_shared_returns_bool(self) -> None:
        ep = self._make_endpoint()
        assert ep.is_shared is False

    def test_authorization_scheme_returns_scheme(self) -> None:
        ep = self._make_endpoint()
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
            "pyado.oop.pipelines.service_endpoint.raw.iter_service_endpoints"
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
            "pyado.oop.pipelines.service_endpoint.raw.iter_service_endpoints"
        ) as mock_iter:
            mock_iter.return_value = iter([other_info])
            with pytest.raises(KeyError):
                _ = ep.info


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
