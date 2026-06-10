"""ProjectRepos — the Repos section object for a project."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, cast

from pyado import raw
from pyado.oop.repos.branch import Branch
from pyado.oop.repos.pull_request import PullRequest
from pyado.oop.repos.repository import Repository
from pyado.oop.repos.tag import Tag
from pyado.raw import (
    PullRequestId,
    PullRequestSearchCriteria,
    PullRequestStatus,
    RepositoryId,
)

if TYPE_CHECKING:
    from pyado.oop.project import Project


class ProjectRepos:
    """The Repos section of a project.

    Accessed via ``project.repos``.  Exposes all repository and pull-request
    operations that belong to the ADO Repos section.

    Attributes:
        _project: The owning Project.
    """

    def __init__(self, project: "Project") -> None:
        """Construct a ProjectRepos section.

        Args:
            project: The Project this section belongs to.
        """
        self._project = project

    # ------------------------------------------------------------------
    # Repositories
    # ------------------------------------------------------------------

    def iter_repositories(self) -> Iterator[Repository]:
        """Iterate over all repositories in the project.

        Each yielded Repository is cached in the service so that repeated
        access returns the same instance.

        Yields:
            Repository for each repository in the project.
        """
        service = self._project._service  # noqa: SLF001
        for info in raw.iter_repository_details(self._project.api_call):
            repo_api_call = raw.get_repository_api_call(self._project.api_call, info.id)
            cache_key = str(repo_api_call.url)
            repo: Repository = service.oop_api.get_or_cache(
                cache_key,
                cast(
                    "Callable[[], Repository]",
                    lambda i=info, a=repo_api_call: Repository(
                        self._project, a, i, service
                    ),
                ),
            )
            yield repo

    def get_repository(self, name: str) -> Repository:
        """Return a wrapper for a repository by name.

        Args:
            name: Repository name (case-sensitive).

        Returns:
            Repository wrapping the matched repository.

        Raises:
            KeyError: If no repository with the given name is found.
        """
        for repo in self.iter_repositories():
            if repo.name == name:
                return repo
        raise KeyError(name)

    def get_repository_by_id(self, repo_id: RepositoryId) -> Repository:
        """Return a wrapper for a repository by UUID.

        Args:
            repo_id: Repository UUID.

        Returns:
            Repository wrapping the matched repository.

        Raises:
            KeyError: If no repository with the given ID is found.
        """
        for repo in self.iter_repositories():
            if repo.id == repo_id:
                return repo
        raise KeyError(repo_id)

    def list_repositories(self) -> list[Repository]:
        """Return all repositories in the project as a list."""
        return list(self.iter_repositories())

    # ------------------------------------------------------------------
    # Pull requests (project-wide)
    # ------------------------------------------------------------------

    def iter_pull_requests(
        self,
        status: PullRequestStatus | None = None,
        *,
        criteria: PullRequestSearchCriteria | None = None,
        expand: str | None = None,
    ) -> Iterator[PullRequest]:
        """Iterate over pull requests across all repositories in the project.

        Args:
            status: Filter by PR lifecycle status.  When ``None`` (default),
                all PRs are returned regardless of status.  Ignored when
                *criteria* is provided.
            criteria: Full search criteria; overrides *status* when provided.
            expand: Optional ``$expand`` value (e.g. ``"labels"``,
                ``"reviewers"``).

        Yields:
            PullRequest for each matching PR, in API-returned order.
        """
        service = self._project._service  # noqa: SLF001
        effective_criteria = criteria or PullRequestSearchCriteria(status=status)
        for item in raw.iter_pull_requests(
            self._project.api_call,
            search_criteria=effective_criteria,
            expand=expand,
        ):
            repo_id = item.repository.id
            repo_api_call = raw.get_repository_api_call(self._project.api_call, repo_id)
            cache_key = str(repo_api_call.url)

            def _make_repo(r: raw.ApiCall = repo_api_call) -> Repository:
                return Repository(self._project, r, raw.get_repository_info(r), service)

            repo: Repository = service.oop_api.get_or_cache(cache_key, _make_repo)
            pr_api_call = raw.get_pull_request_api_call(
                self._project.api_call, repo_id, item.pr_id
            )
            yield PullRequest(repo, pr_api_call, item, expand)

    def iter_active_prs(self, *, expand: str | None = None) -> Iterator[PullRequest]:
        """Iterate over all active pull requests in the project.

        Convenience shortcut for
        ``iter_pull_requests(status=PullRequestStatus.ACTIVE)``.

        Args:
            expand: Optional ``$expand`` value (e.g. ``"labels"``,
                ``"reviewers"``).

        Yields:
            PullRequest for each active PR, in API-returned order.
        """
        yield from self.iter_pull_requests(
            status=PullRequestStatus.ACTIVE, expand=expand
        )

    def get_pull_request(
        self,
        pr_id: PullRequestId,
        repo_id: RepositoryId | None = None,
    ) -> PullRequest:
        """Return a PR wrapper by ID.

        When *repo_id* is provided, the PR is fetched directly from the
        repository-scoped endpoint (one API call).  When omitted, a
        project-wide search is performed instead.

        Args:
            pr_id: Numeric pull request ID.
            repo_id: Optional repository UUID.  When supplied, the direct
                lookup path is used; when omitted the project-wide
                ``searchCriteria.pullRequestId`` search is used.

        Returns:
            PullRequest wrapping the matched PR.

        Raises:
            KeyError: If no PR with *pr_id* exists in this project.
        """
        service = self._project._service  # noqa: SLF001
        if repo_id is not None:
            repo_api_call = raw.get_repository_api_call(self._project.api_call, repo_id)
            cache_key = str(repo_api_call.url)
            repo: Repository = service.oop_api.get_or_cache(
                cache_key,
                lambda: Repository(
                    self._project,
                    repo_api_call,
                    raw.get_repository_info(repo_api_call),
                    service,
                ),
            )
            pr_api_call = raw.get_pull_request_api_call(
                self._project.api_call, repo_id, pr_id
            )
            info = raw.get_pull_request_details(pr_api_call)
            return PullRequest(repo, pr_api_call, info)
        items = list(
            raw.iter_pull_requests(
                self._project.api_call,
                search_criteria=PullRequestSearchCriteria(pull_request_id=pr_id),
            )
        )
        if not items:
            raise KeyError(pr_id)
        item = items[0]
        found_repo_id = item.repository.id
        found_repo_api_call = raw.get_repository_api_call(
            self._project.api_call, found_repo_id
        )
        cache_key = str(found_repo_api_call.url)
        found_repo: Repository = service.oop_api.get_or_cache(
            cache_key,
            lambda: Repository(
                self._project,
                found_repo_api_call,
                raw.get_repository_info(found_repo_api_call),
                service,
            ),
        )
        pr_api_call = raw.get_pull_request_api_call(
            self._project.api_call, found_repo_id, pr_id
        )
        return PullRequest(found_repo, pr_api_call, item)

    def list_pull_requests(
        self,
        status: PullRequestStatus | None = None,
        *,
        criteria: PullRequestSearchCriteria | None = None,
        expand: str | None = None,
    ) -> list[PullRequest]:
        """Return all pull requests in the project as a list."""
        return list(
            self.iter_pull_requests(status=status, criteria=criteria, expand=expand)
        )

    def list_active_prs(self, *, expand: str | None = None) -> list[PullRequest]:
        """Return all active pull requests in the project as a list."""
        return list(self.iter_active_prs(expand=expand))

    # ------------------------------------------------------------------
    # Branches (project-wide convenience)
    # ------------------------------------------------------------------

    def iter_branches(self, repo_name: str) -> Iterator[Branch]:
        """Iterate over branches in a named repository.

        Args:
            repo_name: Repository name (case-sensitive).

        Yields:
            :class:`Branch` for each branch.
        """
        repo = self.get_repository(repo_name)
        for ref in repo.iter_branches():
            yield Branch(repo, ref)

    def list_branches(self, repo_name: str) -> list[Branch]:
        """Return all branches in a named repository as a list."""
        return list(self.iter_branches(repo_name))

    # ------------------------------------------------------------------
    # Tags (project-wide convenience)
    # ------------------------------------------------------------------

    def iter_git_tags(self, repo_name: str) -> Iterator[Tag]:
        """Iterate over git tags in a named repository.

        Args:
            repo_name: Repository name (case-sensitive).

        Yields:
            :class:`Tag` for each tag.
        """
        yield from self.get_repository(repo_name).iter_git_tags()

    def list_git_tags(self, repo_name: str) -> list[Tag]:
        """Return all git tags in a named repository as a list."""
        return list(self.iter_git_tags(repo_name))
