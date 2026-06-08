"""HTTP client infrastructure and shared primitive types for pyado.raw submodules."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import os
from contextlib import suppress
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Annotated, Any, Literal, TypeAlias
from uuid import UUID

if TYPE_CHECKING:
    from azure.core.credentials import TokenCredential

import requests
import requests.auth
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, TypeAdapter
from pydantic.networks import HttpUrl, UrlConstraints

from pyado.exceptions import (
    AzureDevOpsAuthError,
    AzureDevOpsBadRequestError,
    AzureDevOpsConflictError,
    AzureDevOpsError,
    AzureDevOpsHttpError,
    AzureDevOpsNotFoundError,
)

__all__ = [
    "AccessToken",
    "AdoUrl",
    "ApiCall",
    "AzureDevOpsAuthError",
    "AzureDevOpsBadRequestError",
    "AzureDevOpsConflictError",
    "AzureDevOpsError",
    "AzureDevOpsHttpError",
    "AzureDevOpsNotFoundError",
    "HtmlTextFilter",
    "JsonPatchAdd",
    "JsonPatchRemove",
    "get_session",
]

# `OAuth` scope for Azure DevOps
_ADO_GRAPH_SCOPE = "499b84ac-1321-427f-aa17-267ca6975798/.default"


def to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class AdoBaseModel(BaseModel):
    """Base model for Azure DevOps REST models."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class HtmlTextFilter(HTMLParser):
    """Filter HTML error pages for useful text."""

    def __init__(self) -> None:
        """Construct the HTML text filter."""
        self.text = ""
        super().__init__()
        self._tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Add tags to the stack."""
        del attrs
        self._tags.append(tag)

    def handle_endtag(self, tag: str) -> None:
        """Remove tags from the stack.

        Raises:
            ValueError: If the closing tag does not match the open tag.
        """
        if self._tags.pop() != tag:
            err_msg = "Invalid end tag!"
            raise ValueError(err_msg)

    def handle_data(self, data: str) -> None:
        """Add data if the tag context is correct."""
        if "style" in self._tags:
            return
        self.text = (self.text + " " + data.strip()).strip()


AccessToken: TypeAlias = str

#: Validated HTTPS URL accepted by ADO API calls (max 256 characters).
AdoUrl: TypeAlias = Annotated[
    HttpUrl,
    UrlConstraints(
        max_length=256,
        allowed_schemes=[
            "https",
        ],
    ),
]
_ADO_URL_ADAPTER: TypeAdapter[AdoUrl] = TypeAdapter(AdoUrl)


_HTTP_EXCEPTION_MAP: dict[int, type[AzureDevOpsHttpError]] = {
    400: AzureDevOpsBadRequestError,
    401: AzureDevOpsAuthError,
    403: AzureDevOpsAuthError,
    404: AzureDevOpsNotFoundError,
    409: AzureDevOpsConflictError,
}


class JsonPatchAdd(AdoBaseModel):
    """Type to store JSON patch information to add data."""

    op: Literal["add"] = "add"
    path: str
    value: Any


class JsonPatchRemove(AdoBaseModel):
    """Type to store JSON patch information to remove data."""

    op: Literal["remove"] = "remove"
    path: str


def _is_json_patch(value: Any | list[Any] | list[dict[str, str]]) -> bool:
    """Check if the value is a JSON patch.

    Returns:
        True if the value is a list of JSON patch operations, False otherwise.
    """
    if not isinstance(value, list):
        return False
    for item in value:
        if not isinstance(item, dict):
            return False
        if "op" not in item:
            return False
        if "path" not in item:
            return False
    return True


class _BearerAuth(requests.auth.AuthBase):
    """Auth handler that injects an ``Authorization: Bearer`` header."""

    def __init__(self, token: str) -> None:
        """Construct the auth handler.

        Args:
            token: OAuth bearer token string.
        """
        self._token = token

    def __call__(self, r: requests.PreparedRequest) -> requests.PreparedRequest:
        """Attach the Authorization header to the request.

        Returns:
            The modified PreparedRequest with the Authorization header set.
        """
        r.headers["Authorization"] = f"Bearer {self._token}"
        return r


def _setup_session(
    session: requests.Session,
    pat: str | None = None,
    bearer_token: str | None = None,
    azure_credentials: "TokenCredential | None" = None,
) -> requests.Session:
    """Configure *session* with auth and return it.

    Disables ``trust_env`` to prevent netrc credentials (which may contain a
    repo-scoped token) from overriding the explicitly supplied ADO token.
    Falls back to the ``AZURE_DEVOPS_EXT_PAT`` environment variable when no
    other token source is provided.  If nothing is available, the session is
    returned unconfigured (auth remains whatever the caller set).

    Args:
        session: Session to configure in-place.
        pat: ADO personal access token.  Falls back to
            ``AZURE_DEVOPS_EXT_PAT``.
        bearer_token: Pre-acquired OAuth bearer token string.
        azure_credentials: Any azure-identity ``TokenCredential``.  A bearer
            token is acquired immediately using the ADO resource scope.

    Returns:
        The same session, configured with auth when a token source is found.
    """
    session.trust_env = False
    if azure_credentials is not None:
        bearer_token = azure_credentials.get_token(_ADO_GRAPH_SCOPE).token
    if bearer_token is not None:
        session.auth = _BearerAuth(bearer_token)
        return session
    resolved_pat = pat or os.environ.get("AZURE_DEVOPS_EXT_PAT")
    if resolved_pat is not None:
        session.auth = requests.auth.HTTPBasicAuth("", resolved_pat)
    return session


def _get_content_type(*, has_data: bool, json_value: Any) -> str:
    """Get the appropriate content type.

    Returns:
        The MIME content type string for the request.
    """
    if has_data:
        return "application/octet-stream"
    if _is_json_patch(json_value):
        return "application/json-patch+json"
    return "application/json"


class ApiCall(BaseModel):
    """Class to call Azure DevOps APIs.

    Pass a session from :func:`get_session` to authenticate requests.  When
    no session is provided a plain unauthenticated session is used.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    session: requests.Session = Field(default_factory=requests.Session)
    parameters: dict[str, int | str | bool] = {}
    timeout: PositiveInt = 10
    url: AdoUrl

    def build_call(
        self,
        *args: str | int | UUID,
        parameters: dict[str, int | str | bool] | None = None,
        version: str | None = None,
    ) -> "ApiCall":
        """Build API call from arguments.

        Returns:
            A new ApiCall with the appended path and merged parameters.
        """
        parameters = parameters or {}
        if version is not None:
            parameters["api-version"] = version

        url_parts = [str(arg) for arg in args]
        new_url = "/".join([self.url.unicode_string().rstrip("/"), *url_parts])
        return ApiCall(
            session=self.session,
            parameters=parameters | self.parameters,
            timeout=self.timeout,
            url=_ADO_URL_ADAPTER.validate_python(new_url),
        )

    @staticmethod
    def _get_error_message(response: requests.Response) -> str:
        """Construct useful error message.

        Returns:
            A human-readable error message extracted from the response.
        """
        with suppress(Exception):
            error_message: str = response.json()["message"]
            return error_message
        error_message = repr(response.content)
        with suppress(Exception):
            html_filter = HtmlTextFilter()
            html_filter.feed(response.content.decode("utf-8"))
            error_message = repr(html_filter.text)
        return f"Invalid error response: {error_message}"

    @staticmethod
    def _parse_response(response: requests.Response, *, raw: bool = False) -> Any:
        """Parse API response from Azure DevOps.

        Returns:
            The parsed JSON response, raw bytes if raw is True, or None if empty.

        Raises:
            ValueError: If the response body cannot be parsed as JSON.
        """
        try:
            response.raise_for_status()
        except Exception as ex:
            error_message = ApiCall._get_error_message(response)
            exc_class = _HTTP_EXCEPTION_MAP.get(
                response.status_code, AzureDevOpsHttpError
            )
            raise exc_class(response.status_code, error_message) from ex
        if raw:
            return response.content
        if not response.content:  # Handle b'' return values
            return None
        try:
            return response.json()
        except Exception as ex:
            error_message = f"Invalid API response: {response.content!r}"
            raise ValueError(error_message) from ex

    @staticmethod
    def _request(
        method: str,
        api_call: "ApiCall",
        json: Any = None,
        data: Any = None,
        *,
        raw: bool = False,
    ) -> Any:
        """Helper function to interact with the Azure DevOps API.

        Returns:
            The parsed API response.

        Raises:
            ConnectionResetError: If all retry attempts fail due to a reset.
        """
        headers = {
            "Content-Type": _get_content_type(
                has_data=data is not None, json_value=json
            ),
        }
        kwargs = {}
        if json is not None:
            kwargs = {"json": json}
        if data is not None:
            kwargs = {"data": data}
        session = api_call.session
        max_retries = 3
        for retry in range(max_retries, 0, -1):  # max_retries, ..., 1
            try:
                response = session.request(
                    method,
                    headers=headers,
                    params=api_call.parameters,
                    timeout=api_call.timeout,
                    url=api_call.url.unicode_string(),
                    **kwargs,
                )
                return ApiCall._parse_response(response, raw=raw)
            except ConnectionResetError:
                if retry == 1:
                    raise
        return None  # pragma: no cover

    def get(
        self,
        *args: str | int | UUID,
        parameters: dict[str, int | str | bool] | None = None,
        version: str | None = None,
    ) -> Any:
        """Helper function to interact with the Azure DevOps API via GET.

        Returns:
            The parsed API response.
        """
        api_call = self.build_call(*args, parameters=parameters, version=version)
        return ApiCall._request("GET", api_call)

    def get_raw(
        self,
        *args: str | int | UUID,
        parameters: dict[str, int | str | bool] | None = None,
        version: str | None = None,
    ) -> Any:
        """Helper function to interact with the Azure DevOps API via GET.

        Returns:
            The raw bytes content of the response.
        """
        api_call = self.build_call(*args, parameters=parameters, version=version)
        return ApiCall._request("GET", api_call, raw=True)

    def put(
        self,
        *args: str | int | UUID,
        parameters: dict[str, int | str | bool] | None = None,
        version: str | None = None,
        json: Any = None,
        data: Any = None,
    ) -> Any:
        """Helper function to interact with the Azure DevOps API via PUT.

        Returns:
            The parsed API response.
        """
        api_call = self.build_call(*args, parameters=parameters, version=version)
        return ApiCall._request("PUT", api_call, json=json, data=data)

    def post(
        self,
        *args: str | int | UUID,
        parameters: dict[str, int | str | bool] | None = None,
        version: str | None = None,
        json: Any = None,
        data: Any = None,
    ) -> Any:
        """Helper function to interact with the Azure DevOps API via POST.

        Returns:
            The parsed API response.
        """
        api_call = self.build_call(*args, parameters=parameters, version=version)
        return ApiCall._request("POST", api_call, json=json, data=data)

    def patch(
        self,
        *args: str | int | UUID,
        parameters: dict[str, int | str | bool] | None = None,
        version: str | None = None,
        json: Any = None,
    ) -> Any:
        """Helper function to interact with the Azure DevOps API via PATCH.

        Returns:
            The parsed API response.
        """
        api_call = self.build_call(*args, parameters=parameters, version=version)
        return ApiCall._request("PATCH", api_call, json=json)

    def delete(
        self,
        *args: str | int | UUID,
        parameters: dict[str, int | str | bool] | None = None,
        version: str | None = None,
    ) -> Any:
        """Helper function to interact with the Azure DevOps API via DELETE.

        Returns:
            The parsed API response.
        """
        api_call = self.build_call(*args, parameters=parameters, version=version)
        return ApiCall._request("DELETE", api_call)


def get_session(
    pat: str | None = None,
    bearer_token: str | None = None,
    azure_credentials: "TokenCredential | None" = None,
) -> requests.Session:
    """Return a new session configured via :func:`_setup_session`.

    Args:
        pat: ADO personal access token.  Falls back to
            ``AZURE_DEVOPS_EXT_PAT``.
        bearer_token: Pre-acquired OAuth bearer token string.
        azure_credentials: Any azure-identity ``TokenCredential``.  A bearer
            token is acquired immediately using the ADO resource scope.

    Returns:
        A new requests.Session configured with the supplied credentials.
    """
    return _setup_session(
        requests.Session(),
        pat=pat,
        bearer_token=bearer_token,
        azure_credentials=azure_credentials,
    )


class _IdentityRef(AdoBaseModel):
    """Minimal identity reference as returned across ADO REST responses."""

    id: str
    display_name: str
    unique_name: str | None = None
    url: AdoUrl | None = None
    image_url: AdoUrl | None = None
