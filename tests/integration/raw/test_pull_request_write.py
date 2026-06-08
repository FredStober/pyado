"""Integration tests for pull request write endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import random
import time

from pyado import raw
from pyado.raw import (
    GitChangeType,
    PullRequestMergeStrategy,
    PullRequestStatus,
    PullRequestStatusState,
    PullRequestThreadCommentType,
    PullRequestThreadContext,
    PullRequestThreadStatus,
    PullRequestVote,
    VersionDescriptorType,
    WorkItemArtifactUrlPrefix,
    WorkItemExpand,
    WorkItemFieldName,
    WorkItemRelationType,
    WorkItemTypeName,
)
from tests.integration.raw._support import _take, console


def _run_pr1_scenario(
    project_api_call: raw.ApiCall,
    repo_api_call: raw.ApiCall,
    branch_name: str,
    default_branch: str,
    run_ts: str,
    reviewer_id: str | None,
    file_path: str,
) -> None:
    """PR-1: create, label/thread/reviewer exercise, metadata update, abandon."""
    # Pre-cleanup: abandon any active PR from a previous smoke run on this branch
    for stale_pr in raw.iter_pull_requests(
        project_api_call,
        search_criteria=raw.PullRequestSearchCriteria(
            status=PullRequestStatus.ACTIVE, source_ref_name=branch_name
        ),
    ):
        stale_api_call = raw.get_pull_request_api_call(
            project_api_call, stale_pr.repository.id, stale_pr.pr_id
        )
        raw.patch_pull_request(
            stale_api_call,
            raw.PullRequestUpdateRequest(status=PullRequestStatus.ABANDONED),
        )

    pr = raw.post_pull_request(
        repo_api_call,
        raw.PullRequestCreateRequest(
            title=f"[pyado-smoke-test][PR1][{run_ts}] Temporary PR",
            source_ref_name=branch_name,
            target_ref_name=default_branch,
            completion_options=raw.PullRequestCompletionOptions(),
            description="Created by pyado smoke_test.py — safe to abandon",
        ),
    )
    console.print(f"  PR (raw): #{pr.pr_id}  {pr.title!r}")

    pr_api_call = raw.get_pull_request_api_call(
        project_api_call, pr.repository.id, pr.pr_id
    )

    # ---- Labels ----
    raw.post_pull_request_label(pr_api_call, "smoke-a")
    raw.post_pull_request_label(pr_api_call, "smoke-b")
    raw.post_pull_request_label(pr_api_call, "smoke-c")
    raw.get_pull_request_labels_details(pr_api_call)
    raw.delete_pull_request_label(pr_api_call, "smoke-a")
    raw.get_pull_request_labels_details(pr_api_call)
    raw.delete_pull_request_label(pr_api_call, "smoke-b")
    raw.get_pull_request_labels_details(pr_api_call)

    # ---- Thread creation ----
    thread = raw.post_pull_request_new_thread(
        pr_api_call,
        raw.PullRequestThreadRequest(
            comments=[
                raw.PullRequestThreadCommentRequest(
                    content="Smoke test comment (PR-level)",
                    comment_type=PullRequestThreadCommentType.TEXT,
                    parent_comment_id=0,
                )
            ],
            status=PullRequestThreadStatus.ACTIVE,
        ),
    )
    raw.post_pull_request_new_thread(
        pr_api_call,
        raw.PullRequestThreadRequest(
            comments=[
                raw.PullRequestThreadCommentRequest(
                    content="Smoke test comment (file-anchored)",
                    comment_type=PullRequestThreadCommentType.TEXT,
                    parent_comment_id=0,
                )
            ],
            status=PullRequestThreadStatus.ACTIVE,
            thread_context=PullRequestThreadContext.model_validate(
                {
                    "filePath": file_path,
                    "rightFileStart": {"line": 1, "offset": 1},
                    "rightFileEnd": {"line": 1, "offset": 1},
                }
            ),
        ),
    )

    if thread and thread.id:
        raw.post_pull_request_thread_comment(
            pr_api_call,
            thread.id,
            raw.PullRequestThreadCommentRequest(
                content="Smoke test reply (raw)",
                comment_type=PullRequestThreadCommentType.TEXT,
                parent_comment_id=1,
            ),
        )

    list(raw.iter_pull_request_threads(pr_api_call))
    list(raw.iter_pull_request_iterations(pr_api_call))
    _take(raw.iter_pull_request_commits(pr_api_call), 10)

    # ---- PR status ----
    raw.post_pull_request_status(
        pr_api_call,
        raw.PullRequestStatusRequest(
            context=raw.PullRequestStatusContext(name="smoke-test", genre="pyado"),
            description="Smoke test status",
            iteration_id=1,
            state=PullRequestStatusState.SUCCEEDED,
        ),
    )

    # ---- Reviewer management ----
    if reviewer_id:
        raw.put_pull_request_reviewer(
            pr_api_call, reviewer_id, raw.PullRequestReviewerRequest(is_required=False)
        )
        raw.get_pull_request_reviewers(pr_api_call)
        raw.put_pull_request_reviewer_vote(
            pr_api_call,
            reviewer_id,
            raw.PullRequestReviewerVoteRequest(vote=PullRequestVote.APPROVED),
        )
        raw.put_pull_request_reviewer_vote(
            pr_api_call,
            reviewer_id,
            raw.PullRequestReviewerVoteRequest(vote=PullRequestVote.NO_VOTE),
        )
        raw.delete_pull_request_reviewer(pr_api_call, reviewer_id)

    # ---- PR metadata updates ----
    raw.patch_pull_request(
        pr_api_call,
        raw.PullRequestUpdateRequest(
            title=f"[pyado-smoke-test][PR1][{run_ts}] Temporary PR (updated)"
        ),
    )
    raw.patch_pull_request(pr_api_call, raw.PullRequestUpdateRequest(is_draft=True))
    raw.patch_pull_request(pr_api_call, raw.PullRequestUpdateRequest(is_draft=False))

    # ---- Patch PR thread ----
    console.print("\n=== PR THREAD PATCH (write) ===")
    if thread and thread.id is not None:
        current_status = thread.status or PullRequestThreadStatus.ACTIVE
        new_thread_status: raw.PullRequestThreadStatus = (
            PullRequestThreadStatus.FIXED
            if current_status != PullRequestThreadStatus.FIXED
            else PullRequestThreadStatus.ACTIVE
        )
        raw.patch_pull_request_thread(pr_api_call, thread.id, new_thread_status)

    # ---- Abandon PR ----
    raw.patch_pull_request(
        pr_api_call, raw.PullRequestUpdateRequest(status=PullRequestStatus.ABANDONED)
    )


def _pr2_link_wi(
    project_api_call: raw.ApiCall,
    repo: raw.RepositoryInfo,
    pr2: raw.PullRequestResponse,
    pr2_api_call: raw.ApiCall,
    wi_for_pr2: raw.WorkItemInfo,
) -> None:
    """Verify PR2↔WI link in both directions and add WI→PR ArtifactLink."""
    wi_for_pr2_api = raw.get_work_item_api_call(project_api_call, wi_for_pr2.id)

    def _verify_wi_in_pr2() -> list[int]:
        refs = list(raw.iter_pull_request_work_item_ids(pr2_api_call))
        ref_ids = [ref.id for ref in refs]
        if wi_for_pr2.id not in ref_ids:
            msg = (
                f"WI #{wi_for_pr2.id} not found in"
                f" PR #{pr2.pr_id} workItemRefs (API link);"
                f" found: {ref_ids}"
            )
            raise AssertionError(msg)
        console.print(f"  PR #{pr2.pr_id} → WI #{wi_for_pr2.id} (API link) confirmed")
        return ref_ids

    _verify_wi_in_pr2()
    vstfs_pr2 = (
        f"{WorkItemArtifactUrlPrefix.PULL_REQUEST}"
        f"/{repo.project.id}/{repo.id}/{pr2.pr_id}"
    )
    raw.patch_work_item(
        wi_for_pr2_api,
        [
            raw.JsonPatchAdd(
                path="/relations/-",
                value={
                    "rel": WorkItemRelationType.ARTIFACT_LINK,
                    "url": vstfs_pr2,
                    "attributes": {"name": "Pull Request"},
                },
            )
        ],
    )

    def _verify_wi_pr2_link() -> list[raw.WorkItemRelation]:
        item = raw.get_work_item(wi_for_pr2_api, expand=WorkItemExpand.RELATIONS)
        pr_id_str = str(pr2.pr_id)
        matching = [
            r
            for r in item.relations
            if r.rel == WorkItemRelationType.ARTIFACT_LINK and pr_id_str in str(r.url)
        ]
        if not matching:
            artifact_urls = [
                str(r.url)
                for r in item.relations
                if r.rel == WorkItemRelationType.ARTIFACT_LINK
            ]
            msg = (
                f"no ArtifactLink on WI #{item.id}"
                f" references PR #{pr2.pr_id};"
                f" urls: {artifact_urls}"
            )
            raise AssertionError(msg)
        console.print(f"  WI #{item.id} → PR #{pr2.pr_id} (ArtifactLink) confirmed")
        return matching

    _verify_wi_pr2_link()


def _pr2_merge_and_verify(
    pr2_api_call: raw.ApiCall,
    pr2: raw.PullRequestResponse,
    current_sha: raw.CommitId,
    default_branch: str,
) -> None:
    """Squash-merge PR2 and verify it completed."""
    pr2_merge_sha = (
        pr2.last_merge_source_commit.commit_id
        if pr2.last_merge_source_commit
        else current_sha
    )
    patch_pr2 = raw.patch_pull_request(
        pr2_api_call,
        raw.PullRequestUpdateRequest(
            status=PullRequestStatus.COMPLETED,
            last_merge_source_commit=raw.CommitIdRef(commit_id=pr2_merge_sha),
            completion_options=raw.PullRequestCompletionOptions(
                squash_merge=True,
                delete_source_branch=False,
                merge_strategy=PullRequestMergeStrategy.SQUASH,
            ),
        ),
    )
    if patch_pr2 and patch_pr2.status == PullRequestStatus.COMPLETED:
        pr2_details = patch_pr2
    else:
        deadline_pr2 = time.monotonic() + 120.0
        pr2_details = patch_pr2
        while time.monotonic() < deadline_pr2:
            pr2_details = raw.get_pull_request_details(pr2_api_call)
            if pr2_details.status == PullRequestStatus.COMPLETED:
                break
            time.sleep(5)

    def _verify_pr2_merged(
        _details: raw.PullRequestResponse | None = pr2_details,
    ) -> raw.PullRequestResponse:
        if _details is None:
            msg = f"PR #{pr2.pr_id} could not fetch details"
            raise AssertionError(msg)
        if _details.status == PullRequestStatus.COMPLETED:
            console.print(f"  PR #{pr2.pr_id} squash-merged into {default_branch!r}")
            return _details
        if _details.last_merge_commit is not None:
            console.print(
                f"  PR #{pr2.pr_id} squash-merged "
                f"(lastMergeCommit="
                f"{_details.last_merge_commit.commit_id[:8]},"
                f" status={_details.status!r})"
            )
            return _details
        msg = (
            f"PR #{pr2.pr_id} expected completed or merge commit after 2 min;"
            f" status={_details.status!r},"
            f" mergeStatus={_details.merge_status!r}"
        )
        raise AssertionError(msg)

    _verify_pr2_merged()


def _run_pr2_scenario(
    project_api_call: raw.ApiCall,
    repo_api_call: raw.ApiCall,
    repo: raw.RepositoryInfo,
    branch_name: str,
    default_branch: str,
    current_sha: raw.CommitId,
    run_ts: str,
) -> None:
    """PR-2: create with API WI link, squash-merge, verify WI↔PR in both directions."""
    short_source = branch_name.removeprefix("refs/heads/")
    short_target = default_branch.removeprefix("refs/heads/")

    wi_for_pr2 = raw.post_work_item(
        project_api_call,
        WorkItemTypeName.TASK,
        [
            raw.JsonPatchAdd(
                path=f"/fields/{WorkItemFieldName.TITLE}",
                value=f"[pyado-smoke-test][WI-PR2][{run_ts}] API link",
            ),
            raw.JsonPatchAdd(
                path=f"/fields/{WorkItemFieldName.DESCRIPTION}",
                value="Linked to PR2 via workItemRefs API",
            ),
        ],
    )
    if wi_for_pr2:
        console.print(f"  created WI #{wi_for_pr2.id} for PR2 API link")

    wi_refs_for_pr2 = [raw.WorkItemRef(id=wi_for_pr2.id)] if wi_for_pr2 else None
    pr2 = raw.post_pull_request(
        repo_api_call,
        raw.PullRequestCreateRequest(
            title=f"[pyado-smoke-test][PR2][{run_ts}] Temporary PR (API WI link)",
            source_ref_name=f"refs/heads/{short_source}",
            target_ref_name=f"refs/heads/{short_target}",
            completion_options=raw.PullRequestCompletionOptions(
                squash_merge=True,
                delete_source_branch=False,
                merge_strategy=PullRequestMergeStrategy.SQUASH,
            ),
            description="Created by pyado smoke_test.py — merged with API WI link",
            work_item_refs=wi_refs_for_pr2,
        ),
    )
    console.print(f"  PR2 (raw): #{pr2.pr_id}  {pr2.title!r}")
    pr2_api_call = raw.get_pull_request_api_call(
        project_api_call, pr2.repository.id, pr2.pr_id
    )

    if wi_for_pr2:
        _pr2_link_wi(project_api_call, repo, pr2, pr2_api_call, wi_for_pr2)

    _pr2_merge_and_verify(pr2_api_call, pr2, current_sha, default_branch)


def _pr3_merge_and_verify(
    pr3_api_call: raw.ApiCall,
    pr3: raw.PullRequestResponse,
    current_sha: raw.CommitId,
    default_branch: str,
) -> None:
    """Squash-merge PR3 and verify it completed."""
    pr3_merge_sha = (
        pr3.last_merge_source_commit.commit_id
        if pr3.last_merge_source_commit
        else current_sha
    )
    patch_pr3 = raw.patch_pull_request(
        pr3_api_call,
        raw.PullRequestUpdateRequest(
            status=PullRequestStatus.COMPLETED,
            last_merge_source_commit=raw.CommitIdRef(commit_id=pr3_merge_sha),
            completion_options=raw.PullRequestCompletionOptions(
                squash_merge=True,
                delete_source_branch=False,
                merge_strategy=PullRequestMergeStrategy.SQUASH,
            ),
        ),
    )
    if patch_pr3 and patch_pr3.status == PullRequestStatus.COMPLETED:
        pr3_details = patch_pr3
    else:
        deadline_pr3 = time.monotonic() + 120.0
        pr3_details = patch_pr3
        while time.monotonic() < deadline_pr3:
            pr3_details = raw.get_pull_request_details(pr3_api_call)
            if pr3_details.status == PullRequestStatus.COMPLETED:
                break
            if pr3_details.last_merge_commit is not None:
                break
            time.sleep(5)

    def _verify_pr3_merged(
        _details: raw.PullRequestResponse | None = pr3_details,
    ) -> raw.PullRequestResponse:
        if _details is None:
            msg = f"PR #{pr3.pr_id} could not fetch details"
            raise AssertionError(msg)
        if _details.status == PullRequestStatus.COMPLETED:
            console.print(f"  PR #{pr3.pr_id} squash-merged into {default_branch!r}")
            return _details
        if _details.last_merge_commit is not None:
            console.print(
                f"  PR #{pr3.pr_id} squash-merged "
                f"(lastMergeCommit="
                f"{_details.last_merge_commit.commit_id[:8]},"
                f" status={_details.status!r})"
            )
            return _details
        msg = (
            f"PR #{pr3.pr_id} expected completed or merge commit after 2 min;"
            f" status={_details.status!r},"
            f" mergeStatus={_details.merge_status!r}"
        )
        raise AssertionError(msg)

    _verify_pr3_merged()


def _pr3_check_wi_links(
    project_api_call: raw.ApiCall,
    repo: raw.RepositoryInfo,
    pr3: raw.PullRequestResponse,
    wi_for_pr3: raw.WorkItemInfo | None,
) -> None:
    """Verify WI→commit ArtifactLink (async poll) and WI→PR3 ArtifactLink."""
    if not wi_for_pr3:
        return

    wi_for_pr3_api = raw.get_work_item_api_call(project_api_call, wi_for_pr3.id)

    # ADO indexes #<id> commit links asynchronously.  Poll until the
    # WI has a git-commit ArtifactLink (up to 60 s).
    ab_deadline = time.monotonic() + 60.0
    ab_commit_links: list[raw.WorkItemRelation] = []
    while time.monotonic() < ab_deadline:
        item_poll = raw.get_work_item(wi_for_pr3_api, expand=WorkItemExpand.RELATIONS)
        ab_commit_links = [
            r
            for r in item_poll.relations
            if r.rel == WorkItemRelationType.ARTIFACT_LINK
            and WorkItemArtifactUrlPrefix.COMMIT in str(r.url)
        ]
        if ab_commit_links:
            break
        time.sleep(5)

    def _verify_wi_commit_link(
        _links: list[raw.WorkItemRelation] = ab_commit_links,
    ) -> list[raw.WorkItemRelation]:
        if not _links:
            msg = (
                f"WI #{wi_for_pr3.id} has no git-commit ArtifactLink"
                f" after 60 s — #<id> indexing may not be enabled"
                f" for feature branches in this environment"
            )
            raise AssertionError(msg)
        console.print(
            f"  WI #{wi_for_pr3.id} → commit ArtifactLink confirmed "
            f"({len(_links)} link(s))"
        )
        return _links

    _verify_wi_commit_link()
    vstfs_pr3 = (
        f"{WorkItemArtifactUrlPrefix.PULL_REQUEST}"
        f"/{repo.project.id}/{repo.id}/{pr3.pr_id}"
    )
    raw.patch_work_item(
        wi_for_pr3_api,
        [
            raw.JsonPatchAdd(
                path="/relations/-",
                value={
                    "rel": WorkItemRelationType.ARTIFACT_LINK,
                    "url": vstfs_pr3,
                    "attributes": {"name": "Pull Request"},
                },
            )
        ],
    )

    def _verify_wi_pr3_link() -> list[raw.WorkItemRelation]:
        item = raw.get_work_item(wi_for_pr3_api, expand=WorkItemExpand.RELATIONS)
        pr_id_str = str(pr3.pr_id)
        matching = [
            r
            for r in item.relations
            if r.rel == WorkItemRelationType.ARTIFACT_LINK and pr_id_str in str(r.url)
        ]
        if not matching:
            msg = f"no ArtifactLink on WI #{item.id} references PR #{pr3.pr_id}"
            raise AssertionError(msg)
        console.print(f"  WI #{item.id} → PR #{pr3.pr_id} (ArtifactLink) confirmed")
        return matching

    _verify_wi_pr3_link()


def _run_pr3_scenario(
    project_api_call: raw.ApiCall,
    repo_api_call: raw.ApiCall,
    repo: raw.RepositoryInfo,
    branch_name: str,
    default_branch: str,
    current_sha: raw.CommitId,
    run_ts: str,
    rng: random.Random,
) -> None:
    """PR-3: push #<id> commit, squash-merge, verify WI↔commit and WI↔PR links."""
    wi_for_pr3 = raw.post_work_item(
        project_api_call,
        WorkItemTypeName.TASK,
        [
            raw.JsonPatchAdd(
                path=f"/fields/{WorkItemFieldName.TITLE}",
                value=f"[pyado-smoke-test][WI-PR3][{run_ts}] Commit link",
            ),
            raw.JsonPatchAdd(
                path=f"/fields/{WorkItemFieldName.DESCRIPTION}",
                value="Linked to PR3 via #<id> commit message",
            ),
        ],
    )
    if wi_for_pr3:
        console.print(f"  created WI #{wi_for_pr3.id} for PR3 commit link")

    ab_file_path = f"/smoke-ab-{run_ts}-{rng.randint(10000, 99999)}.txt"
    wi_ref = f"#{wi_for_pr3.id}" if wi_for_pr3 else "no-wi"
    push_ab = raw.post_push(
        repo_api_call,
        raw.GitPushRequest(
            ref_updates=[raw.make_ref_update(branch_name, current_sha)],
            commits=[
                raw.GitPushCommit(
                    comment=f"[pyado-smoke-test] {wi_ref} verify WI commit link",
                    changes=[
                        raw.GitPushChange(
                            change_type=GitChangeType.ADD,
                            item=raw.GitPushChangeItem(path=ab_file_path),
                            new_content=raw.GitPushNewContent(
                                content="#<id> smoke test\n"
                            ),
                        )
                    ],
                )
            ],
        ),
    )
    if push_ab:
        current_sha = push_ab.commits[0].commit_id

    # Abandon any stale active PRs on this branch before creating PR3.
    for stale_pr_ in raw.iter_pull_requests(
        project_api_call,
        search_criteria=raw.PullRequestSearchCriteria(
            status=PullRequestStatus.ACTIVE,
            source_ref_name=branch_name,
        ),
    ):
        stale_pr_api = raw.get_pull_request_api_call(
            project_api_call, stale_pr_.repository.id, stale_pr_.pr_id
        )
        raw.patch_pull_request(
            stale_pr_api,
            raw.PullRequestUpdateRequest(status=PullRequestStatus.ABANDONED),
        )

    pr3 = raw.post_pull_request(
        repo_api_call,
        raw.PullRequestCreateRequest(
            title=f"[pyado-smoke-test][PR3][{run_ts}] Temporary PR (commit WI link)",
            source_ref_name=branch_name,
            target_ref_name=default_branch,
            completion_options=raw.PullRequestCompletionOptions(
                squash_merge=True,
                delete_source_branch=False,
                merge_strategy=PullRequestMergeStrategy.SQUASH,
            ),
            description=(
                "Created by pyado smoke_test.py — squash-merged with #<id> commit"
            ),
        ),
    )
    pr3_api_call = raw.get_pull_request_api_call(
        project_api_call, pr3.repository.id, pr3.pr_id
    )
    _pr3_merge_and_verify(pr3_api_call, pr3, current_sha, default_branch)
    _pr3_check_wi_links(project_api_call, repo, pr3, wi_for_pr3)


