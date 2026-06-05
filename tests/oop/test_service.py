"""Tests for pyado.oop AzureDevOpsService — OOP layer."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import MagicMock, patch

import pytest
import requests

from pyado.oop import (
    AzureDevOpsService,
    Build,
    Organization,
    Project,
    PullRequest,
    Repository,
    WorkItem,
)
from tests.oop.conftest import (
    ORG_NAME,
    ORG_URL,
    REPO_ID,
    TOKEN,
    _api_call,
    _build_details,
    _make_service,
    _pipeline_info,
    _pr_list_item,
    _project_info,
    _repo_info,
    _work_item_info,
)


class TestAzureDevOpsService:
    def test_init_with_explicit_org_and_pat(self) -> None:
        svc = AzureDevOpsService(org=ORG_NAME, pat=TOKEN)
        assert svc.oop_api.org_name == ORG_NAME
        assert svc.oop_api.token == TOKEN

    def test_init_from_env_org(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AZURE_DEVOPS_ORG", ORG_NAME)
        monkeypatch.setenv("AZURE_DEVOPS_EXT_PAT", TOKEN)
        svc = AzureDevOpsService()
        assert svc.oop_api.org_name == ORG_NAME

    def test_init_from_env_system_uri(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AZURE_DEVOPS_ORG", raising=False)
        monkeypatch.setenv("SYSTEM_TEAMFOUNDATIONCOLLECTIONURI", ORG_NAME)
        monkeypatch.setenv("AZURE_DEVOPS_EXT_PAT", TOKEN)
        svc = AzureDevOpsService()
        assert svc.oop_api.org_name == ORG_NAME

    def test_init_with_credential(self) -> None:
        credential = MagicMock()
        token_result = MagicMock()
        token_result.token = "bearer-token"
        credential.get_token.return_value = token_result
        svc = AzureDevOpsService(org=ORG_NAME, credential=credential)
        assert svc.oop_api.token == "bearer-token"
        credential.get_token.assert_called_once()

    def test_init_both_pat_and_credential_raises(self) -> None:
        with pytest.raises(ValueError, match="either"):
            AzureDevOpsService(org=ORG_NAME, pat=TOKEN, credential=MagicMock())

    def test_init_no_org_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AZURE_DEVOPS_ORG", raising=False)
        monkeypatch.delenv("SYSTEM_TEAMFOUNDATIONCOLLECTIONURI", raising=False)
        with pytest.raises(ValueError, match="Organisation name"):
            AzureDevOpsService(pat=TOKEN)

    def test_init_no_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AZURE_DEVOPS_EXT_PAT", raising=False)
        with pytest.raises(ValueError, match="No access token"):
            AzureDevOpsService(org=ORG_NAME)

    def test_org_is_singleton(self) -> None:
        svc = _make_service()
        assert svc.org is svc.org

    def test_org_type(self) -> None:
        svc = _make_service()
        assert isinstance(svc.org, Organization)

    def test_api_call_is_org_level(self) -> None:
        svc = _make_service()
        assert "_apis" in str(svc.api_call.url)

    def test_refresh_clears_cache(self) -> None:
        svc = _make_service()
        svc._cache["some-key"] = object()
        svc._org_view = MagicMock()
        svc.refresh()
        assert len(svc._cache) == 0
        assert svc._org_view is None

    def test_refresh_resets_org_singleton(self) -> None:
        svc = _make_service()
        org1 = svc.org
        svc.refresh()
        org2 = svc.org
        assert org1 is not org2


class TestAzureDevOpsServiceInitPaths:
    def test_raises_when_both_org_and_org_url_provided(self) -> None:
        with pytest.raises(ValueError, match="either"):
            AzureDevOpsService(
                org=ORG_NAME,
                org_url=ORG_URL,
                pat=TOKEN,
            )

    def test_resolves_org_name_from_full_url(self) -> None:
        svc = AzureDevOpsService(org_url=f"https://dev.azure.com/{ORG_NAME}", pat=TOKEN)
        assert svc.oop_api.org_name == ORG_NAME

    def test_raises_when_org_url_yields_empty_org(self) -> None:
        with pytest.raises(ValueError, match="Cannot extract"):
            AzureDevOpsService(org_url="https://", pat=TOKEN)

    def test_passes_session_to_api_call(self) -> None:
        session = requests.Session()
        svc = AzureDevOpsService(org=ORG_NAME, pat=TOKEN, session=session)
        assert svc is not None


class TestSharedIdentity:
    def test_build_project_is_wi_project(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        proj_url = str(proj.api_call.url)
        svc._cache[proj_url] = proj

        build_api = _api_call(f"{ORG_URL}/TestProject/_apis/build/builds/100")
        wi_api = _api_call(f"{ORG_URL}/TestProject/_apis/wit/workitems/10")
        build = Build(proj, build_api, _build_details(), svc)
        wi = WorkItem(proj, wi_api, _work_item_info())

        assert build.project is wi.project

    def test_build_org_is_svc_org(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        build_api = _api_call(f"{ORG_URL}/TestProject/_apis/build/builds/100")
        build = Build(proj, build_api, _build_details(), svc)
        assert build.org is svc.org

    def test_pipeline_cached_across_build_and_project(self) -> None:
        svc = _make_service()
        proj = Project(svc, "TestProject", _project_info())
        build_api = _api_call(f"{ORG_URL}/TestProject/_apis/build/builds/100")
        build = Build(proj, build_api, _build_details(pipeline_id=1), svc)

        # Access build.pipeline to populate the cache
        pipe_from_build = build.pipeline

        # Access project.get_pipeline_by_id — should return same cached object
        with patch("pyado.oop.project.raw.get_pipeline") as mock_get:
            mock_get.return_value = _pipeline_info(1)
            pipe_from_project = proj.get_pipeline_by_id(1)

        # Already cached so mock not called; same object
        assert pipe_from_build is pipe_from_project

    def test_pr_project_via_repo(self) -> None:
        proj = _make_service_project()
        repo_api = _api_call(f"{ORG_URL}/TestProject/_apis/git/repositories/{REPO_ID}")
        repo = Repository(proj, repo_api, _repo_info(), proj._service)
        pr_api = _api_call(
            f"{ORG_URL}/TestProject/_apis/git/repositories/{REPO_ID}/pullrequests/1"
        )
        pr = PullRequest(repo, pr_api, _pr_list_item(1))
        assert pr.project is proj
        assert pr.repo is repo


def _make_service_project() -> Project:
    svc = _make_service()
    return Project(svc, "TestProject", _project_info())
