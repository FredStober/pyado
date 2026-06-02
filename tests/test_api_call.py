"""Tests for pyado.api_call module."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import io
import json
import pathlib
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from pyado.api_call import (
    ApiCall,
    HTMLTextFilter,
    JsonPatchAdd,
    _get_content_type,
    _is_json_patch,
    get_test_api_call,
)

BASE_URL = "https://dev.azure.com/org/"
ACCESS_TOKEN = "test_token"


def make_mock_response(
    *,
    json_data: Any = None,
    content: bytes | None = None,
    raise_for_status_exc: Exception | None = None,
) -> MagicMock:
    """Create a mock requests.Response.

    Returns:
        A MagicMock configured to behave as a requests.Response.
    """
    mock = MagicMock(spec=requests.Response)
    if raise_for_status_exc:
        mock.raise_for_status.side_effect = raise_for_status_exc
    else:
        mock.raise_for_status.return_value = None

    if json_data is not None:
        mock.json.return_value = json_data
        mock.content = json.dumps(json_data).encode()
    elif content is not None:
        mock.content = content
        mock.json.side_effect = ValueError("not json")
    else:
        mock.content = b""
        mock.json.side_effect = ValueError("empty")

    return mock


class TestHTMLTextFilter:
    """Tests for HTMLTextFilter."""

    @staticmethod
    def test_init_sets_empty_text() -> None:
        """Filter starts with empty text."""
        html_filter = HTMLTextFilter()
        assert not html_filter.text

    @staticmethod
    def test_handle_data_appends_text() -> None:
        """Data outside style tags is accumulated in text."""
        html_filter = HTMLTextFilter()
        html_filter.handle_starttag("p", [])
        html_filter.handle_data("hello")
        assert html_filter.text == "hello"

    @staticmethod
    def test_handle_data_skips_inside_style_tag() -> None:
        """Data inside a style tag is ignored."""
        html_filter = HTMLTextFilter()
        html_filter.handle_starttag("style", [])
        html_filter.handle_data("body { color: red; }")
        assert not html_filter.text

    @staticmethod
    def test_handle_data_strips_and_concatenates() -> None:
        """Multiple data segments are joined with a single space."""
        html_filter = HTMLTextFilter()
        html_filter.handle_starttag("p", [])
        html_filter.handle_data("  hello  ")
        html_filter.handle_endtag("p")
        html_filter.handle_starttag("p", [])
        html_filter.handle_data("  world  ")
        assert html_filter.text == "hello world"

    @staticmethod
    def test_handle_endtag_matching_tag() -> None:
        """Matching end tag is removed from the stack without error."""
        html_filter = HTMLTextFilter()
        html_filter.handle_starttag("p", [])
        html_filter.handle_endtag("p")  # Should not raise

    @staticmethod
    def test_handle_endtag_mismatched_raises() -> None:
        """Mismatched end tag raises ValueError."""
        html_filter = HTMLTextFilter()
        html_filter.handle_starttag("p", [])
        with pytest.raises(ValueError, match="Invalid end tag!"):
            html_filter.handle_endtag("div")

    @staticmethod
    def test_feed_full_html() -> None:
        """Full HTML document is parsed and text extracted."""
        html_filter = HTMLTextFilter()
        html_filter.feed("<html><body><p>content</p></body></html>")
        assert html_filter.text == "content"


class TestIsJsonPatch:
    """Tests for _is_json_patch."""

    @staticmethod
    def test_non_list_returns_false() -> None:
        """Non-list input returns False."""
        assert _is_json_patch("string") is False

    @staticmethod
    def test_empty_list_returns_true() -> None:
        """Empty list is considered a valid (empty) patch."""
        assert _is_json_patch([]) is True

    @staticmethod
    def test_list_with_non_dict_returns_false() -> None:
        """List containing a non-dict returns False."""
        assert _is_json_patch([1, 2]) is False

    @staticmethod
    def test_dict_missing_op_returns_false() -> None:
        """Dict without 'op' key returns False."""
        assert _is_json_patch([{"path": "/a"}]) is False

    @staticmethod
    def test_dict_missing_path_returns_false() -> None:
        """Dict without 'path' key returns False."""
        assert _is_json_patch([{"op": "add"}]) is False

    @staticmethod
    def test_valid_patch_returns_true() -> None:
        """Dict with both 'op' and 'path' returns True."""
        assert _is_json_patch([{"op": "add", "path": "/a", "value": 1}]) is True


class TestGetContentType:
    """Tests for _get_content_type."""

    @staticmethod
    def test_has_data_returns_octet_stream() -> None:
        """Binary data triggers octet-stream content type."""
        result = _get_content_type(has_data=True, json_value=None)
        assert result == "application/octet-stream"

    @staticmethod
    def test_json_patch_returns_json_patch_type() -> None:
        """JSON patch list triggers json-patch content type."""
        patch_value = [{"op": "add", "path": "/a"}]
        result = _get_content_type(has_data=False, json_value=patch_value)
        assert result == "application/json-patch+json"

    @staticmethod
    def test_regular_json_returns_application_json() -> None:
        """Regular dict triggers application/json content type."""
        result = _get_content_type(has_data=False, json_value={"key": "val"})
        assert result == "application/json"


class TestApiCallBuildCall:
    """Tests for ApiCall.build_call."""

    @staticmethod
    def test_build_call_appends_path_segments() -> None:
        """Path segments are appended to the base URL."""
        api_call = ApiCall(access_token=ACCESS_TOKEN, url=BASE_URL)
        result = api_call.build_call("projects", "myproject")
        assert "projects/myproject" in result.url.unicode_string()

    @staticmethod
    def test_build_call_adds_version_parameter() -> None:
        """Version is added as api-version query parameter."""
        api_call = ApiCall(access_token=ACCESS_TOKEN, url=BASE_URL)
        result = api_call.build_call("resource", version="7.0")
        assert result.parameters["api-version"] == "7.0"

    @staticmethod
    def test_build_call_without_version_no_api_version_param() -> None:
        """Without version, no api-version parameter is added."""
        api_call = ApiCall(access_token=ACCESS_TOKEN, url=BASE_URL)
        result = api_call.build_call("resource")
        assert "api-version" not in result.parameters

    @staticmethod
    def test_build_call_merges_parameters() -> None:
        """Provided parameters are merged with existing ones."""
        api_call = ApiCall(
            access_token=ACCESS_TOKEN, url=BASE_URL, parameters={"base": "param"}
        )
        result = api_call.build_call("resource", parameters={"extra": "value"})
        assert result.parameters["base"] == "param"
        assert result.parameters["extra"] == "value"

    @staticmethod
    def test_build_call_inherits_access_token() -> None:
        """Access token is preserved in the new ApiCall."""
        api_call = ApiCall(access_token=ACCESS_TOKEN, url=BASE_URL)
        result = api_call.build_call("path")
        assert result.access_token == ACCESS_TOKEN


class TestApiCallGetErrorMessage:
    """Tests for ApiCall._get_error_message."""

    @staticmethod
    def test_json_with_message_key_returns_message() -> None:
        """JSON response with 'message' key returns that message."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.json.return_value = {"message": "something went wrong"}
        result = ApiCall._get_error_message(mock_response)
        assert result == "something went wrong"

    @staticmethod
    def test_json_without_message_key_uses_html_text() -> None:
        """JSON response without 'message' falls back to HTML parsing."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.json.return_value = {"other": "value"}
        mock_response.content = b"<p>Error text here</p>"
        result = ApiCall._get_error_message(mock_response)
        assert "Error text here" in result

    @staticmethod
    def test_json_fails_html_decode_fails_uses_content_repr() -> None:
        """If both JSON and HTML parsing fail, content repr is used."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.json.side_effect = ValueError("bad json")
        mock_response.content = b"\xff"  # invalid UTF-8
        result = ApiCall._get_error_message(mock_response)
        assert "Invalid error response" in result
        assert repr(b"\xff") in result