def _run_pr_suite(
    project_api_call: raw.ApiCall,
    repo_api_call: raw.ApiCall,
    repo: raw.RepositoryInfo,
    branch_name: str,
    default_branch: str,
    head_sha: raw.CommitId,
    run_ts: str,
    rng: random.Random,
    reviewer_id: str | None,
) -> None:
    """Pre-cleanup, branch create, file pushes, and all three PR scenarios."""
    # Pre-cleanup: delete the branch if it already exists from an aborted run
    filter_name = branch_name.removeprefix("refs/")
    existing = list(
        raw.iter_refs(repo_api_call, raw.GitRefFilter(name_filter=filter_name))
    )
    if existing:
        raw.post_repository_refs(
            repo_api_call,
            [
                raw.GitRefUpdate(
                    name=branch_name,
                    new_object_id=raw.ZERO_SHA,
                    old_object_id=existing[0].object_id,
                )
            ],
        )

    raw.post_repository_refs(
        repo_api_call,
        [
            raw.GitRefUpdate(
                name=branch_name, new_object_id=head_sha, old_object_id=raw.ZERO_SHA
            )
        ],
    )

    file_path = f"/smoke-{run_ts}-{rng.randint(10000, 99999)}.txt"
    file_content = f"pyado smoke test\nseed={rng.randint(0, 999999)}\n"

    current_sha = head_sha
    push_result = raw.post_push(
        repo_api_call,
        raw.GitPushRequest(
            ref_updates=[raw.make_ref_update(branch_name, current_sha)],
            commits=[
                raw.GitPushCommit(
                    comment="[pyado-smoke-test] add smoke test file",
                    changes=[
                        raw.GitPushChange(
                            change_type=GitChangeType.ADD,
                            item=raw.GitPushChangeItem(path=file_path),
                            new_content=raw.GitPushNewContent(content=file_content),
                        )
                    ],
                )
            ],
        ),
    )
    if push_result:
        current_sha = push_result.commits[0].commit_id

    if push_result:
        raw.get_commit_diff_page(
            repo_api_call, head_sha, push_result.commits[0].commit_id
        )
        raw.get_repository_item_bytes(
            repo_api_call,
            file_path,
            push_result.commits[0].commit_id,
            VersionDescriptorType.COMMIT,
        )

    push_edit = raw.post_push(
        repo_api_call,
        raw.GitPushRequest(
            ref_updates=[raw.make_ref_update(branch_name, current_sha)],
            commits=[
                raw.GitPushCommit(
                    comment="[pyado-smoke-test] edit smoke test file",
                    changes=[
                        raw.GitPushChange(
                            change_type=GitChangeType.EDIT,
                            item=raw.GitPushChangeItem(path=file_path),
                            new_content=raw.GitPushNewContent(
                                content=file_content + "edited\n"
                            ),
                        )
                    ],
                )
            ],
        ),
    )
    if push_edit:
        current_sha = push_edit.commits[0].commit_id

    _run_pr1_scenario(
        project_api_call,
        repo_api_call,
        branch_name,
        default_branch,
        run_ts,
        reviewer_id,
        file_path,
    )
    _run_pr2_scenario(
        project_api_call,
        repo_api_call,
        repo,
        branch_name,
        default_branch,
        current_sha,
        run_ts,
    )
    _run_pr3_scenario(
        project_api_call,
        repo_api_call,
        repo,
        branch_name,
        default_branch,
        current_sha,
        run_ts,
        rng,
    )


