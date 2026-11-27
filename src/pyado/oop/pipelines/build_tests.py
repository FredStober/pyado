"""OOP wrappers for the Tests and Code Coverage tabs of a build."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import TYPE_CHECKING

from pyado import raw
from pyado.raw import (
    ApiCall,
    CodeCoverageData,
    CodeCoverageStats,
    TestAttachmentInfo,
    TestAttachmentType,
    TestResultCreate,
    TestResultInfo,
    TestResultUpdate,
    TestRunInfo,
    TestRunState,
    TestRunUpdate,
    make_attachment_request,
)

if TYPE_CHECKING:
    from pyado.oop.pipelines.build import Build
    from pyado.oop.project import Project

__all__ = ["CodeCoverage", "TestResult", "TestRun"]


class TestRun:
    """One test run of a build (a row group of the build's **Tests** tab).

    **ADO concept:** a build can have many test runs, for example one per
    ``PublishTestResults`` task or one per matrix job.  Each run owns its
    results; result ids are only unique *within* a run.

    Instances come from :meth:`Build.iter_test_runs`.
    """

    __test__ = False

    def __init__(self, build: "Build", info: TestRunInfo) -> None:
        """Construct a TestRun wrapper.

        Args:
            build: The build the run belongs to.
            info: Run data as returned by the list call.
        """
        self._build = build
        self._info = info

    @property
    def info(self) -> TestRunInfo:
        """Run data captured at construction time (or last refresh)."""
        return self._info

    @property
    def id(self) -> int:
        """Numeric run id."""
        return self._info.id

    @property
    def name(self) -> str:
        """Run name."""
        return self._info.name

    @property
    def is_deleted(self) -> bool:
        """Whether the run was deleted (the list still shows it, state ``"255"``)."""
        return self._info.state == TestRunState.OTHER

    @property
    def build(self) -> "Build":
        """The build this run belongs to — zero-cost."""
        return self._build

    @property
    def project(self) -> "Project":
        """The project of the build — zero-cost."""
        return self._build.project

    @property
    def api_call(self) -> ApiCall:
        """Project-level API call for direct use with pyado.raw functions."""
        return self._build.project.api_call

    def refresh(self) -> None:
        """Re-read the run, including its counters, from the API."""
        self._info = raw.get_test_run(self.api_call, self.id)

    def add_results(self, results: list[TestResultCreate]) -> list["TestResult"]:
        """Add results to the run.

        Post one clean set: every row becomes a test of the run.  The duration
        of a result is computed by the server from its two dates.

        Args:
            results: The result requests.

        Returns:
            The created results, read back so ``outcome`` and the other fields
            are filled.
        """
        refs = raw.post_test_results(self.api_call, self.id, results)
        return [
            TestResult(self, raw.get_test_result(self.api_call, self.id, ref.id))
            for ref in refs
        ]

    def complete(self) -> None:
        """Close the run (state ``Completed``)."""
        self.update(TestRunUpdate(state=TestRunState.COMPLETED))

    def update(self, update: TestRunUpdate) -> None:
        """Update the run (state, comment, completion date) and re-read it.

        Args:
            update: The partial update.
        """
        raw.patch_test_run(self.api_call, self.id, update)
        self.refresh()

    def delete(self) -> None:
        """Delete the run with its results.

        The build's run list keeps returning it, marked as deleted.
        """
        raw.delete_test_run(self.api_call, self.id)
        self._info = self._info.model_copy(update={"state": TestRunState.OTHER})

    def add_attachment(
        self,
        file_name: str,
        content: bytes,
        *,
        attachment_type: TestAttachmentType = TestAttachmentType.GENERAL,
        comment: str | None = None,
    ) -> int:
        """Attach a file to the whole run.

        Args:
            file_name: Name shown in the Attachments list.
            content: The file content.
            attachment_type: ``GeneralAttachment`` or ``ConsoleLog``.
            comment: Optional comment.

        Returns:
            The attachment id.
        """
        request = make_attachment_request(
            file_name, content, attachment_type=attachment_type, comment=comment
        )
        return raw.post_test_run_attachment(self.api_call, self.id, request)

    def iter_results(self) -> Iterator["TestResult"]:
        """Iterate over the results of this run.

        Yields:
            A :class:`TestResult` for each result.
        """
        for info in raw.iter_test_results(self.api_call, self.id):
            yield TestResult(self, info)

    def list_results(self) -> list["TestResult"]:
        """Return all results of this run as a list."""
        return list(self.iter_results())

    def iter_attachments(self) -> Iterator[TestAttachmentInfo]:
        """Iterate over the attachments of the run itself (not of its results).

        Yields:
            TestAttachmentInfo for each attachment.
        """
        yield from raw.iter_test_run_attachments(self.api_call, self.id)

    def list_attachments(self) -> list[TestAttachmentInfo]:
        """Return the run attachments as a list."""
        return list(self.iter_attachments())

    def get_attachment_bytes(self, attachment: TestAttachmentInfo) -> bytes:
        """Download a run attachment.

        Args:
            attachment: An attachment from :meth:`iter_attachments`.

        Returns:
            The file content.
        """
        return raw.get_test_attachment_bytes(self.api_call, self.id, attachment.id)


class TestResult:
    """One test result inside a :class:`TestRun`.

    The result id restarts in every run, so the result always keeps its run.
    """

    __test__ = False

    def __init__(self, run: TestRun, info: TestResultInfo) -> None:
        """Construct a TestResult wrapper.

        Args:
            run: The run the result belongs to.
            info: Result data as returned by the API.
        """
        self._run = run
        self._info = info

    @property
    def info(self) -> TestResultInfo:
        """The result data."""
        return self._info

    @property
    def id(self) -> int:
        """Result id, unique only within :attr:`run`."""
        return self._info.id

    @property
    def run(self) -> TestRun:
        """The run this result belongs to — zero-cost."""
        return self._run

    @property
    def outcome(self) -> str | None:
        """Outcome text, e.g. ``Passed`` or ``Failed``."""
        return self._info.outcome

    @property
    def name(self) -> str | None:
        """The test name shown in the Tests tab."""
        return self._info.test_case_title or self._info.automated_test_name

    def update(self, update: TestResultUpdate) -> None:
        """Change the outcome, comment or linked bugs and re-read the result.

        Args:
            update: The partial update; its ``id`` is replaced by this result's id.
        """
        request = update.model_copy(update={"id": self.id})
        raw.patch_test_results(self._run.api_call, self._run.id, [request])
        self._info = raw.get_test_result(self._run.api_call, self._run.id, self.id)

    def link_bugs(self, work_item_ids: list[int]) -> None:
        """Link work items (bugs) to the result; they show in its Work items tab.

        Args:
            work_item_ids: Ids of the bugs.
        """
        self.update(
            TestResultUpdate(
                id=self.id,
                associated_bugs=[{"id": item} for item in work_item_ids],
            )
        )

    def add_attachment(
        self,
        file_name: str,
        content: bytes,
        *,
        attachment_type: TestAttachmentType = TestAttachmentType.GENERAL,
        comment: str | None = None,
    ) -> int:
        """Attach a file to this result (Attachments sub-tab of the detail pane).

        Args:
            file_name: Name shown in the list.
            content: The file content.
            attachment_type: ``GeneralAttachment`` or ``ConsoleLog``.
            comment: Optional comment.

        Returns:
            The attachment id.
        """
        request = make_attachment_request(
            file_name, content, attachment_type=attachment_type, comment=comment
        )
        return raw.post_test_result_attachment(
            self._run.api_call, self._run.id, self.id, request
        )

    def iter_attachments(self) -> Iterator[TestAttachmentInfo]:
        """Iterate over the attachments of this result.

        Yields:
            TestAttachmentInfo for each attachment.
        """
        yield from raw.iter_test_result_attachments(
            self._run.api_call, self._run.id, self.id
        )

    def list_attachments(self) -> list[TestAttachmentInfo]:
        """Return the result attachments as a list."""
        return list(self.iter_attachments())

    def get_attachment_bytes(self, attachment: TestAttachmentInfo) -> bytes:
        """Download a result attachment.

        Args:
            attachment: An attachment from :meth:`iter_attachments`.

        Returns:
            The file content.
        """
        return raw.get_test_attachment_bytes(
            self._run.api_call, self._run.id, attachment.id, result_id=self.id
        )


class CodeCoverage:
    """The coverage of one build, as the API returns it.

    The API keeps one entry per flavor/platform pair.  pyado writes only the
    entry without a pair (both values empty; the portal prints "empty"), as the
    real publish task does.  Entries with a pair can exist on builds written by
    other tools and are read as they are, but a pair cannot be shown in Azure
    DevOps: the Code Coverage tab's selector listed only the empty pair in every
    measured build, so the pair is no use for a user of the portal.

    Instances come from :meth:`Build.iter_code_coverage`.
    """

    def __init__(
        self, build: "Build", data: CodeCoverageData, status: str | None
    ) -> None:
        """Construct a CodeCoverage wrapper.

        Args:
            build: The build the coverage belongs to.
            data: One ``coverage_data`` entry.
            status: Status of the whole summary (``completed``/``finalized``).
        """
        self._build = build
        self._data = data
        self._status = status

    @property
    def build(self) -> "Build":
        """The build this coverage belongs to — zero-cost."""
        return self._build

    @property
    def flavor(self) -> str:
        """Build flavor (configuration); empty when none was given."""
        return self._data.build_flavor

    @property
    def platform(self) -> str:
        """Build platform; empty when none was given."""
        return self._data.build_platform

    @property
    def status(self) -> str | None:
        """Summary status: ``completed`` while running, ``finalized`` after."""
        return self._status

    @property
    def stats(self) -> list[CodeCoverageStats]:
        """All figures of this entry; the server does not order them."""
        return self._data.coverage_stats

    def stat(self, label: str) -> CodeCoverageStats | None:
        """Find one figure by label.

        The match is case-insensitive and by prefix, because the service
        rewrites ``line`` to ``Lines`` when the build is finalised.

        Args:
            label: For example ``"line"`` or ``"branch"``.

        Returns:
            The figure, or ``None`` when this entry has none with that label.
        """
        wanted = label.casefold()
        for stat in self._data.coverage_stats:
            if stat.label.casefold().startswith(wanted):
                return stat
        return None

    def percent(self, label: str = "line") -> float | None:
        """Covered share of one figure in percent.

        Args:
            label: Figure label, see :meth:`stat`.

        Returns:
            ``100 * covered / total``, or ``None`` when the figure is missing
            or its total is zero.
        """
        stat = self.stat(label)
        if stat is None or stat.total == 0:
            return None
        return 100.0 * stat.covered / stat.total
