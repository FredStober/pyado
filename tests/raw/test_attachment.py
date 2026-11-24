"""Unit tests for pyado.raw.pipelines.attachment."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import gzip
from unittest.mock import patch

import pytest
import requests

from pyado.raw import (
    SUMMARY_ATTACHMENT_TYPE,
    ApiCall,
    BuildAttachmentInfo,
    get_build_container_id,
    get_container_api_call,
    get_container_item_bytes,
    get_container_item_text,
    iter_build_attachments,
    iter_build_summaries,
    iter_container_items,
    make_container_artifact_data,
    make_report_artifact_request,
    post_build_artifact,
    publish_coverage_report,
    put_container_file,
    put_record_attachment,
    put_record_summaries,
)
from tests.conftest import _make_mock_response

RECORD_ID = "0b7d3a5e-aaaa-bbbb-cccc-1234567890ab"


class TestPutRecordAttachment:
    """Tests for put_record_attachment."""

    @staticmethod
    def test_puts_the_bytes_to_the_attachment_path(api_call: ApiCall) -> None:
        """The file goes to .../records/{id}/attachments/{type}/{name} as bytes."""
        response = _make_mock_response({"name": "sum", "type": SUMMARY_ATTACHMENT_TYPE})
        with patch.object(
            requests.Session, "request", return_value=response
        ) as mock_req:
            result = put_record_attachment(
                api_call, RECORD_ID, SUMMARY_ATTACHMENT_TYPE, "sum", b"# hi"
            )
        call = mock_req.call_args
        assert call.args[0] == "PUT"
        url = call.kwargs["url"]
        assert url.endswith(
            f"/records/{RECORD_ID}/attachments/{SUMMARY_ATTACHMENT_TYPE}/sum"
        )
        assert call.kwargs["data"] == b"# hi"
        assert result.name == "sum"


class TestContainer:
    """Tests for the file-container functions."""

    @staticmethod
    def test_container_call_is_organisation_level(api_call: ApiCall) -> None:
        """The container path has _apis/resources/Containers/{id} (no project)."""
        call = get_container_api_call(api_call, 77)
        assert str(call.url).endswith("/_apis/resources/Containers/77")

    @staticmethod
    def test_put_sends_content_range_and_item_path(api_call: ApiCall) -> None:
        """A PUT carries the itemPath parameter and the Content-Range header."""
        container = get_container_api_call(api_call, 77)
        response = _make_mock_response(
            {"path": "f/a.html", "itemType": "file", "fileLength": 5}
        )
        with patch.object(
            requests.Session, "request", return_value=response
        ) as mock_req:
            item = put_container_file(container, "f/a.html", b"hello")
        call = mock_req.call_args
        assert call.args[0] == "PUT"
        assert call.kwargs["params"]["itemPath"] == "f/a.html"
        assert call.kwargs["headers"]["Content-Range"] == "bytes 0-4/5"
        assert item.file_length == 5

    @staticmethod
    def test_put_refuses_an_empty_file(api_call: ApiCall) -> None:
        """A range header cannot express zero bytes."""
        container = get_container_api_call(api_call, 77)
        with pytest.raises(ValueError, match="empty file"):
            put_container_file(container, "f/a.html", b"")

    @staticmethod
    def test_iter_lists_items(api_call: ApiCall) -> None:
        """The listing yields every item of the folder."""
        container = get_container_api_call(api_call, 77)
        response = _make_mock_response(
            {
                "value": [
                    {"path": "f", "itemType": "folder"},
                    {"path": "f/a", "itemType": "file", "fileLength": 3},
                ]
            }
        )
        with patch.object(
            requests.Session, "request", return_value=response
        ) as mock_req:
            items = list(iter_container_items(container, "f"))
        assert [i.path for i in items] == ["f", "f/a"]
        assert mock_req.call_args.kwargs["params"]["itemPath"] == "f"

    @staticmethod
    def test_get_item_text_decodes_utf8(api_call: ApiCall) -> None:
        """The raw bytes of a file come back as text."""
        container = get_container_api_call(api_call, 77)
        response = _make_mock_response()
        response.content = "äöü".encode()
        with patch.object(requests.Session, "request", return_value=response):
            assert get_container_item_text(container, "f/a.html") == "äöü"


class TestReportArtifact:
    """Tests for the report artifact helpers."""

    @staticmethod
    def test_artifact_data_string() -> None:
        """The data string is #/<container>/<folder>."""
        assert make_container_artifact_data(5, "Rep_1") == "#/5/Rep_1"

    @staticmethod
    def test_report_request_is_browsable_container() -> None:
        """The request names the folder and marks it browsable with its size."""
        request = make_report_artifact_request(5, "Rep_1", size=177)
        dumped = request.model_dump(by_alias=True, mode="json")
        assert dumped["name"] == "Rep_1"
        assert dumped["resource"]["type"] == "Container"
        assert dumped["resource"]["data"] == "#/5/Rep_1"
        assert dumped["resource"]["properties"] == {
            "Browsable": "True",
            "artifactsize": "177",
        }

    @staticmethod
    def test_report_request_can_be_not_browsable() -> None:
        """browsable=False is sent as the string False."""
        request = make_report_artifact_request(5, "Rep_1", size=1, browsable=False)
        assert request.resource.properties["Browsable"] == "False"

    @staticmethod
    def test_post_build_artifact(api_call: ApiCall) -> None:
        """The artifact is POSTed to build/builds/{id}/artifacts as JSON."""
        response = _make_mock_response(
            {
                "id": 1,
                "name": "Rep_1",
                "resource": {
                    "type": "Container",
                    "data": "#/5/Rep_1",
                    "url": "https://dev.azure.com/org/_apis/build/builds/9/artifacts",
                },
            }
        )
        with patch.object(
            requests.Session, "request", return_value=response
        ) as mock_req:
            artifact = post_build_artifact(
                api_call, 9, make_report_artifact_request(5, "Rep_1", size=1)
            )
        call = mock_req.call_args
        assert call.args[0] == "POST"
        assert call.kwargs["url"].endswith("/build/builds/9/artifacts")
        assert call.kwargs["json"]["name"] == "Rep_1"
        assert artifact.name == "Rep_1"

    @staticmethod
    def test_get_item_text_does_not_double_encode_the_path(
        api_call: ApiCall,
    ) -> None:
        """A path with a space reaches requests unquoted (requests encodes it once).

        Pre-quoting turned the space into %20 and requests then encoded the %,
        so the server looked for a folder literally named ``Code%20Coverage``.
        """
        container = get_container_api_call(api_call, 77)
        response = _make_mock_response()
        response.content = b"x"
        with patch.object(
            requests.Session, "request", return_value=response
        ) as mock_req:
            get_container_item_text(container, "Code Coverage Report_1/index.html")
        sent = mock_req.call_args.kwargs["params"]["itemPath"]
        assert sent == "Code Coverage Report_1/index.html"

    @staticmethod
    def test_get_item_text_decompresses_gzip(api_call: ApiCall) -> None:
        """A gzip-compressed file (leading 1f 8b) is decompressed before decoding."""
        container = get_container_api_call(api_call, 77)
        response = _make_mock_response()
        response.content = gzip.compress("zip äöü".encode())
        with patch.object(requests.Session, "request", return_value=response):
            assert get_container_item_text(container, "f/a.gz") == "zip äöü"


