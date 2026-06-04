"""AzureDevOpsService — factory, auth holder, and central object cache."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import os
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar, cast

from pyado.oop.organization import Organization
from pyado.raw import ApiCall
from pyado.raw._core import _ADO_URL_ADAPTER, AccessToken

if TYPE_CHECKING:
    from azure.core.credentials import TokenCredential

__all__ = ["AzureDevOpsService"]

_ADO_RESOURCE_ID = "499b84ac-1321-427f-aa17-267ca6975798"
_T = TypeVar("_T")


class _OopApi:
    """Package-internal proxy for AzureDevOpsService internals.

    Obtained via :attr:`AzureDevOpsService.oop_api`.  Not part of the public
    pyado interface — intended for use by sibling OOP classes only.

    Attributes:
        token: Resolved access token.
        org_url: Organisation base URL (trailing slash stripped).
        org_base_api_call: Org-scoped ApiCall without the ``/_apis`` suffix.
    """

    def __init__(
        self,
        token: AccessToken,
        org_url: str,
        cache: "dict[str, Any]",
    ) -> None:
        """Construct the proxy from extracted service state.

        Args:
            token: Resolved ADO access token.
            org_url: Organisation base URL (trailing slash stripped).
            cache: Shared object cache reference from the service.
        """
        self.token = token
        self.org_url = org_url
        self._cache = cache

    @property
    def org_base_api_call(self) -> ApiCall:
        """Org-scoped API call without the ``/_apis`` suffix."""
        return ApiCall(
            access_token=self.token,
            url=_ADO_URL_ADAPTER.validate_python(self.org_url),
        )

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
            An ApiCall pointing at ``{org_url}/{name}/_apis``.
        """
        return ApiCall(
            access_token=self.token,
            url=_ADO_URL_ADAPTER.validate_python(f"{self.org_url}/{name}/_apis"),
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

    Holds credentials and resolves authentication from explicit arguments or
    environment variables. Acts as a factory and shared object cache so that
    resource objects obtained through different paths share identity — for
    example, ``build.project is wi.project`` is guaranteed when both belong to
    the same ADO project.

    Auth resolution order:

    1. Explicit ``pat`` argument.
    2. ``AZURE_DEVOPS_EXT_PAT`` environment variable.
    3. Explicit ``credential`` (any azure-identity ``TokenCredential``); a
       bearer token is acquired once at construction. Recreate the service to
       refresh the token.

    ``pat`` and ``credential`` are mutually exclusive.

    Org URL resolution order (when ``org`` is ``None``):

    1. ``AZURE_DEVOPS_ORG`` environment variable.
    2. ``SYSTEM_TEAMFOUNDATIONCOLLECTIONURI`` environment variable.

    Raises ``ValueError`` when no org URL is found.

    Attributes:
        _org_url: Organisation base URL, trailing slash stripped.
        _token: Resolved ADO access token.
        _org_api_call: Organisation-level API call.
        _cache: URL-keyed object cache (Project, Repository, Pipeline).
        _org_view: Cached Organisation singleton, or None before first access.
    """

    def __init__(
        self,
        *,
        org: str | None = None,
        pat: str | None = None,
        credential: "TokenCredential | None" = None,
    ) -> None:
        """Construct the service.

        Args:
            org: ADO organisation URL (e.g. ``"https://dev.azure.com/myorg"``).
                Falls back to ``AZURE_DEVOPS_ORG``, then
                ``SYSTEM_TEAMFOUNDATIONCOLLECTIONURI``.
            pat: Personal access token. Falls back to
                ``AZURE_DEVOPS_EXT_PAT``. Mutually exclusive with
                ``credential``.
            credential: Any azure-identity ``TokenCredential``. A bearer token
                is acquired immediately. Mutually exclusive with ``pat``.

        Raises:
            ValueError: If both ``pat`` and ``credential`` are provided, if no
                organisation URL can be resolved, or if no access token is
                available.
        """
        if pat is not None and credential is not None:
            err_msg = "Provide either 'pat' or 'credential', not both."
            raise ValueError(err_msg)

        resolved_org = (
            org
            or os.environ.get("AZURE_DEVOPS_ORG")
            or os.environ.get("SYSTEM_TEAMFOUNDATIONCOLLECTIONURI")
        )
        if not resolved_org:
            err_msg = (
                "Organisation URL is required. Provide 'org' or set "
                "AZURE_DEVOPS_ORG (or SYSTEM_TEAMFOUNDATIONCOLLECTIONURI)."
            )
            raise ValueError(err_msg)

        self._org_url = resolved_org.rstrip("/")

        if credential is not None:
            token_result = credential.get_token(f"{_ADO_RESOURCE_ID}/.default")
            self._token: AccessToken = token_result.token
        else:
            resolved_pat = pat or os.environ.get("AZURE_DEVOPS_EXT_PAT")
            if not resolved_pat:
                err_msg = (
                    "No access token found. Provide 'pat' or set AZURE_DEVOPS_EXT_PAT."
                )
                raise ValueError(err_msg)
            self._token = resolved_pat

        self._org_api_call = ApiCall(
            access_token=self._token,
            url=_ADO_URL_ADAPTER.validate_python(f"{self._org_url}/_apis"),
        )
        self._cache: dict[str, Any] = {}
        self._org_view: Organization | None = None

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
        return _OopApi(self._token, self._org_url, self._cache)

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Clear all cached objects.

        The next access to any cached resource (projects, repositories,
        pipelines) will create fresh objects from the API. The Organisation
        singleton is also recreated.
        """
        self._cache.clear()
        self._org_view = None