class TestApiCallParseResponse:
    """Tests for ApiCall._parse_response."""

    @staticmethod
    def test_failed_response_raises_runtime_error() -> None:
        """HTTP error response raises RuntimeError with message."""
        mock_response = make_mock_response(
            json_data={"message": "not found"},
            raise_for_status_exc=requests.HTTPError("404"),
        )
        with pytest.raises(RuntimeError, match="not found"):
            ApiCall._parse_response(mock_response)

    @staticmethod
    def test_raw_true_returns_bytes() -> None:
        """raw=True returns raw bytes content."""
        mock_response = make_mock_response(json_data={"key": "value"})
        result = ApiCall._parse_response(mock_response, raw=True)
        assert result == mock_response.content

    @staticmethod
    def test_empty_content_returns_none() -> None:
        """Empty response content returns None."""
        mock_response = make_mock_response()
        result = ApiCall._parse_response(mock_response)
        assert result is None

    @staticmethod
    def test_valid_json_returns_parsed_dict() -> None:
        """Valid JSON content returns parsed dict."""
        mock_response = make_mock_response(json_data={"key": "value"})
        result = ApiCall._parse_response(mock_response)
        assert result == {"key": "value"}

    @staticmethod
    def test_invalid_json_raises_value_error() -> None:
        """Non-JSON content raises ValueError."""
        mock_response = make_mock_response(content=b"not json at all")
        with pytest.raises(ValueError, match="Invalid API response"):
            ApiCall._parse_response(mock_response)


