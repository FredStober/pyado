"""Timeline-record attachments, build file containers and build artifacts.

Everything here is what the build page's **Extensions** tab (task summary) and
the **Code Coverage** tab (report) read.  Behaviour was measured against a live
organisation (Azure DevOps Services); no storage account key or SAS token is
involved anywhere, a PAT or the build's ``System.AccessToken`` is enough.
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import gzip
import re
from collections.abc import Iterator, Mapping
from typing import Any

from pydantic import Field

from pyado.raw._core import AdoBaseModel, ApiCall
from pyado.raw.pipelines.build import (
    BuildArtifact,
    BuildId,
    get_build_api_call,
    iter_build_artifacts,
)

__all__ = [
    "SUMMARY_ATTACHMENT_TYPE",
    "ArtifactLinkRequest",
    "ArtifactLinkResource",
    "BuildAttachmentInfo",
    "ContainerItem",
    "RecordAttachment",
    "get_build_container_id",
    "get_container_api_call",
    "get_container_item_bytes",
    "get_container_item_text",
    "iter_build_attachments",
    "iter_build_summaries",
    "iter_container_items",
    "make_container_artifact_data",
    "make_report_artifact_request",
    "post_build_artifact",
    "publish_coverage_report",
    "put_container_file",
    "put_record_attachment",
    "put_record_summaries",
]

SUMMARY_ATTACHMENT_TYPE = "DistributedTask.Core.Summary"
"""Attachment type of ``##vso[task.uploadsummary]`` (capital ``T``).

The server compares type names case-sensitively, so ``Distributedtask.Core.Summary``
(small ``t``) is a different type: a listing of one never returns the other.
"""

_CONTAINER_VERSION = "6.0-preview.4"
_GZIP_MAGIC = b"\x1f\x8b"
_ATTACHMENT_RECORD = re.compile(r"/([0-9a-fA-F-]{36})/attachments/")
_CONTAINER_DATA = re.compile(r"^#/(\d+)/")
_REPORT_PREFIX = "Code Coverage Report_"


class RecordAttachment(AdoBaseModel, extra="ignore"):
    """An attachment as returned after it was stored on a timeline record."""

    name: str
    type: str | None = None
    record_id: str | None = None


class ContainerItem(AdoBaseModel, extra="ignore"):
    """A file or folder in a build file container."""

    container_id: int | None = None
    path: str
    item_type: str
    file_length: int | None = None


class _AttachmentLinks(AdoBaseModel, extra="ignore"):
    href: str


class _AttachmentLinkSet(AdoBaseModel, extra="ignore"):
    self: _AttachmentLinks | None = None


class BuildAttachmentInfo(AdoBaseModel, extra="ignore"):
    """A timeline attachment of a build (for example a task summary).

    ``href`` is the address of the content; read it with
    ``ApiCall.get_raw`` or the build's attachment route.
    """

    name: str
    links: _AttachmentLinkSet | None = Field(default=None, alias="_links")

    @property
    def href(self) -> str | None:
        """The content address, or ``None`` when the server sent no link.

        Returns:
            The ``_links.self.href`` value.
        """
        return self.links.self.href if self.links and self.links.self else None

    @property
    def record_id(self) -> str | None:
        """The id of the timeline record that owns the attachment.

        It is the path segment before ``attachments`` in :attr:`href`
        (``.../builds/{build}/{timeline}/{record}/attachments/{type}/{name}``).
        Two summaries can share a name when they sit on different records.

        Returns:
            The record id, or ``None`` when the link has another shape.
        """
        match = _ATTACHMENT_RECORD.search(self.href or "")
        return match.group(1) if match else None


class _ContainerSummary(AdoBaseModel, extra="ignore"):
    """One entry of the organisation's container list."""

    id: int


class _ContainerSummaries(AdoBaseModel):
    value: list[_ContainerSummary]


