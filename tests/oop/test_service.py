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
from pyado.raw import ApiCall
from tests.oop.conftest import (
    ORG_NAME,
    ORG_URL,
    REPO_ID,
    TOKEN,
    _api_call,
    _build_details,
    _make_service,
    _pipeline_info,
    _pr_created,
    _pr_list_item,
    _project_info,
    _repo_info,
    _work_item_info,
)


class TestAzureDevOpsService:
    def test_init_with_explicit_org_and_pat(self) -> None:
        svc = AzureDevOpsService(org=ORG_NAME, pat=TOKEN)
        assert svc.oop_api.org_name == ORG_NAME

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

    def test_init_with_azure_credentials(self) -> None:
        azure_credentials = MagicMock()
        token_result = MagicMock()
        token_result.token = "bearer-token"
        azure_credentials.get_token.return_value = token_result
        AzureDevOpsService(org=ORG_NAME, azure_credentials=azure_credentials)
        azure_credentials.get_token.assert_called_once()

    def test_init_with_bearer_token(self) -> None:
        svc = AzureDevOpsService(org=ORG_NAME, bearer_token=TOKEN)
        assert svc.oop_api.org_name == ORG_NAME

    def test_init_with_azure_credentials_and_session_configures_session(self) -> None:
        azure_credentials = MagicMock()
        token_result = MagicMock()
        token_result.token = "bearer-token"
        azure_credentials.get_token.return_value = token_result
        custom_session = requests.Session()
        svc = AzureDevOpsService(
            org=ORG_NAME, azure_credentials=azure_credentials, session=custom_session
        )
        assert svc._session is custom_session

    def test_init_with_pat_and_session_attaches_auth(self) -> None:
        custom_session = requests.Session()
        AzureDevOpsService(org=ORG_NAME, pat=TOKEN, session=custom_session)
        assert isinstance(custom_session.auth, requests.auth.HTTPBasicAuth)

    def test_init_both_pat_and_azure_credentials_raises(self) -> None:
        with pytest.raises(ValueError, match="at most one"):
            AzureDevOpsService(org=ORG_NAME, pat=TOKEN, azure_credentials=MagicMock())

    def test_init_no_org_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AZURE_DEVOPS_ORG", raising=False)
        monkeypatch.delenv("SYSTEM_TEAMFOUNDATIONCOLLECTIONURI", raising=False)
        with pytest.raises(ValueError, match="Organisation name"):
            AzureDevOpsService(pat=TOKEN)

    def test_org_is_singleton(self) -> None:
        svc = _make_service()
        assert svc.org is svc.org

    def test_oop_api_is_identity_stable(self) -> None:
        svc = _make_service()
        assert svc.oop_api is svc.oop_api

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

        # Access project.pipelines.get_pipeline_by_id — should return same cached object
        with patch("pyado.oop.pipelines.pipeline.raw.get_pipeline") as mock_get:
            mock_get.return_value = _pipeline_info(1)
            pipe_from_project = proj.pipelines.get_pipeline_by_id(1)

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


