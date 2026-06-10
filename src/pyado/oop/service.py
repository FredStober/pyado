"""AzureDevOpsService — factory, auth holder, and central object cache."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import os
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar, cast
from urllib.parse import parse_qs, urlparse

import requests

from pyado.oop.organization import Organization
from pyado.oop.project import Project
from pyado.raw import ApiCall, BuildId, PullRequestId, WorkItemId
from pyado.raw._core import (
    _ADO_URL_ADAPTER,
    _setup_session,
)

if TYPE_CHECKING:
    from azure.core.credentials import TokenCredential

    from pyado.oop.boards.work_item import WorkItem
    from pyado.oop.pipelines.build import Build
    from pyado.oop.repos.pull_request import PullRequest
    from pyado.oop.repos.repository import Repository

__all__ = ["AzureDevOpsService"]

_ADO_BASE_URL = "https://dev.azure.com"
_SEARCH_BASE_URL = "https://almsearch.dev.azure.com"
_T = TypeVar("_T")


def _parse_ado_project(url: str) -> tuple[str, list[str]]:
    """Parse an ADO URL and return the project name and remaining path segments.

    Supports both ``dev.azure.com`` and legacy ``{org}.visualstudio.com``
    URL forms.

    Args:
        url: ADO URL to parse.

    Returns:
        Tuple of ``(project_name, path_segments_after_project)``.

    Raises:
        ValueError: If the URL host is not a recognised ADO host, or if the
            path does not contain enough segments to identify a project.
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    segments = [s for s in parsed.path.split("/") if s]
    err_msg = f"Cannot parse ADO URL: {url!r}"
    if host == "dev.azure.com":
        # path: /{org}/{project}/...
        try:
            _, project_name, *rest = segments
        except ValueError:
            raise ValueError(err_msg) from None
        return project_name, rest
    if host.endswith(".visualstudio.com"):
        # path: /{project}/...
        try:
            project_name, *rest = segments
        except ValueError:
            raise ValueError(err_msg) from None
        return project_name, rest
    raise ValueError(err_msg)