class _BuildAttachmentInfos(AdoBaseModel):
    value: list[BuildAttachmentInfo]


class _ContainerItemResults(AdoBaseModel):
    value: list[ContainerItem]


class ArtifactLinkResource(AdoBaseModel):
    """The ``resource`` part of a build artifact that points into a container."""

    type: str = "Container"
    data: str
    properties: dict[str, str] = Field(default_factory=dict)


class ArtifactLinkRequest(AdoBaseModel):
    """Request body that associates a container path with a build as an artifact."""

    name: str
    resource: ArtifactLinkResource


def put_record_attachment(
    timeline_api_call: ApiCall,
    record_id: str,
    attachment_type: str,
    name: str,
    content: bytes,
) -> RecordAttachment:
    """Attach a file to a timeline record (task summary, custom attachment).

    With ``attachment_type`` = :data:`SUMMARY_ATTACHMENT_TYPE` the markdown in
    ``content`` appears as a card (titled by ``name`` without its extension) in
    the build page's **Extensions** tab.  It is *not* shown on the Summary tab.
    The renderer is not the wiki's: mermaid and math do not render and scripts
    are removed; see :func:`put_record_summaries` and ``docs/usage.md``, section
    "What a summary can contain", for the full list.

    Behaviour measured against a live organisation:

    * Works with a PAT, on a **Task** and on a **Job** record, and on a build
      that has already **finished**.
    * ``content`` is sent as ``application/octet-stream``.
    * The agent's ``##vso[task.uploadsummary]`` and ``task.addattachment``
      commands use the same endpoint with the current step's record.

    Args:
        timeline_api_call: Timeline-level call (from ``get_timeline_api_call``).
        record_id: Id of the timeline record (Task or Job) that owns the file.
        attachment_type: Attachment type, e.g. :data:`SUMMARY_ATTACHMENT_TYPE`.
        name: File name; also the card title for summaries.
        content: File content (markdown for a summary).

    Returns:
        The stored attachment.

    Reference:
        PUT .../distributedtask/hubs/{hub}/plans/{plan}/timelines/{tl}/records/
        {record}/attachments/{type}/{name}
    """
    response = timeline_api_call.put(
        "records",
        record_id,
        "attachments",
        attachment_type,
        name,
        version="7.1-preview.1",
        data=content,
    )
    return RecordAttachment.model_validate(response)


def get_container_api_call(
    organization_api_call: ApiCall, container_id: int
) -> ApiCall:
    """Get the call for one build file container.

    Containers live at **organisation** level (``/_apis/resources/Containers``);
    the same path below a project answers HTTP 404 "controller ... was not
    found".

    Args:
        organization_api_call: Call for ``https://dev.azure.com/{org}``.
        container_id: The build's container id (``BUILD_CONTAINERID`` in a job,
            or the ``#/<id>/`` part of an artifact's ``data``).

    Returns:
        An ApiCall pointing at the container resource.
    """
    return organization_api_call.build_call(
        "_apis", "resources", "Containers", container_id
    )


def put_container_file(
    container_api_call: ApiCall,
    item_path: str,
    content: bytes,
) -> ContainerItem:
    """Upload one file into a build file container.

    Behaviour measured against a live organisation: a PAT answers HTTP 201 and
    the ``Content-Range: bytes 0-(n-1)/n`` header is required.  The container
    id is the build's own; do not guess it.

    Args:
        container_api_call: Container call (from :func:`get_container_api_call`).
        item_path: Path inside the container, e.g.
            ``"Code Coverage Report_123/index.html"``.
        content: File content (non-empty).

    Returns:
        The created item.

    Raises:
        ValueError: If ``content`` is empty (a range header cannot express it).

    Reference:
        PUT https://dev.azure.com/{org}/_apis/resources/Containers/{id}?itemPath=
    """
    if not content:
        msg = "an empty file cannot be uploaded with a Content-Range header"
        raise ValueError(msg)
    response: Any = container_api_call.put(
        parameters={"itemPath": item_path},
        version=_CONTAINER_VERSION,
        data=content,
        extra_headers={"Content-Range": f"bytes 0-{len(content) - 1}/{len(content)}"},
    )
    return ContainerItem.model_validate(response)