class TestBuildContainerId:
    """Tests for get_build_container_id."""

    @staticmethod
    def _artifacts(*data: str) -> dict[str, object]:
        return {
            "value": [
                {
                    "id": i,
                    "name": f"a{i}",
                    "resource": {"type": "Container", "data": d, "url": "u"},
                }
                for i, d in enumerate(data, start=1)
            ]
        }

    def test_the_id_is_read_from_a_container_artifact(self, api_call: ApiCall) -> None:
        """The number after #/ in the artifact data is the container id."""
        response = _make_mock_response(self._artifacts("#/100816538/Report_1"))
        with patch.object(requests.Session, "request", return_value=response):
            assert get_build_container_id(api_call, 9) == 100816538

    def test_other_artifact_types_are_skipped(self, api_call: ApiCall) -> None:
        """An artifact whose data is not a container path is ignored."""
        response = _make_mock_response(self._artifacts("", "\\\\share\\x", "#/5/f"))
        with patch.object(requests.Session, "request", return_value=response):
            assert get_build_container_id(api_call, 9) == 5

    def test_without_artifact_the_organisation_list_is_asked(
        self, api_call: ApiCall
    ) -> None:
        """A build that published nothing still owns a BUILD_<id> container."""
        responses = [
            _make_mock_response(self._artifacts()),
            _make_mock_response(
                {"count": 1, "value": [{"id": 4711, "name": "BUILD_9"}]}
            ),
        ]
        with patch.object(requests.Session, "request", side_effect=responses) as req:
            assert get_build_container_id(api_call, 9) == 4711
        url = str(req.call_args_list[1].kwargs["url"])
        assert "/_apis/resources/Containers" in url
        assert "/main/" not in url
        assert req.call_args_list[1].kwargs["params"]["artifactUris"] == (
            "vstfs:///Build/Build/9"
        )

    def test_no_container_at_all_means_no_id(self, api_call: ApiCall) -> None:
        """A deleted build has neither artifact nor container."""
        responses = [
            _make_mock_response(self._artifacts()),
            _make_mock_response({"count": 0, "value": []}),
        ]
        with patch.object(requests.Session, "request", side_effect=responses):
            assert get_build_container_id(api_call, 9) is None