class _OopApi:
    """Package-internal proxy for AzureDevOpsService internals.

    Obtained via :attr:`AzureDevOpsService.oop_api`.  Not part of the public
    pyado interface — intended for use by sibling OOP classes only.

    Attributes:
        org_name: Organisation name (e.g. ``"myorg"``).
        org_base_api_call: Org-scoped ApiCall without the ``/_apis`` suffix.
    """

    def __init__(
        self,
        org_name: str,
        cache: "dict[str, Any]",
        session: requests.Session,
    ) -> None:
        """Construct the proxy from extracted service state.

        Args:
            org_name: Organisation name (e.g. ``"myorg"``).
            cache: Shared object cache reference from the service.
            session: Pre-configured ``requests.Session`` with auth already set.
        """
        self.org_name = org_name
        self._cache = cache
        self._session = session

    def _make_api_call(self, url_str: str) -> ApiCall:
        """Build an ApiCall for the given URL using the stored session.

        Returns:
            ApiCall configured with the stored session and the given URL.
        """
        return ApiCall(
            session=self._session,
            url=_ADO_URL_ADAPTER.validate_python(url_str),
        )

    @property
    def org_base_api_call(self) -> ApiCall:
        """Org-scoped API call without the ``/_apis`` suffix."""
        return self._make_api_call(f"{_ADO_BASE_URL}/{self.org_name}")

    def get_or_cache(self, url: str, factory: Callable[[], _T]) -> _T:
        """Return the cached object for *url*, creating it via *factory* if absent.

        Args:
            url: Cache key (string form of the resource API call URL).
            factory: Zero-argument callable that creates the resource object.

        Returns:
            The cached (or newly created) resource object.
        """
        if url not in self._cache:
            self._cache[url] = factory()
        return cast("_T", self._cache[url])

    def make_project_api_call(self, name: str) -> ApiCall:
        """Build a project-level API call for the given project name.

        Args:
            name: Project name as it appears in ADO (case-sensitive).

        Returns:
            An ApiCall pointing at ``{org}/{name}/_apis``.
        """
        return self._make_api_call(f"{_ADO_BASE_URL}/{self.org_name}/{name}/_apis")

    def make_team_api_call(self, project_name: str, team_name: str) -> ApiCall:
        """Build a team-scoped API call.

        ADO team endpoints use ``{org}/{project}/{team}/_apis/...``.

        Args:
            project_name: Project name as it appears in ADO (case-sensitive).
            team_name: Team name as it appears in ADO (case-sensitive).

        Returns:
            An ApiCall pointing at ``{org}/{project}/{team}/_apis``.
        """
        return self._make_api_call(
            f"{_ADO_BASE_URL}/{self.org_name}/{project_name}/{team_name}/_apis"
        )

    @property
    def vssps_api_call(self) -> ApiCall:
        """vssps-scoped ApiCall (graph groups, identities)."""
        return self._make_api_call(f"https://vssps.dev.azure.com/{self.org_name}")

    @property
    def profile_api_call(self) -> ApiCall:
        """Profile-scoped ApiCall (user profile endpoint)."""
        return self._make_api_call("https://app.vssps.visualstudio.com/_apis")

    @property
    def search_api_call(self) -> ApiCall:
        """Org-scoped search API call (almsearch.dev.azure.com)."""
        return self._make_api_call(f"{_SEARCH_BASE_URL}/{self.org_name}/_apis")

    def make_search_project_api_call(self, project_name: str) -> ApiCall:
        """Build a project-level search API call on almsearch.dev.azure.com.

        Args:
            project_name: Project name as it appears in ADO (case-sensitive).

        Returns:
            An ApiCall pointing at the project search endpoint.
        """
        return self._make_api_call(
            f"{_SEARCH_BASE_URL}/{self.org_name}/{project_name}/_apis"
        )

    def clear_cache_prefix(self, prefix: str) -> None:
        """Evict all cache entries whose key starts with *prefix*.

        Args:
            prefix: URL prefix string; all matching entries are removed.
        """
        for key in [k for k in self._cache if k.startswith(prefix)]:
            del self._cache[key]