def iter_container_items(
    container_api_call: ApiCall, item_path: str = ""
) -> Iterator[ContainerItem]:
    """List the items below ``item_path`` in a build file container.

    Yields:
        Each file or folder item.
    """
    response = container_api_call.get(
        parameters={"itemPath": item_path, "isShallow": False},
        version=_CONTAINER_VERSION,
    )
    yield from _ContainerItemResults.model_validate(response).value


def get_container_item_text(container_api_call: ApiCall, item_path: str) -> str:
    """Read one file from a build file container as text.

    A file you uploaded with :func:`put_container_file` comes back unchanged
    (verified byte for byte, including multibyte text).  Files that a build
    *task* uploaded may be gzip-compressed (the leading bytes ``1f 8b``); this
    function decompresses those, so the text is readable either way.

    Args:
        container_api_call: Container call (from :func:`get_container_api_call`).
        item_path: Path of the file inside the container.

    Returns:
        The decoded (UTF-8) file content.
    """
    raw: bytes = container_api_call.get_raw(
        parameters={"itemPath": item_path, "$format": "OctetStream"},
        version=_CONTAINER_VERSION,
    )
    if raw[:2] == _GZIP_MAGIC:
        raw = gzip.decompress(raw)
    return raw.decode("utf-8")


def get_container_item_bytes(container_api_call: ApiCall, item_path: str) -> bytes:
    """Read one file from a build file container as bytes.

    Use this for anything that is not UTF-8 text (images, archives, logs with
    unknown encoding).  Like :func:`get_container_item_text` it decompresses a
    body that starts with the gzip magic.

    Args:
        container_api_call: Container call (from :func:`get_container_api_call`).
        item_path: Path of the file inside the container.

    Returns:
        The file content.
    """
    raw: bytes = container_api_call.get_raw(
        parameters={"itemPath": item_path, "$format": "OctetStream"},
        version=_CONTAINER_VERSION,
    )
    return gzip.decompress(raw) if raw[:2] == _GZIP_MAGIC else raw


def iter_build_attachments(
    project_api_call: ApiCall, build_id: BuildId, attachment_type: str
) -> Iterator[BuildAttachmentInfo]:
    """Iterate over a build's timeline attachments of one type.

    With :data:`SUMMARY_ATTACHMENT_TYPE` this lists the task and job summaries
    that fill the **Extensions** tab.  Only the name and a link come back.

    Args:
        project_api_call: Project-level call.
        build_id: The build.
        attachment_type: For example :data:`SUMMARY_ATTACHMENT_TYPE`.

    Yields:
        Each attachment of that type.
    """
    response = project_api_call.get(
        "build",
        "builds",
        build_id,
        "attachments",
        attachment_type,
        version="7.1-preview.2",
    )
    yield from _BuildAttachmentInfos.model_validate(response).value


def iter_build_summaries(
    project_api_call: ApiCall, build_id: BuildId
) -> Iterator[BuildAttachmentInfo]:
    """Iterate over every summary of a build, whoever wrote it.

    These are the cards of the **Extensions** tab: the files written by
    ``##vso[task.uploadsummary]`` and by :func:`put_record_summaries`
    (type :data:`SUMMARY_ATTACHMENT_TYPE`).  A build can hold many.  A summary
    is identified by its record and its name, so the same name can appear
    twice (on two records); use :attr:`BuildAttachmentInfo.record_id` to tell
    them apart.

    Args:
        project_api_call: Project-level call.
        build_id: The build.

    Yields:
        Each summary (name, link and owning record).
    """
    yield from iter_build_attachments(
        project_api_call, build_id, SUMMARY_ATTACHMENT_TYPE
    )


