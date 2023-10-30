"""Module with utilities to interact with Azure DevOps."""
import base64
import json as jsonlib
import pathlib
from contextlib import suppress
from html.parser import HTMLParser
from typing import Annotated
from typing import Any
from typing import Literal
from typing import Optional
from typing import TypeAlias
from uuid import UUID

import requests
from pydantic import BaseModel
from pydantic import PositiveInt
from pydantic.networks import HttpUrl
from pydantic.networks import UrlConstraints


class HTMLTextFilter(HTMLParser):
    """Filter HTML error pages for useful text."""

    def __init__(self) -> None:
        """Construct the HTML text filter."""
        self.text = ""
        super().__init__()
        self._tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Add tags to the stack."""
        self._tags.append(tag)

    def handle_endtag(self, tag: str) -> None:
        """Remove tags from the stack."""
        if self._tags.pop() != tag:
            raise ValueError("Invalid end tag!")

    def handle_data(self, data: str) -> None:
        """Add data if the tag context is correct."""
        if "style" in self._tags:
            return
        self.text = (self.text + " " + data.strip()).strip()


AccessToken: TypeAlias = str

ADOUrl: TypeAlias = Annotated[
    HttpUrl,
    UrlConstraints(
        max_length=256,
        allowed_schemes={
            "https",
        },
    ),
]


def _encode_as_base64(value: str) -> str:
    """Encode string as base64 string."""
    return base64.b64encode(value.encode("utf-8")).decode("utf-8")


class JsonPatchAdd(BaseModel):
    """Type to store JSON patch information to add data."""

    op: Literal["add"] = "add"
    path: str
    value: Any


def _is_json_patch(value: Any | list[Any] | list[dict[str, str]]) -> bool:
    """Check if the value is a JSON patch."""
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


def _get_content_type(has_data: bool, json_value: Any) -> str:
    """Get the appropriate content type."""
    if has_data:
        return "application/octet-stream"
    if _is_json_patch(json_value):
        return "application/json-patch+json"
    return "application/json"


class ApiCall(BaseModel):
    """Class to call Azure DevOps APIs."""

    access_token: AccessToken
    parameters: dict[str, int | str] = {}
    timeout: PositiveInt = 10
    url: ADOUrl

    def build_call(
        self,
        *args: str | int | UUID,
        parameters: Optional[dict[str, int | str]] = None,
        version: Optional[str] = None,
    ) -> "ApiCall":
        """Build API call from arguments."""
        parameters = parameters or {}
        if version is not None:
            parameters["api-version"] = version

        url_parts = [str(arg) for arg in args]
        new_url = "/".join([self.url.unicode_string().rstrip("/")] + url_parts)
        return ApiCall(
            access_token=self.access_token,
            parameters=parameters | self.parameters,
            timeout=self.timeout,
            url=ADOUrl(new_url),
        )

    @staticmethod
    def _get_error_message(response: requests.Response) -> str:
        """Construct useful error message."""
        with suppress(Exception):
            error_message: str = response.json()["message"]
            return error_message
        error_message = repr(response.content)
        with suppress(Exception):
            html_filter = HTMLTextFilter()
            html_filter.feed(response.content.decode("utf-8"))
            error_message = repr(html_filter.text)
        return f"Invalid error response: {error_message}"

    @staticmethod
    def _parse_response(response: requests.Response) -> Any:
        """Parse API response from Azure DevOps."""
        try:
            response.raise_for_status()
        except Exception as ex:
            error_message = ApiCall._get_error_message(response)
            raise RuntimeError(error_message) from ex
        if not response.content:  # Handle b'' return values
            return None
        try:
            return response.json()
        except Exception as ex:
            error_message = f"Invalid API response: {response.content!r}"
            raise ValueError(error_message) from ex

    @staticmethod
    def _request(
        method: str, api_call: "ApiCall", json: Any = None, data: Any = None
    ) -> Any:
        """Helper function to interact with the Azure DevOps API."""
        base64_auth = _encode_as_base64(f":{api_call.access_token}")
        headers = {
            "Authorization": f"Basic {base64_auth}",
            "Content-Type": _get_content_type(data is not None, json),
        }
        kwargs = {}
        if json is not None:
            kwargs = {"json": json}
        if data is not None:
            kwargs = {"data": data}
        session = requests.Session()
        response = session.request(
            method,
            headers=headers,
            params=api_call.parameters,
            timeout=api_call.timeout,
            url=api_call.url.unicode_string(),
            **kwargs,
        )
        return ApiCall._parse_response(response)

    def get(
        self,
        *args: str | int | UUID,
        parameters: Optional[dict[str, int | str]] = None,
        version: Optional[str] = None,
    ) -> Any:
        """Helper function to interact with the Azure DevOps API via GET."""
        api_call = self.build_call(*args, parameters=parameters, version=version)
        return ApiCall._request("GET", api_call)

    def put(
        self,
        *args: str | int | UUID,
        parameters: Optional[dict[str, int | str]] = None,
        version: Optional[str] = None,
        json: Any = None,
        data: Any = None,
    ) -> Any:
        """Helper function to interact with the Azure DevOps API via POST."""
        api_call = self.build_call(*args, parameters=parameters, version=version)
        return ApiCall._request("PUT", api_call, json=json, data=data)

    def post(
        self,
        *args: str | int | UUID,
        parameters: Optional[dict[str, int | str]] = None,
        version: Optional[str] = None,
        json: Any = None,
        data: Any = None,
    ) -> Any:
        """Helper function to interact with the Azure DevOps API via POST."""
        api_call = self.build_call(*args, parameters=parameters, version=version)
        return ApiCall._request("POST", api_call, json=json, data=data)

    def patch(
        self,
        *args: str | int | UUID,
        parameters: Optional[dict[str, int | str]] = None,
        version: Optional[str] = None,
        json: Any = None,
    ) -> Any:
        """Helper function to interact with the Azure DevOps API via PATCH."""
        api_call = self.build_call(*args, parameters=parameters, version=version)
        return ApiCall._request("PATCH", api_call, json=json)

    def delete(
        self,
        *args: str | int | UUID,
        parameters: Optional[dict[str, int | str]] = None,
        version: Optional[str] = None,
    ) -> Any:
        """Helper function to interact with the Azure DevOps API via DELETE."""
        api_call = self.build_call(*args, parameters=parameters, version=version)
        return ApiCall._request("DELETE", api_call)


def get_test_api_call() -> tuple[ApiCall, Any]:
    """Get API call object for testing."""
    test_config_file = pathlib.Path(__file__).resolve().parent / "test.json"
    test_config = jsonlib.load(test_config_file.open(encoding="utf-8"))
    test_api_call = ApiCall(
        access_token=test_config["access_token"], url=test_config["url"]
    )
    return test_api_call, test_config