class TestApiCallGetSession:
    """Tests for ApiCall._get_session."""

    @staticmethod
    def test_creates_session_with_auth() -> None:
        """Session is created with basic auth using the access token."""
        session = ApiCall._get_session("mytoken")
        assert isinstance(session, requests.Session)
        assert session.auth is not None

    @staticmethod
    def test_same_token_returns_cached_session() -> None:
        """The same token always returns the same session object."""
        session_1 = ApiCall._get_session("token_a")
        session_2 = ApiCall._get_session("token_a")
        assert session_1 is session_2

    @staticmethod
    def test_different_tokens_return_different_sessions() -> None:
        """Different tokens produce distinct session objects."""
        session_1 = ApiCall._get_session("token_a")
        session_2 = ApiCall._get_session("token_b")
        assert session_1 is not session_2


class TestApiCallRequest:
    """Tests for ApiCall._request."""

    @staticmethod
    def test_successful_get_request(api_call: ApiCall) -> None:
        """Successful GET returns parsed response."""
        mock_response = make_mock_response(json_data={"result": "ok"})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = ApiCall._request("GET", api_call)
        assert result == {"result": "ok"}

    @staticmethod
    def test_request_with_json_body(api_call: ApiCall) -> None:
        """Request with json body passes json kwarg to session."""
        mock_response = make_mock_response(json_data={})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            ApiCall._request("POST", api_call, json={"payload": 1})
        call_kwargs = mock_req.call_args
        assert "json" in call_kwargs.kwargs or "json" in str(call_kwargs)

    @staticmethod
    def test_request_with_data_body(api_call: ApiCall) -> None:
        """Request with data body passes data kwarg to session."""
        mock_response = make_mock_response(json_data={})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            ApiCall._request("PUT", api_call, data=b"rawdata")
        call_kwargs = mock_req.call_args
        assert "data" in call_kwargs.kwargs or "data" in str(call_kwargs)

    @staticmethod
    def test_raw_flag_returns_bytes(api_call: ApiCall) -> None:
        """raw=True returns bytes from response.content."""
        mock_response = make_mock_response(json_data={"key": "val"})
        with patch.object(requests.Session, "request", return_value=mock_response):
            result = ApiCall._request("GET", api_call, raw=True)
        assert result == mock_response.content

    @staticmethod
    def test_connection_reset_retries_and_succeeds(api_call: ApiCall) -> None:
        """ConnectionResetError triggers a retry that eventually succeeds."""
        mock_response = make_mock_response(json_data={"ok": True})
        side_effects = [ConnectionResetError(), mock_response]
        with patch.object(requests.Session, "request", side_effect=side_effects):
            result = ApiCall._request("GET", api_call)
        assert result == {"ok": True}

    @staticmethod
    def test_connection_reset_raises_on_final_retry(api_call: ApiCall) -> None:
        """ConnectionResetError on the last retry propagates the exception."""
        side_effects = [
            ConnectionResetError(),
            ConnectionResetError(),
            ConnectionResetError(),
        ]
        with (
            patch.object(requests.Session, "request", side_effect=side_effects),
            pytest.raises(ConnectionResetError),
        ):
            ApiCall._request("GET", api_call)