def put_record_summaries(
    timeline_api_call: ApiCall,
    record_id: str,
    summaries: Mapping[str, str | bytes],
) -> list[RecordAttachment]:
    """Attach several summaries to one timeline record.

    Each entry becomes its own card in the **Extensions** tab, titled by the
    key.  Behaviour measured against a live organisation (build 2410):

    * A summary is identified by **record + name**.  Uploading a name that the
      record already has **replaces** its content; the same name on another
      record is a second summary.
    * An empty body is accepted and listed.
    * The calls are independent: when one fails, the earlier ones stay.
    * A summary cannot be deleted (``DELETE`` answers HTTP 405); upload an empty
      or placeholder body over the same name to blank it.

    What a card may contain (the Extensions tab has its own renderer, not the
    wiki's; see ``docs/usage.md``, section "What a summary can contain"):

    * **Renders:** GitHub-style markdown (headings, lists, task lists, tables,
      code fences without highlighting, quotes, ``https`` links and images) and a
      sanitized subset of HTML (``details``/``summary``, ``table``, ``span`` and
      ``div`` with inline ``style``, ``font``, ``br``, ``b``/``i``/``u``/``s``,
      ``img`` with an ``https`` source).
    * **Does not render:** mermaid, math (``$...$``), footnotes, definition lists,
      ``:emoji:`` shortcodes and ``data:`` images (shown as text); a bare URL is
      not linked.
    * **Removed:** ``script``, ``style``, ``svg``, ``iframe``, ``form``,
      ``button`` and similar tags, every ``on*`` handler, and ``javascript:`` or
      ``data:`` links.  Nothing executes.  Inline ``style`` keeps layout
      properties (``width``, ``background``, ``border``, ``color``, ...) but
      drops ``position``, ``display`` and ``opacity``, so a card cannot cover the
      page.  ``[[_TOC_]]`` renders a table of contents.
    * **External addresses are loaded** by the viewer's browser: ``https`` and
      ``http`` images and ``background:url(...)`` are kept.

    Args:
        timeline_api_call: Timeline-level call (from ``get_timeline_api_call``).
        record_id: Id of the timeline record (Task or Job) that owns the files.
        summaries: File name to markdown or HTML (text is sent as UTF-8).  The
            card title is the name without its extension.

    Returns:
        The stored attachments, in the order of ``summaries``.
    """
    return [
        put_record_attachment(
            timeline_api_call,
            record_id,
            SUMMARY_ATTACHMENT_TYPE,
            name,
            content.encode("utf-8") if isinstance(content, str) else content,
        )
        for name, content in summaries.items()
    ]


def get_build_container_id(project_api_call: ApiCall, build_id: BuildId) -> int | None:
    """Find the id of a build's file container.

    Every build owns a container named ``BUILD_<id>`` even if it published
    nothing.  The id is read, in this order, from

    1. the ``data`` of a container artifact (``#/<container id>/<folder>``;
       free: the artifacts are listed anyway), then
    2. the organisation's container list, filtered by the build's artifact
       URI (``vstfs:///Build/Build/<id>``).

    The ``BUILD_CONTAINERID`` variable inside a job holds the same number.

    Args:
        project_api_call: Project-level call (``{org}/{project}/_apis``).
        build_id: The build.

    Returns:
        The container id, or ``None`` if the build has none (for example a
        deleted build).
    """
    build_call = get_build_api_call(project_api_call, build_id)
    for artifact in iter_build_artifacts(build_call):
        match = _CONTAINER_DATA.match(artifact.resource.data or "")
        if match:
            return int(match.group(1))
    org_call = _organization_call(project_api_call)
    response = org_call.get(
        "_apis",
        "resources",
        "Containers",
        parameters={"artifactUris": f"vstfs:///Build/Build/{build_id}"},
        version=_CONTAINER_VERSION,
    )
    containers = _ContainerSummaries.model_validate(response).value
    return containers[0].id if containers else None