class AzureDevOpsService:
    """Entry point and central object cache for the pyado OOP API.

    **ADO concept:** this class does not model a single ADO resource; it
    represents the *authenticated connection to an organisation* — the root
    of the hierarchy ``org → project → (build | pipeline | repo | …)``.

    **Why it exists:** the raw layer is stateless (every function takes an
    :class:`~pyado.raw.ApiCall`).  ``AzureDevOpsService`` exists to:

    1. Hold the access token and resolve it once from env-vars or
       ``azure-identity`` credentials so callers never pass tokens manually.
    2. Build correctly-scoped ``ApiCall`` objects (org, project, team) so
       callers never construct URLs.
    3. Maintain a URL-keyed object cache so that resource objects reached
       through different paths are the *same Python object* — ``build.project
       is wi.project`` is guaranteed when both belong to the same ADO project.
       This prevents duplicate API calls and makes identity comparisons safe.

    Holds credentials and resolves authentication from explicit arguments or
    environment variables. Acts as a factory and shared object cache so that
    resource objects obtained through different paths share identity — for
    example, ``build.project is wi.project`` is guaranteed when both belong to
    the same ADO project.

    Auth resolution order:

    1. Explicit ``pat`` argument.
    2. ``AZURE_DEVOPS_EXT_PAT`` environment variable.
    3. Explicit ``bearer_token`` (pre-acquired OAuth bearer token string).
    4. Explicit ``azure_credentials`` (any azure-identity ``TokenCredential``);
       a bearer token is acquired once at construction. Recreate the service to
       refresh the token.

    ``pat``, ``bearer_token``, and ``azure_credentials`` are mutually
    exclusive.

    Org name resolution order (when ``org`` and ``org_url`` are both ``None``):

    1. ``AZURE_DEVOPS_ORG`` environment variable (bare name or full URL).
    2. ``SYSTEM_TEAMFOUNDATIONCOLLECTIONURI`` environment variable (full URL).

    Raises ``ValueError`` when no org name is found.

    Attributes:
        _org_name: Organisation name (bare, e.g. ``"myorg"``).
        _org_api_call: Organisation-level API call.
        _cache: URL-keyed object cache (Project, Repository, Pipeline).
        _org_view: Cached Organisation singleton, or None before first access.
    """

    def __init__(
        self,
        *,
        org: str | None = None,
        org_url: str | None = None,
        pat: str | None = None,
        bearer_token: str | None = None,
        azure_credentials: "TokenCredential | None" = None,
        session: requests.Session | None = None,
    ) -> None:
        """Construct the service.

        Args:
            org: ADO organisation name (e.g. ``"myorg"``).  Mutually
                exclusive with *org_url*.
            org_url: Full ADO organisation URL
                (e.g. ``"https://dev.azure.com/myorg"``).  The org name is
                extracted automatically from the last path component.  Mutually
                exclusive with *org*.  Falls back to ``AZURE_DEVOPS_ORG`` or
                ``SYSTEM_TEAMFOUNDATIONCOLLECTIONURI`` (both accept a full URL).
            pat: Personal access token.  Falls back to ``AZURE_DEVOPS_EXT_PAT``.
                Mutually exclusive with ``bearer_token`` and
                ``azure_credentials``.
            bearer_token: Pre-acquired OAuth bearer token string.  Mutually
                exclusive with ``pat`` and ``azure_credentials``.
            azure_credentials: Any azure-identity ``TokenCredential``.  A
                bearer token is acquired immediately.  Mutually exclusive with
                ``pat`` and ``bearer_token``.
            session: Optional custom ``requests.Session`` to use for all HTTP
                requests made by this service instance (e.g. to inject a
                custom SSL adapter or trust-store configuration).  When
                provided, auth is configured on it via :func:`_setup_session`.
                When ``None`` (default), a plain :class:`requests.Session` is
                created and configured via :func:`_setup_session`.

        Raises:
            ValueError: If more than one of ``pat``, ``bearer_token``, or
                ``azure_credentials`` are provided, if both ``org`` and
                ``org_url`` are provided, if no organisation name can be
                resolved.
        """
        auth_count = sum(
            [pat is not None, bearer_token is not None, azure_credentials is not None]
        )
        if auth_count > 1:
            err_msg = (
                "Provide at most one of 'pat', 'bearer_token', or 'azure_credentials'."
            )
            raise ValueError(err_msg)
        if org is not None and org_url is not None:
            err_msg = "Provide either 'org' or 'org_url', not both."
            raise ValueError(err_msg)

        raw_org = (
            org_url
            or org
            or os.environ.get("AZURE_DEVOPS_ORG")
            or os.environ.get("SYSTEM_TEAMFOUNDATIONCOLLECTIONURI")
        )
        if not raw_org:
            err_msg = (
                "Organisation name is required. Provide 'org' or 'org_url', or set "
                "AZURE_DEVOPS_ORG (or SYSTEM_TEAMFOUNDATIONCOLLECTIONURI)."
            )
            raise ValueError(err_msg)

        # Extract bare org name from a full URL if needed.
        parsed = urlparse(raw_org)
        if parsed.scheme:
            resolved_org = parsed.path.strip("/").rsplit("/", 1)[-1]
        else:
            resolved_org = raw_org
        if not resolved_org:
            err_msg = f"Cannot extract organisation name from {raw_org!r}."
            raise ValueError(err_msg)

        self._org_name = resolved_org

        self._session: requests.Session = _setup_session(
            session if session is not None else requests.Session(),
            pat=pat,
            bearer_token=bearer_token,
            azure_credentials=azure_credentials,
        )

        self._org_api_call = ApiCall(
            session=self._session,
            url=_ADO_URL_ADAPTER.validate_python(
                f"{_ADO_BASE_URL}/{self._org_name}/_apis"
            ),
        )
        self._cache: dict[str, Any] = {}
        self._org_view: Organization | None = None
        self._oop_api = _OopApi(self._org_name, self._cache, self._session)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def org(self) -> Organization:
        """Organisation singleton — always the same object per service instance."""
        if self._org_view is None:
            self._org_view = Organization(self)
        return self._org_view

    @property
    def api_call(self) -> ApiCall:
        """Organisation-level API call for direct use with pyado.raw functions."""
        return self._org_api_call

    @property
    def oop_api(self) -> _OopApi:
        """Package-internal proxy — for use by sibling OOP classes only.

        Returns:
            _OopApi proxy that exposes service internals to the OOP layer
            without polluting the public API with implementation details.
        """
        return self._oop_api

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def get_pull_request_by_url(
        self,
        url: str,
        pull_request_id: PullRequestId | None = None,
    ) -> "PullRequest":
        """Return a PullRequest resolved from a URL.

        Accepts two calling conventions:

        * **PR URL** — pass the full pull request web URL and omit
          *pull_request_id*::

              svc.get_pull_request_by_url(
                  "https://dev.azure.com/org/MyProject/_git/myrepo/pullrequest/42"
              )

        * **Repo URL + ID** — pass the repository web URL and supply
          *pull_request_id* separately::

              svc.get_pull_request_by_url(
                  "https://dev.azure.com/org/MyProject/_git/myrepo",
                  pull_request_id=42,
              )

        Both ``dev.azure.com`` and legacy ``{org}.visualstudio.com`` URLs are
        accepted.

        Args:
            url: Full ADO repository URL or pull request URL.
            pull_request_id: Numeric pull request ID.  Required when *url* is
                a repository URL; ignored when *url* already contains the PR ID.

        Returns:
            PullRequest wrapping the resolved pull request.

        Raises:
            ValueError: If *url* cannot be parsed as an ADO repository or
                pull request URL, or if no pull request ID is available.
        """
        project_name, rest = _parse_ado_project(url)
        try:
            git_segment, repo_name, *pr_rest = rest
        except ValueError:
            err_msg = f"Cannot parse ADO repository URL: {url!r}"
            raise ValueError(err_msg) from None
        if git_segment.lower() != "_git":
            err_msg = f"Cannot parse ADO repository URL: {url!r}"
            raise ValueError(err_msg)
        if pull_request_id is not None:
            pr_id = pull_request_id
        else:
            try:
                pr_segment, pr_id_str, *_ = pr_rest
            except ValueError:
                err_msg = (
                    f"URL does not contain a pull request ID and none was "
                    f"provided: {url!r}"
                )
                raise ValueError(err_msg) from None
            if pr_segment.lower() != "pullrequest":
                err_msg = (
                    f"URL does not contain a pull request ID and none was "
                    f"provided: {url!r}"
                )
                raise ValueError(err_msg)
            pr_id = int(pr_id_str)
        project = Project(self, project_name)
        repo = project.repos.get_repository(repo_name)
        return repo.get_pull_request(pr_id)

    def get_repository_by_url(self, url: str) -> "Repository":
        """Return a Repository resolved from its web URL.

        Accepts ``dev.azure.com`` and legacy ``{org}.visualstudio.com`` forms::

            svc.get_repository_by_url(
                "https://dev.azure.com/org/MyProject/_git/myrepo"
            )

        Args:
            url: Full ADO repository URL (may also be a pull request URL —
                the pull request segment is ignored).

        Returns:
            Repository wrapping the resolved repository.

        Raises:
            ValueError: If *url* cannot be parsed as an ADO repository URL.
        """
        project_name, rest = _parse_ado_project(url)
        try:
            git_segment, repo_name, *_ = rest
        except ValueError:
            err_msg = f"Cannot parse ADO repository URL: {url!r}"
            raise ValueError(err_msg) from None
        if git_segment.lower() != "_git":
            err_msg = f"Cannot parse ADO repository URL: {url!r}"
            raise ValueError(err_msg)
        project = Project(self, project_name)
        return project.repos.get_repository(repo_name)

    def get_work_item_by_url(
        self,
        url: str,
        work_item_id: WorkItemId | None = None,
    ) -> "WorkItem":
        """Return a WorkItem resolved from a URL.

        Accepts two calling conventions:

        * **Work item URL** — pass the full work item edit URL::

              svc.get_work_item_by_url(
                  "https://dev.azure.com/org/MyProject/_workitems/edit/42"
              )

        * **Project URL + ID** — pass any project-scoped ADO URL and supply
          *work_item_id* separately::

              svc.get_work_item_by_url(
                  "https://dev.azure.com/org/MyProject/_workitems",
                  work_item_id=42,
              )

        Both ``dev.azure.com`` and legacy ``{org}.visualstudio.com`` URLs are
        accepted.

        Args:
            url: Full ADO work item edit URL, or any URL under the same
                project when *work_item_id* is provided.
            work_item_id: Numeric work item ID.  Required when *url* does not
                contain the ID; ignored when *url* already contains it.

        Returns:
            WorkItem wrapping the resolved work item.

        Raises:
            ValueError: If *url* cannot be parsed or no work item ID is
                available.
        """
        project_name, rest = _parse_ado_project(url)
        if work_item_id is not None:
            wi_id: WorkItemId = work_item_id
        else:
            try:
                wi_segment, edit_segment, wi_id_str, *_ = rest
            except ValueError:
                err_msg = (
                    f"URL does not contain a work item ID and none was "
                    f"provided: {url!r}"
                )
                raise ValueError(err_msg) from None
            if wi_segment.lower() != "_workitems" or edit_segment.lower() != "edit":
                err_msg = (
                    f"URL does not contain a work item ID and none was "
                    f"provided: {url!r}"
                )
                raise ValueError(err_msg)
            wi_id = int(wi_id_str)
        project = Project(self, project_name)
        return project.boards.get_work_item(wi_id)

    def get_build_by_url(
        self,
        url: str,
        build_id: BuildId | None = None,
    ) -> "Build":
        """Return a Build resolved from a URL.

        Accepts two calling conventions:

        * **Build results URL** — pass the full build results URL (the build
          ID is read from the ``buildId`` query parameter)::

              svc.get_build_by_url(
                  "https://dev.azure.com/org/MyProject/_build/results?buildId=42"
              )

        * **Project URL + ID** — pass any project-scoped ADO URL and supply
          *build_id* separately::

              svc.get_build_by_url(
                  "https://dev.azure.com/org/MyProject/_build/results",
                  build_id=42,
              )

        Both ``dev.azure.com`` and legacy ``{org}.visualstudio.com`` URLs are
        accepted.

        Args:
            url: Full ADO build results URL, or any URL under the same project
                when *build_id* is provided.
            build_id: Numeric build ID.  Required when *url* does not contain
                a ``buildId`` query parameter; ignored when the URL already
                contains it.

        Returns:
            Build wrapping the resolved build.

        Raises:
            ValueError: If *url* cannot be parsed, or no build ID is
                available.
        """
        project_name, _ = _parse_ado_project(url)
        if build_id is not None:
            resolved_build_id: BuildId = build_id
        else:
            params = parse_qs(urlparse(url).query)
            build_id_values = params.get("buildId")
            if not build_id_values:
                err_msg = (
                    f"URL does not contain a buildId query parameter and "
                    f"none was provided: {url!r}"
                )
                raise ValueError(err_msg)
            resolved_build_id = int(build_id_values[0])
        project = Project(self, project_name)
        return project.pipelines.get_build(resolved_build_id)

    def refresh(self) -> None:
        """Clear all cached objects.

        The next access to any cached resource (projects, repositories,
        pipelines) will create fresh objects from the API. The Organisation
        singleton is also recreated.
        """
        self._cache.clear()
        self._org_view = None