class TestGetPullRequestByUrl:
    _PR_URL = f"{ORG_URL}/TestProject/_git/myrepo/pullrequest/42"
    _REPO_URL = f"{ORG_URL}/TestProject/_git/myrepo"
    _VS_PR_URL = (
        f"https://{ORG_NAME}.visualstudio.com/TestProject/_git/myrepo/pullrequest/42"
    )

    def _patch_repo_and_pr(self) -> tuple[MagicMock, MagicMock]:
        """Return (mock_iter_repos, mock_get_pr_details) patches ready to start."""
        mock_iter = MagicMock(return_value=iter([_repo_info()]))
        mock_details = MagicMock(return_value=_pr_created(42))
        return mock_iter, mock_details

    def test_pr_url_returns_pull_request(self) -> None:
        svc = _make_service()
        mock_iter, mock_details = self._patch_repo_and_pr()
        with (
            patch(
                "pyado.oop.repos.project_repos.raw.iter_repository_details", mock_iter
            ),
            patch(
                "pyado.oop.repos.repository.raw.get_pull_request_details", mock_details
            ),
        ):
            pr = svc.get_pull_request_by_url(self._PR_URL)
        assert isinstance(pr, PullRequest)
        assert pr.id == 42

    def test_repo_url_with_pr_id_returns_pull_request(self) -> None:
        svc = _make_service()
        mock_iter, mock_details = self._patch_repo_and_pr()
        with (
            patch(
                "pyado.oop.repos.project_repos.raw.iter_repository_details", mock_iter
            ),
            patch(
                "pyado.oop.repos.repository.raw.get_pull_request_details", mock_details
            ),
        ):
            pr = svc.get_pull_request_by_url(self._REPO_URL, pull_request_id=42)
        assert isinstance(pr, PullRequest)
        assert pr.id == 42

    def test_visualstudio_url_is_accepted(self) -> None:
        svc = _make_service()
        mock_iter, mock_details = self._patch_repo_and_pr()
        with (
            patch(
                "pyado.oop.repos.project_repos.raw.iter_repository_details", mock_iter
            ),
            patch(
                "pyado.oop.repos.repository.raw.get_pull_request_details", mock_details
            ),
        ):
            pr = svc.get_pull_request_by_url(self._VS_PR_URL)
        assert isinstance(pr, PullRequest)
        assert pr.id == 42

    def test_invalid_url_raises_value_error(self) -> None:
        svc = _make_service()
        with pytest.raises(ValueError, match="Cannot parse ADO URL"):
            svc.get_pull_request_by_url("https://example.com/not-ado")

    def test_repo_url_without_pr_id_raises_value_error(self) -> None:
        svc = _make_service()
        with pytest.raises(ValueError, match="does not contain a pull request ID"):
            svc.get_pull_request_by_url(self._REPO_URL)

    def test_project_url_with_no_git_path_raises_value_error(self) -> None:
        svc = _make_service()
        with pytest.raises(ValueError, match="Cannot parse ADO repository URL"):
            svc.get_pull_request_by_url(f"https://dev.azure.com/{ORG_NAME}/TestProject")

    def test_ado_url_without_git_segment_raises_value_error(self) -> None:
        svc = _make_service()
        with pytest.raises(ValueError, match="Cannot parse ADO repository URL"):
            svc.get_pull_request_by_url(f"{ORG_URL}/TestProject/_build/results")

    def test_git_url_with_non_pullrequest_segment_raises_value_error(self) -> None:
        svc = _make_service()
        with pytest.raises(ValueError, match="does not contain a pull request ID"):
            svc.get_pull_request_by_url(
                f"{ORG_URL}/TestProject/_git/myrepo/commits/abc"
            )

    def test_dev_azure_com_org_only_raises_value_error(self) -> None:
        svc = _make_service()
        with pytest.raises(ValueError, match="Cannot parse ADO URL"):
            svc.get_pull_request_by_url(f"https://dev.azure.com/{ORG_NAME}")

    def test_visualstudio_com_no_path_raises_value_error(self) -> None:
        svc = _make_service()
        with pytest.raises(ValueError, match="Cannot parse ADO URL"):
            svc.get_pull_request_by_url(f"https://{ORG_NAME}.visualstudio.com/")


class TestGetRepositoryByUrl:
    _REPO_URL = f"{ORG_URL}/TestProject/_git/myrepo"
    _VS_REPO_URL = f"https://{ORG_NAME}.visualstudio.com/TestProject/_git/myrepo"

    def test_returns_repository(self) -> None:
        svc = _make_service()
        mock_iter = MagicMock(return_value=iter([_repo_info()]))
        with patch(
            "pyado.oop.repos.project_repos.raw.iter_repository_details", mock_iter
        ):
            repo = svc.get_repository_by_url(self._REPO_URL)
        assert isinstance(repo, Repository)
        assert repo.name == "myrepo"

    def test_visualstudio_url_is_accepted(self) -> None:
        svc = _make_service()
        mock_iter = MagicMock(return_value=iter([_repo_info()]))
        with patch(
            "pyado.oop.repos.project_repos.raw.iter_repository_details", mock_iter
        ):
            repo = svc.get_repository_by_url(self._VS_REPO_URL)
        assert isinstance(repo, Repository)

    def test_pr_url_resolves_to_repository(self) -> None:
        svc = _make_service()
        pr_url = f"{ORG_URL}/TestProject/_git/myrepo/pullrequest/42"
        mock_iter = MagicMock(return_value=iter([_repo_info()]))
        with patch(
            "pyado.oop.repos.project_repos.raw.iter_repository_details", mock_iter
        ):
            repo = svc.get_repository_by_url(pr_url)
        assert isinstance(repo, Repository)
        assert repo.name == "myrepo"

    def test_project_url_with_no_git_path_raises_value_error(self) -> None:
        svc = _make_service()
        with pytest.raises(ValueError, match="Cannot parse ADO repository URL"):
            svc.get_repository_by_url(f"https://dev.azure.com/{ORG_NAME}/TestProject")

    def test_ado_url_without_git_segment_raises_value_error(self) -> None:
        svc = _make_service()
        with pytest.raises(ValueError, match="Cannot parse ADO repository URL"):
            svc.get_repository_by_url(f"{ORG_URL}/TestProject/_build/results")

    def test_invalid_url_raises_value_error(self) -> None:
        svc = _make_service()
        with pytest.raises(ValueError, match="Cannot parse ADO"):
            svc.get_repository_by_url("https://example.com/not-ado")