def _organization_call(project_api_call: ApiCall) -> ApiCall:
    """Return the organisation-level call that belongs to a project call.

    Returns:
        A call for ``https://dev.azure.com/{org}``.
    """
    parts = project_api_call.url.unicode_string().rstrip("/").split("/")
    # https:, "", host, org, project, _apis ...
    organization_url = "/".join(parts[:4])
    return ApiCall(
        session=project_api_call.session,
        timeout=project_api_call.timeout,
        url=organization_url,
    )


def make_container_artifact_data(container_id: int, folder: str) -> str:
    """Build the ``resource.data`` string of a container artifact.

    Returns:
        ``"#/<container_id>/<folder>"``.
    """
    return f"#/{container_id}/{folder}"


def make_report_artifact_request(
    container_id: int,
    folder: str,
    *,
    size: int,
    browsable: bool = True,
) -> ArtifactLinkRequest:
    """Build the artifact request that makes ``folder`` the build's report.

    A folder named ``Code Coverage Report_<buildId>`` with an ``index.html`` is
    what the build page's **Code Coverage** tab renders.

    Returns:
        The request for :func:`post_build_artifact`.
    """
    return ArtifactLinkRequest(
        name=folder,
        resource=ArtifactLinkResource(
            data=make_container_artifact_data(container_id, folder),
            properties={"Browsable": str(browsable), "artifactsize": str(size)},
        ),
    )


def post_build_artifact(
    project_api_call: ApiCall,
    build_id: BuildId,
    request: ArtifactLinkRequest,
) -> BuildArtifact:
    """Associate a container path with a build as an artifact.

    Works on a finished build.  The artifact then appears in the build's
    *Published artifacts* page, and a folder named ``Code Coverage Report_*``
    with an ``index.html`` also fills the Code Coverage tab.

    Returns:
        The created artifact.

    Reference:
        POST .../build/builds/{id}/artifacts
    """
    response = project_api_call.post(
        "build",
        "builds",
        build_id,
        "artifacts",
        version="7.1",
        json=request.model_dump(by_alias=True, mode="json"),
    )
    return BuildArtifact.model_validate(response)


def publish_coverage_report(
    organization_api_call: ApiCall,
    project_api_call: ApiCall,
    build_id: BuildId,
    container_id: int,
    files: Mapping[str, bytes],
) -> BuildArtifact:
    """Upload a coverage report folder and link it, so the Code Coverage tab shows it.

    The folder is named ``Code Coverage Report_<build id>`` and must contain an
    ``index.html``.  Files may be in sub-folders (``"sub/page.html"``).  This is
    the upload and the artifact link in one call; it is the only way that fills
    the tab from outside.  The coverage *figures* (the Details and Files sub-tabs) are
    written by :func:`pyado.raw.publish_code_coverage`; read them with
    :func:`pyado.raw.get_code_coverage`.

    Args:
        organization_api_call: Organisation call (``{org}``), for the container.
        project_api_call: Project call (``{org}/{project}/_apis``), for the artifact.
        build_id: The build the report belongs to.
        container_id: The build's container (:func:`get_build_container_id`).
        files: Path inside the folder to content; every file must be non-empty.

    Returns:
        The created artifact.

    Raises:
        ValueError: If there is no ``index.html``.
    """
    if "index.html" not in files:
        msg = "a coverage report needs an index.html"
        raise ValueError(msg)
    folder = f"{_REPORT_PREFIX}{build_id}"
    container = get_container_api_call(organization_api_call, container_id)
    for path, content in files.items():
        put_container_file(container, f"{folder}/{path}", content)
    size = sum(len(content) for content in files.values())
    return post_build_artifact(
        project_api_call,
        build_id,
        make_report_artifact_request(container_id, folder, size=size),
    )