class TestApiCallHttpMethods:
    """Tests for ApiCall HTTP method wrappers."""

    @staticmethod
    def _mock_session_request(json_data: Any = None) -> MagicMock:
        return make_mock_response(json_data=json_data or {})

    @staticmethod
    def test_get_calls_session_request(api_call: ApiCall) -> None:
        """get() issues a GET request."""
        mock_response = TestApiCallHttpMethods._mock_session_request()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            api_call.get("resource", version="7.0")
        mock_req.assert_called_once()
        assert mock_req.call_args.args[0] == "GET"

    @staticmethod
    def test_get_raw_calls_session_request(api_call: ApiCall) -> None:
        """get_raw() issues a GET request and returns raw bytes."""
        mock_response = TestApiCallHttpMethods._mock_session_request(json_data={"x": 1})
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            result = api_call.get_raw("resource")
        mock_req.assert_called_once()
        assert isinstance(result, bytes)

    @staticmethod
    def test_put_calls_session_request(api_call: ApiCall) -> None:
        """put() issues a PUT request."""
        mock_response = TestApiCallHttpMethods._mock_session_request()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            api_call.put("resource", json={"a": 1})
        assert mock_req.call_args.args[0] == "PUT"

    @staticmethod
    def test_post_calls_session_request(api_call: ApiCall) -> None:
        """post() issues a POST request."""
        mock_response = TestApiCallHttpMethods._mock_session_request()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            api_call.post("resource", json={"b": 2})
        assert mock_req.call_args.args[0] == "POST"

    @staticmethod
    def test_patch_calls_session_request(api_call: ApiCall) -> None:
        """patch() issues a PATCH request."""
        mock_response = TestApiCallHttpMethods._mock_session_request()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            api_call.patch("resource", json=[{"op": "add", "path": "/x"}])
        assert mock_req.call_args.args[0] == "PATCH"

    @staticmethod
    def test_delete_calls_session_request(api_call: ApiCall) -> None:
        """delete() issues a DELETE request."""
        mock_response = TestApiCallHttpMethods._mock_session_request()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            api_call.delete("resource")
        assert mock_req.call_args.args[0] == "DELETE"

    @staticmethod
    def test_put_with_data(api_call: ApiCall) -> None:
        """put() accepts raw data body."""
        mock_response = TestApiCallHttpMethods._mock_session_request()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            api_call.put("resource", data=b"rawbytes")
        mock_req.assert_called_once()

    @staticmethod
    def test_post_with_data(api_call: ApiCall) -> None:
        """post() accepts raw data body."""
        mock_response = TestApiCallHttpMethods._mock_session_request()
        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_req:
            api_call.post("resource", data=b"rawbytes")
        mock_req.assert_called_once()


class TestGetTestApiCall:
    """Tests for get_test_api_call."""

    @staticmethod
    def test_returns_api_call_and_config() -> None:
        """get_test_api_call returns configured ApiCall and raw config dict."""
        config = {"access_token": "mytoken", "url": "https://dev.azure.com/myorg/"}
        mock_file = io.StringIO(json.dumps(config))
        with patch.object(pathlib.Path, "open", return_value=mock_file):
            api_call, returned_config = get_test_api_call()
        assert api_call.access_token == "mytoken"
        assert returned_config == config


class TestJsonPatchAdd:
    """Tests for JsonPatchAdd model."""

    @staticmethod
    def test_default_op_is_add() -> None:
        """JsonPatchAdd defaults to op='add'."""
        patch_op = JsonPatchAdd(path="/fields/key", value="val")
        assert patch_op.op == "add"

    @staticmethod
    def test_model_dump_produces_correct_keys() -> None:
        """model_dump produces expected keys for JSON serialization."""
        patch_op = JsonPatchAdd(path="/fields/key", value=42)
        dumped = patch_op.model_dump(mode="json")
        assert dumped["op"] == "add"
        assert dumped["path"] == "/fields/key"
        assert dumped["value"] == 42
