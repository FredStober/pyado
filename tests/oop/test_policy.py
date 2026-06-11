"""Tests for pyado.oop PolicyConfiguration and ProjectSettings policy methods."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from pyado.oop.repos.policy import PolicyConfiguration
from pyado.raw import (
    PolicyConfigurationInfo as RawPolicyConfiguration,
)
from pyado.raw import (
    PolicyConfigurationRequest,
    PolicyType,
    PolicyTypeIdRef,
    ProcessDetail,
)
from tests.oop.conftest import (
    _api_call,
    _make_project,
    _project_info,
)

# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _policy_type(type_id: str | None = None) -> PolicyType:
    return PolicyType.model_validate(
        {
            "id": type_id or str(uuid4()),
            "displayName": "Minimum number of reviewers",
        }
    )


def _policy_config(config_id: int = 1) -> RawPolicyConfiguration:
    return RawPolicyConfiguration.model_validate(
        {
            "id": config_id,
            "type": {
                "id": str(uuid4()),
                "displayName": "Minimum number of reviewers",
            },
            "isEnabled": True,
            "isBlocking": True,
            "settings": {"minimumApproverCount": 2},
            "revision": 3,
        }
    )


def _policy_config_request() -> PolicyConfigurationRequest:
    return PolicyConfigurationRequest(
        is_enabled=True,
        is_blocking=True,
        type=PolicyTypeIdRef(id=uuid4()),
        settings={"minimumApproverCount": 2},
    )


# ---------------------------------------------------------------------------
# PolicyConfiguration OOP class
# ---------------------------------------------------------------------------


class TestPolicyConfigurationProperties:
    def _make_policy(self, config_id: int = 1) -> PolicyConfiguration:
        return PolicyConfiguration(_make_project(), _policy_config(config_id))

    def test_id_returns_config_id(self) -> None:
        assert self._make_policy(42).id == 42

    def test_type_returns_policy_type(self) -> None:
        result = self._make_policy().type
        assert isinstance(result, PolicyType)

    def test_is_enabled_returns_bool(self) -> None:
        assert self._make_policy().is_enabled is True

    def test_is_blocking_returns_bool(self) -> None:
        assert self._make_policy().is_blocking is True

    def test_revision_returns_int(self) -> None:
        assert self._make_policy().revision == 3

    def test_created_by_returns_none_when_absent(self) -> None:
        assert self._make_policy().created_by is None

    def test_info_returns_stored_raw_info(self) -> None:
        raw_info = _policy_config()
        policy = PolicyConfiguration(_make_project(), raw_info)
        assert policy.info is raw_info

    def test_api_call_built_from_project_and_id(self) -> None:
        proj = _make_project()
        policy = PolicyConfiguration(proj, _policy_config(7))
        with patch(
            "pyado.oop.repos.policy.raw.get_policy_configuration_api_call"
        ) as mock_ac:
            mock_ac.return_value = MagicMock()
            _ = policy.api_call
        mock_ac.assert_called_once_with(proj.api_call, 7)

    def test_project_back_reference(self) -> None:
        proj = _make_project()
        policy = PolicyConfiguration(proj, _policy_config())
        assert policy.project is proj

    def test_org_back_reference(self) -> None:
        proj = _make_project()
        policy = PolicyConfiguration(proj, _policy_config())
        assert policy.org is proj.org


class TestPolicyConfigurationRefresh:
    def test_refresh_clears_info(self) -> None:
        policy = PolicyConfiguration(_make_project(), _policy_config())
        policy.refresh()
        assert policy._info is None

    def test_info_re_fetches_after_refresh(self) -> None:
        proj = _make_project()
        policy = PolicyConfiguration(proj, _policy_config())
        policy.refresh()
        fresh = _policy_config()
        with (
            patch(
                "pyado.oop.repos.policy.raw.get_policy_configuration_api_call"
            ) as mock_ac,
            patch("pyado.oop.repos.policy.raw.get_policy_configuration") as mock_get,
        ):
            mock_ac.return_value = _api_call()
            mock_get.return_value = fresh
            _ = policy.info
        mock_get.assert_called_once()


class TestPolicyConfigurationUpdate:
    def test_update_calls_raw_and_caches_result(self) -> None:
        proj = _make_project()
        policy = PolicyConfiguration(proj, _policy_config())
        request = _policy_config_request()
        updated = _policy_config()
        with (
            patch(
                "pyado.oop.repos.policy.raw.get_policy_configuration_api_call"
            ) as mock_ac,
            patch("pyado.oop.repos.policy.raw.put_policy_configuration") as mock_update,
        ):
            mock_ac.return_value = _api_call()
            mock_update.return_value = updated
            policy.update(request)
        mock_update.assert_called_once()
        assert policy._info is updated


class TestPolicyConfigurationDelete:
    def test_delete_calls_raw(self) -> None:
        proj = _make_project()
        policy = PolicyConfiguration(proj, _policy_config())
        with (
            patch(
                "pyado.oop.repos.policy.raw.get_policy_configuration_api_call"
            ) as mock_ac,
            patch("pyado.oop.repos.policy.raw.delete_policy_configuration") as mock_del,
        ):
            mock_ac.return_value = _api_call()
            policy.delete()
        mock_del.assert_called_once()


# ---------------------------------------------------------------------------
# ProjectSettings policy methods
# ---------------------------------------------------------------------------


class TestProjectSettingsPolicyConfigurations:
    def test_iter_policy_configurations_yields_wrappers(self) -> None:
        proj = _make_project()
        raw_config = _policy_config()
        with patch(
            "pyado.oop.settings.project_settings.raw.iter_policy_configurations"
        ) as mock_iter:
            mock_iter.return_value = iter([raw_config])
            result = list(proj.settings.iter_policy_configurations())
        assert len(result) == 1
        assert isinstance(result[0], PolicyConfiguration)

    def test_list_policy_configurations_delegates(self) -> None:
        proj = _make_project()
        settings = proj.settings
        with patch.object(
            settings, "iter_policy_configurations", return_value=iter([])
        ):
            assert settings.list_policy_configurations() == []

    def test_get_policy_configuration_returns_wrapper(self) -> None:
        proj = _make_project()
        raw_config = _policy_config(5)
        with (
            patch(
                "pyado.oop.settings.project_settings.raw.get_policy_configuration_api_call"
            ) as mock_ac,
            patch(
                "pyado.oop.settings.project_settings.raw.get_policy_configuration"
            ) as mock_get,
        ):
            mock_ac.return_value = _api_call()
            mock_get.return_value = raw_config
            result = proj.settings.get_policy_configuration(5)
        assert isinstance(result, PolicyConfiguration)
        assert result.id == 5

    def test_create_policy_configuration_returns_wrapper(self) -> None:
        proj = _make_project()
        raw_config = _policy_config(99)
        request = _policy_config_request()
        with patch(
            "pyado.oop.settings.project_settings.raw.post_policy_configuration"
        ) as mock_create:
            mock_create.return_value = raw_config
            result = proj.settings.create_policy_configuration(request)
        assert isinstance(result, PolicyConfiguration)
        mock_create.assert_called_once()


class TestProjectSettingsPolicyTypes:
    def test_iter_policy_types_yields_types(self) -> None:
        proj = _make_project()
        ptype = _policy_type()
        with patch(
            "pyado.oop.settings.project_settings.raw.iter_policy_types"
        ) as mock_iter:
            mock_iter.return_value = iter([ptype])
            result = list(proj.settings.iter_policy_types())
        assert len(result) == 1
        assert isinstance(result[0], PolicyType)

    def test_list_policy_types_returns_list(self) -> None:
        proj = _make_project()
        ptype = _policy_type()
        with patch(
            "pyado.oop.settings.project_settings.raw.list_policy_types"
        ) as mock_list:
            mock_list.return_value = [ptype]
            result = proj.settings.list_policy_types()
        assert len(result) == 1

    def test_get_policy_type_returns_type(self) -> None:
        proj = _make_project()
        type_id = uuid4()
        ptype = _policy_type(str(type_id))
        with patch(
            "pyado.oop.settings.project_settings.raw.get_policy_type"
        ) as mock_get:
            mock_get.return_value = ptype
            result = proj.settings.get_policy_type(type_id)
        assert isinstance(result, PolicyType)
        mock_get.assert_called_once_with(proj.api_call, type_id)


class TestProjectSettingsProcessInfo:
    def test_get_process_info_raises_if_no_capabilities(self) -> None:
        proj = _make_project()
        proj_info_no_cap = _project_info()
        with patch("pyado.oop.settings.project_settings.raw.get_project") as mock_get:
            mock_get.return_value = proj_info_no_cap
            with pytest.raises(ValueError, match="capabilities"):
                proj.settings.get_process_info()

    def test_get_process_info_calls_raw(self) -> None:
        proj = _make_project()
        detail = MagicMock(spec=ProcessDetail)
        with (
            patch("pyado.oop.settings.project_settings.raw.get_project") as mock_proj,
            patch(
                "pyado.oop.settings.project_settings.raw.get_process_info"
            ) as mock_proc,
        ):
            mock_proj.return_value = _project_info_with_capabilities()
            mock_proc.return_value = detail
            result = proj.settings.get_process_info()
        assert result is detail
        mock_proc.assert_called_once()


# ---------------------------------------------------------------------------
# Local helper for process info test
# ---------------------------------------------------------------------------


def _project_info_with_capabilities() -> object:
    caps = MagicMock()
    caps.process_template.template_type_id = str(uuid4())
    info_with_caps = MagicMock()
    info_with_caps.capabilities = caps
    return info_with_caps