class TestGetWorkItemByUrl:
    _WI_URL = f"{ORG_URL}/TestProject/_workitems/edit/10"
    _VS_WI_URL = f"https://{ORG_NAME}.visualstudio.com/TestProject/_workitems/edit/10"
    _PROJECT_URL = f"{ORG_URL}/TestProject/_workitems"

    def _patch_wi(self) -> MagicMock:
        return MagicMock(return_value=_work_item_info(10))

    def test_wi_url_returns_work_item(self) -> None:
        svc = _make_service()
        mock_get = self._patch_wi()
        with patch("pyado.oop.boards.project_boards.raw.get_work_item", mock_get):
            wi = svc.get_work_item_by_url(self._WI_URL)
        assert isinstance(wi, WorkItem)
        assert wi.id == 10

    def test_project_url_with_wi_id_returns_work_item(self) -> None:
        svc = _make_service()
        mock_get = self._patch_wi()
        with patch("pyado.oop.boards.project_boards.raw.get_work_item", mock_get):
            wi = svc.get_work_item_by_url(self._PROJECT_URL, work_item_id=10)
        assert isinstance(wi, WorkItem)
        assert wi.id == 10

    def test_visualstudio_url_is_accepted(self) -> None:
        svc = _make_service()
        mock_get = self._patch_wi()
        with patch("pyado.oop.boards.project_boards.raw.get_work_item", mock_get):
            wi = svc.get_work_item_by_url(self._VS_WI_URL)
        assert isinstance(wi, WorkItem)

    def test_url_without_wi_id_raises_value_error(self) -> None:
        svc = _make_service()
        with pytest.raises(ValueError, match="does not contain a work item ID"):
            svc.get_work_item_by_url(self._PROJECT_URL)

    def test_workitems_url_with_wrong_verb_raises_value_error(self) -> None:
        svc = _make_service()
        with pytest.raises(ValueError, match="does not contain a work item ID"):
            svc.get_work_item_by_url(f"{ORG_URL}/TestProject/_workitems/view/42")

    def test_invalid_url_with_wi_id_raises_value_error(self) -> None:
        svc = _make_service()
        with pytest.raises(ValueError, match="Cannot parse ADO URL"):
            svc.get_work_item_by_url("https://example.com/not-ado", work_item_id=10)


class TestGetBuildByUrl:
    _BUILD_URL = f"{ORG_URL}/TestProject/_build/results?buildId=100"
    _BUILD_URL_EXTRA_PARAMS = (
        f"{ORG_URL}/TestProject/_build/results?view=logs&buildId=100"
    )
    _BUILD_PATH_URL = f"{ORG_URL}/TestProject/_build/results"
    _VS_BUILD_URL = (
        f"https://{ORG_NAME}.visualstudio.com/TestProject/_build/results?buildId=100"
    )

    def _patch_build(self) -> MagicMock:
        return MagicMock(return_value=_build_details(100))

    def test_build_url_returns_build(self) -> None:
        svc = _make_service()
        mock_get = self._patch_build()
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.get_build_details", mock_get
        ):
            build = svc.get_build_by_url(self._BUILD_URL)
        assert isinstance(build, Build)
        assert build.id == 100

    def test_build_url_with_extra_params_returns_build(self) -> None:
        svc = _make_service()
        mock_get = self._patch_build()
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.get_build_details", mock_get
        ):
            build = svc.get_build_by_url(self._BUILD_URL_EXTRA_PARAMS)
        assert isinstance(build, Build)
        assert build.id == 100

    def test_build_path_url_with_build_id_returns_build(self) -> None:
        svc = _make_service()
        mock_get = self._patch_build()
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.get_build_details", mock_get
        ):
            build = svc.get_build_by_url(self._BUILD_PATH_URL, build_id=100)
        assert isinstance(build, Build)
        assert build.id == 100

    def test_visualstudio_url_is_accepted(self) -> None:
        svc = _make_service()
        mock_get = self._patch_build()
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.get_build_details", mock_get
        ):
            build = svc.get_build_by_url(self._VS_BUILD_URL)
        assert isinstance(build, Build)

    def test_build_url_without_build_id_raises_value_error(self) -> None:
        svc = _make_service()
        with pytest.raises(ValueError, match="does not contain a buildId"):
            svc.get_build_by_url(self._BUILD_PATH_URL)

    def test_invalid_url_raises_value_error(self) -> None:
        svc = _make_service()
        with pytest.raises(ValueError, match="Cannot parse ADO"):
            svc.get_build_by_url("https://example.com/not-ado")

    def test_project_url_with_build_id_returns_build(self) -> None:
        svc = _make_service()
        mock_get = self._patch_build()
        project_url = f"{ORG_URL}/TestProject/_dashboards"
        with patch(
            "pyado.oop.pipelines.project_pipelines.raw.get_build_details", mock_get
        ):
            build = svc.get_build_by_url(project_url, build_id=100)
        assert isinstance(build, Build)
        assert build.id == 100

    def test_invalid_url_with_build_id_raises_value_error(self) -> None:
        svc = _make_service()
        with pytest.raises(ValueError, match="Cannot parse ADO URL"):
            svc.get_build_by_url("https://example.com/not-ado", build_id=100)


class TestOopApiSearchCalls:
    def test_search_api_call_returns_api_call(self) -> None:
        svc = _make_service()
        result = svc.oop_api.search_api_call
        assert isinstance(result, ApiCall)
        assert "almsearch.dev.azure.com" in str(result.url)

    def test_make_search_project_api_call_returns_api_call(self) -> None:
        svc = _make_service()
        result = svc.oop_api.make_search_project_api_call("MyProject")
        assert isinstance(result, ApiCall)
        assert "almsearch.dev.azure.com" in str(result.url)
        assert "MyProject" in str(result.url)