class TestPublishCoverageReport:
    """Tests for publish_coverage_report."""

    @staticmethod
    def _item(path: str) -> dict[str, object]:
        return {"path": path, "itemType": "file", "fileLength": 1}

    def test_uploads_every_file_then_links_the_folder(self, api_call: ApiCall) -> None:
        """Each file goes into the report folder, then one artifact is posted."""
        artifact = {
            "id": 1,
            "name": "Code Coverage Report_9",
            "resource": {"type": "Container", "data": "#/5/x", "url": "u"},
        }
        responses = [
            _make_mock_response(self._item("a")),
            _make_mock_response(self._item("b")),
            _make_mock_response(artifact),
        ]
        with patch.object(
            requests.Session, "request", side_effect=responses
        ) as mock_req:
            result = publish_coverage_report(
                api_call, api_call, 9, 5, {"index.html": b"<a>", "sub/p.html": b"<b>"}
            )
        calls = mock_req.call_args_list
        assert [c.args[0] for c in calls] == ["PUT", "PUT", "POST"]
        assert (
            calls[0].kwargs["params"]["itemPath"] == "Code Coverage Report_9/index.html"
        )
        assert (
            calls[1].kwargs["params"]["itemPath"] == "Code Coverage Report_9/sub/p.html"
        )
        body = calls[2].kwargs["json"]
        assert body["name"] == "Code Coverage Report_9"
        assert body["resource"]["data"] == "#/5/Code Coverage Report_9"
        assert body["resource"]["properties"]["artifactsize"] == "6"
        assert result.name == "Code Coverage Report_9"

    @staticmethod
    def test_a_report_without_index_is_refused(api_call: ApiCall) -> None:
        """The tab renders index.html, so a folder without one is an error."""
        with pytest.raises(ValueError, match=r"index\.html"):
            publish_coverage_report(api_call, api_call, 9, 5, {"other.html": b"x"})


class TestContainerBytes:
    """Tests for get_container_item_bytes."""

    @staticmethod
    def test_bytes_come_back_unchanged(api_call: ApiCall) -> None:
        """Binary content is not decoded."""
        container = get_container_api_call(api_call, 77)
        response = _make_mock_response()
        response.content = b"\x89PNG\x00\xff"
        with patch.object(requests.Session, "request", return_value=response):
            assert get_container_item_bytes(container, "f/a.png") == b"\x89PNG\x00\xff"

    @staticmethod
    def test_gzip_is_decompressed(api_call: ApiCall) -> None:
        """A body that starts with the gzip magic is decompressed."""
        container = get_container_api_call(api_call, 77)
        response = _make_mock_response()
        response.content = gzip.compress(b"plain")
        with patch.object(requests.Session, "request", return_value=response):
            assert get_container_item_bytes(container, "f/a.gz") == b"plain"

    @staticmethod
    def test_the_path_is_not_double_encoded(api_call: ApiCall) -> None:
        """A path with a space reaches requests unquoted (it encodes once)."""
        container = get_container_api_call(api_call, 77)
        response = _make_mock_response()
        response.content = b"x"
        with patch.object(
            requests.Session, "request", return_value=response
        ) as mock_req:
            get_container_item_bytes(container, "Code Coverage Report_1/index.html")
        sent = mock_req.call_args.kwargs["params"]["itemPath"]
        assert sent == "Code Coverage Report_1/index.html"