def test_pull_request_write(
    project_api_call: raw.ApiCall,
    git_read: tuple[
        raw.RepositoryInfo | None, raw.ApiCall | None, list[raw.GitCommitRef]
    ],
    rng: random.Random,
    run_ts: str,
    reviewer_id: str | None,
) -> None:
    """Create PRs, exercise labels/threads/reviewers, merge and verify WI links."""
    repo, repo_api_call, commits = git_read
    if repo is None or repo_api_call is None:
        return
    console.print("\n=== GIT & PULL REQUEST (write) ===")

    if not commits:
        return

    default_branch = repo.default_branch or "refs/heads/main"
    branch_name = f"refs/heads/pyado-smoke-{rng.randint(100000, 999999)}"
    console.print(f"  branch: {branch_name}")

    # Fetch the current default-branch HEAD at write time
    default_branch_short = default_branch.removeprefix("refs/")
    main_refs = list(
        raw.iter_refs(repo_api_call, raw.GitRefFilter(name_filter=default_branch_short))
    )
    head_sha: raw.CommitId = (
        main_refs[0].object_id if main_refs else commits[0].commit_id
    )

    try:
        _run_pr_suite(
            project_api_call,
            repo_api_call,
            repo,
            branch_name,
            default_branch,
            head_sha,
            run_ts,
            rng,
            reviewer_id,
        )

    finally:
        # Delete branch regardless of what happened above
        try:
            filter_name = branch_name.removeprefix("refs/")
            refs = list(
                raw.iter_refs(repo_api_call, raw.GitRefFilter(name_filter=filter_name))
            )
            if refs:
                raw.post_repository_refs(
                    repo_api_call,
                    [
                        raw.GitRefUpdate(
                            name=branch_name,
                            new_object_id=raw.ZERO_SHA,
                            old_object_id=refs[0].object_id,
                        )
                    ],
                )
                console.print(f"  (cleaned up branch {branch_name})")
        except Exception as cleanup_ex:
            console.print(f"  \033[93mWARN\033[0m  branch cleanup failed: {cleanup_ex}")