class TestBuildAttachments:
    """Tests for iter_build_attachments."""

    @staticmethod
    def test_summaries_are_listed_with_their_link(api_call: ApiCall) -> None:
        """Name and content link come back; the type is part of the path."""
        response = _make_mock_response(
            {
                "value": [
                    {"name": "summary", "_links": {"self": {"href": "https://x/y"}}},
                    {"name": "bare"},
                    {"name": "nolink", "_links": {}},
                ]
            }
        )
        with patch.object(
            requests.Session, "request", return_value=response
        ) as mock_req:
            items = list(iter_build_attachments(api_call, 9, SUMMARY_ATTACHMENT_TYPE))
        url = mock_req.call_args.kwargs["url"]
        assert url.endswith(f"/build/builds/9/attachments/{SUMMARY_ATTACHMENT_TYPE}")
        assert [i.name for i in items] == ["summary", "bare", "nolink"]
        assert items[0].href == "https://x/y"
        assert items[1].href is None
        assert items[2].href is None


class TestSummaryType:
    """The summary type is the one ``##vso[task.uploadsummary]`` writes."""

    def test_it_is_the_agent_spelling(self) -> None:
        """Capital T: the server compares case-sensitively."""
        assert SUMMARY_ATTACHMENT_TYPE == "DistributedTask.Core.Summary"


REC = "5436cf36-29d7-59d9-fd47-8539a43368f9"


class TestSummaryRecordId:
    """The owning record is part of the content link."""

    HREF = (
        "https://dev.azure.com/o/p/_apis/build/builds/9/"
        f"a1a94749-b118-4f4a-b191-548780565b75/{REC}/attachments/"
        "DistributedTask.Core.Summary/same.md"
    )

    def test_the_record_is_read_from_the_link(self) -> None:
        """The segment before ``attachments`` is the record id."""
        info = BuildAttachmentInfo.model_validate(
            {"name": "same.md", "_links": {"self": {"href": self.HREF}}}
        )
        assert info.record_id == REC

    def test_no_link_means_no_record(self) -> None:
        """An attachment without a link has no record id."""
        assert BuildAttachmentInfo.model_validate({"name": "x"}).record_id is None

    def test_a_foreign_link_shape_means_no_record(self) -> None:
        """A link of another shape is not guessed at."""
        info = BuildAttachmentInfo.model_validate(
            {"name": "x", "_links": {"self": {"href": "https://x/y"}}}
        )
        assert info.record_id is None


class TestBuildSummaries:
    """iter_build_summaries and put_record_summaries."""

    def test_the_listing_asks_for_the_agent_type(self, api_call: ApiCall) -> None:
        """Summaries are the attachments of type SUMMARY_ATTACHMENT_TYPE."""
        response = _make_mock_response({"value": [{"name": "a.md"}, {"name": "b.md"}]})
        with patch.object(
            requests.Session, "request", return_value=response
        ) as mock_req:
            names = [i.name for i in iter_build_summaries(api_call, 9)]
        assert names == ["a.md", "b.md"]
        url = mock_req.call_args.kwargs["url"]
        assert url.endswith(f"/build/builds/9/attachments/{SUMMARY_ATTACHMENT_TYPE}")

    def test_every_entry_is_put_under_its_own_name(self, api_call: ApiCall) -> None:
        """Text becomes UTF-8, bytes stay as they are, order is kept."""
        response = _make_mock_response({"name": "n", "type": SUMMARY_ATTACHMENT_TYPE})
        with patch.object(
            requests.Session, "request", return_value=response
        ) as mock_req:
            stored = put_record_summaries(
                api_call, REC, {"one.md": "äö", "two.md": b"\x00\xff"}
            )
        assert len(stored) == 2
        calls = mock_req.call_args_list
        assert (
            calls[0]
            .kwargs["url"]
            .endswith(f"/records/{REC}/attachments/{SUMMARY_ATTACHMENT_TYPE}/one.md")
        )
        assert calls[0].kwargs["data"] == "äö".encode()
        assert calls[1].kwargs["url"].endswith(f"/{SUMMARY_ATTACHMENT_TYPE}/two.md")
        assert calls[1].kwargs["data"] == b"\x00\xff"

    def test_an_empty_mapping_sends_nothing(self, api_call: ApiCall) -> None:
        """No entries, no request."""
        with patch.object(requests.Session, "request") as mock_req:
            assert put_record_summaries(api_call, REC, {}) == []
        mock_req.assert_not_called()
