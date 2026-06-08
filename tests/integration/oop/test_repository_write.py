"""Integration tests for Repository and PullRequest OOP classes (write)."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import datetime
import uuid

from pyado.oop import (
    AddFile,
    Project,
    PullRequest,
    Repository,
    WorkItem,
)
from pyado.raw import (
    GitPushChange,
    GitPushChangeItem,
    GitPushCommit,
    GitPushNewContent,
    PullRequestCompletionOptions,
    PullRequestStatus,
    PullRequestStatusState,
    PullRequestThreadResponse,
    PullRequestThreadStatus,
    PullRequestVote,
    make_ref_update,
)
from tests.integration.raw._support import _take, console


def _exercise_pr_write(
    repo: Repository,
    pr: PullRequest,
    existing_wi: WorkItem | None,
    thread: PullRequestThreadResponse | None,
) -> None:
    """Exercise PullRequest write methods on an open PR."""
    del repo
    pr.update(description="Updated by OOP smoke test.")
    pr.add_tag("oop-smoke")
    pr.get_tags()
    pr.remove_tag("oop-smoke")

    if thread:
        tid = thread.id
        if tid is not None:
            pr.reply_to_thread(tid, "OOP smoke reply.")
            pr.update_thread_status(tid, PullRequestThreadStatus.FIXED)

    pr.set_status(
        PullRequestStatusState.SUCCEEDED,
        "oop-smoke-check",
        description="OOP smoke test status",
    )
    list(pr.iter_statuses())

    if existing_wi:
        pr.link_work_item(existing_wi)
        pr.set_work_item_refs([existing_wi.id])

    author_id = pr.info.created_by.id if pr.info.created_by else None
    if author_id:
        pr.add_reviewer(str(author_id), is_required=False)
        pr.vote(str(author_id), PullRequestVote.APPROVED)
        pr.vote(str(author_id), PullRequestVote.NO_VOTE)
        pr.remove_reviewer(str(author_id))

    list(pr.iter_threads())
    list(pr.iter_commits())
    list(pr.iter_iterations())
    list(pr.iter_work_item_ids())
    _take(pr.iter_files_changed(), 5)
    pr_threads = list(pr.iter_threads())
    if pr_threads and pr_threads[0].id is not None:
        pr.get_thread(pr_threads[0].id)

    pr.sync_tags({"oop-smoke-tag"})
    pr.sync_tags(set())

    auto_complete_id = pr.info.created_by.id if pr.info.created_by else None
    if auto_complete_id:
        pr.enable_auto_complete(
            str(auto_complete_id),
            completion_options=PullRequestCompletionOptions(squash_merge=True),
        )
        pr.refresh()
        if pr.status == PullRequestStatus.ACTIVE:
            pr.disable_auto_complete()

    pr.abandon()


def _scenario_a_draft(
    repo: Repository,
    head_sha: str,
    target: str,
) -> None:
    """Scenario A: Draft PR lifecycle — create, publish, retitle, abandon."""
    branch_a = f"oop-smoke-draft-{uuid.uuid4().hex[:8]}"
    repo.create_branch(branch_a, head_sha)
    push_a = repo.commit(
        branch_a,
        "oop-smoke: draft PR test",
        [AddFile(f"/oop_smoke_draft_{uuid.uuid4().hex[:10]}.txt", "draft smoke\n")],
    )
    sha_a = push_a.commits[0].commit_id if (push_a and push_a.commits) else head_sha
    pr_a = repo.create_pull_request(
        f"[oop-smoke] draft PR {uuid.uuid4().hex[:6]}",
        branch_a,
        target,
        description="Draft lifecycle smoke test — safe to abandon.",
    )
    if pr_a is not None:
        pr_a.update(is_draft=True)
        pr_a.refresh()
        _ = pr_a.info.is_draft
        pr_a.update(title=f"[oop-smoke] draft PR updated {uuid.uuid4().hex[:6]}")
        pr_a.update(is_draft=False)
        pr_a.refresh()
        _ = pr_a.info.is_draft
        pr_a.abandon()
    repo.delete_branch(branch_a, sha_a)


def _scenario_b_multi_iter(
    repo: Repository,
    head_sha: str,
    target: str,
) -> None:
    """Scenario B: Push a second commit after PR creation; verify two iterations."""
    branch_b = f"oop-smoke-iter-{uuid.uuid4().hex[:8]}"
    repo.create_branch(branch_b, head_sha)
    push_b1 = repo.commit(
        branch_b,
        "oop-smoke: multi-iter iteration 1",
        [AddFile(f"/oop_smoke_iter_{uuid.uuid4().hex[:10]}.txt", "iteration 1\n")],
    )
    sha_b = push_b1.commits[0].commit_id if (push_b1 and push_b1.commits) else head_sha
    pr_b = repo.create_pull_request(
        f"[oop-smoke] multi-iter PR {uuid.uuid4().hex[:6]}",
        branch_b,
        target,
        description="Multi-iteration smoke test — safe to abandon.",
    )
    if pr_b is not None:
        push_b2 = repo.commit(
            branch_b,
            "oop-smoke: multi-iter iteration 2",
            [AddFile(f"/oop_smoke_iter2_{uuid.uuid4().hex[:10]}.txt", "iteration 2\n")],
        )
        if push_b2 and push_b2.commits:
            sha_b = push_b2.commits[0].commit_id
        pr_b.refresh()
        iterations_b = list(pr_b.iter_iterations())
        if iterations_b and len(iterations_b) >= 2:
            second_iter_id = sorted(it.id for it in iterations_b)[1]
            pr_b.get_iteration_changes(second_iter_id)
        pr_b.abandon()
    repo.delete_branch(branch_b, sha_b)


def _scenario_c_anchored_thread(
    repo: Repository,
    head_sha: str,
    target: str,
) -> None:
    """Scenario C: Add a review thread anchored to a specific file path."""
    branch_c = f"oop-smoke-anchor-{uuid.uuid4().hex[:8]}"
    repo.create_branch(branch_c, head_sha)
    anchor_file = f"/oop_smoke_anchor_{uuid.uuid4().hex[:10]}.txt"
    push_c = repo.commit(
        branch_c,
        "oop-smoke: file-anchored thread test",
        [AddFile(anchor_file, "line 1\nline 2\nline 3\n")],
    )
    sha_c = push_c.commits[0].commit_id if (push_c and push_c.commits) else head_sha
    pr_c = repo.create_pull_request(
        f"[oop-smoke] anchored thread PR {uuid.uuid4().hex[:6]}",
        branch_c,
        target,
        description="File-anchored thread smoke test — safe to abandon.",
    )
    pr_c.add_thread("OOP smoke: file-anchored comment", file_path=anchor_file, line=1)
    anchored_threads = list(pr_c.iter_threads())
    file_thread = next(
        (
            thr
            for thr in anchored_threads
            if thr.thread_context and thr.thread_context.file_path
        ),
        None,
    )
    if file_thread and file_thread.id is not None:
        pr_c.get_thread(file_thread.id)
    pr_c.abandon()
    repo.delete_branch(branch_c, sha_c)


def test_write_branch_and_pr(
    proj: Project,
    repo: Repository | None,
    existing_wi: WorkItem | None,
) -> None:
    """Create a branch, commit, open a PR, exercise write methods, then abandon."""
    if repo is None:
        return
    del proj
    console.print("\n=== Repository + PullRequest (write) ===")

    if repo.default_branch is None:
        return

    branch_name = f"oop-smoke-{uuid.uuid4().hex[:8]}"
    head_commits = list(repo.iter_commits(top=1))
    if not head_commits:
        return

    head_sha = head_commits[0].sha

    repo.create_branch(branch_name, head_sha)

    unique_file = f"/oop_smoke_{uuid.uuid4().hex[:12]}.txt"
    push_result = repo.commit(
        branch_name,
        "oop-smoke: add test file",
        [
            AddFile(
                unique_file,
                "OOP smoke test\nTimestamp: "
                f"{datetime.datetime.now(datetime.UTC).isoformat()}\n",
            )
        ],
    )
    new_sha = (
        push_result.commits[0].commit_id
        if (push_result and push_result.commits)
        else head_sha
    )
    repo.make_ref_update(branch_name)

    target = repo.default_branch.removeprefix("refs/heads/")
    pr: PullRequest | None = repo.create_pull_request(
        f"[oop-smoke] OOP smoke test PR {uuid.uuid4().hex[:6]}",
        branch_name,
        target,
        description="Created by smoke_test_oop.py — safe to abandon.",
    )
    if pr is None:
        repo.delete_branch(branch_name, new_sha)
        return

    thread = pr.add_thread("OOP smoke test thread — safe to delete.")
    _exercise_pr_write(repo, pr, existing_wi, thread)

    # Delete the test branch
    ref_updates = repo.make_ref_update(branch_name)
    if ref_updates:
        repo.delete_branch(branch_name, new_sha)


def test_write_repo_extras(repo: Repository | None) -> None:
    """Exercise repository write extras.

    Covers push_commits, commit_file, rename_file, delete_file, and
    create/delete tag.
    """
    if repo is None:
        return
    console.print("\n=== Repository (write extras) ===")

    if repo.default_branch is None:
        return

    head_commits = list(repo.iter_commits(top=1))
    if not head_commits:
        return

    head_sha = head_commits[0].sha
    branch_name = f"oop-smoke-extras-{uuid.uuid4().hex[:8]}"
    repo.create_branch(branch_name, head_sha)

    # Push a file using push_commits
    file_path = f"/oop_smoke_extras_{uuid.uuid4().hex[:10]}.txt"
    push_result = repo.push_commits(
        ref_updates=[make_ref_update(f"refs/heads/{branch_name}", head_sha)],
        commits=[
            GitPushCommit(
                comment="oop-smoke: push_commits test",
                changes=[
                    GitPushChange(
                        change_type="add",
                        item=GitPushChangeItem(path=file_path),
                        new_content=GitPushNewContent(content="push_commits smoke\n"),
                    )
                ],
            )
        ],
    )
    current_sha = (
        push_result.commits[0].commit_id
        if (push_result and push_result.commits)
        else head_sha
    )

    # A7 — commit_file (add then edit)
    commit_file_path = f"/oop_smoke_cf_{uuid.uuid4().hex[:10]}.txt"
    repo.commit_file(
        commit_file_path, "smoke test\n", "oop-smoke: commit_file add", branch_name
    )
    repo.commit_file(
        commit_file_path,
        "smoke test edited\n",
        "oop-smoke: commit_file edit",
        branch_name,
    )
    # update current_sha to include the commit_file commits
    latest = list(repo.iter_commits(branch=branch_name, top=1))
    if latest:
        current_sha = latest[0].sha

    # Rename the file
    renamed_path = file_path.replace(".txt", "_renamed.txt")
    rename_result = repo.rename_file(
        branch_name, file_path, renamed_path, "oop-smoke: rename file"
    )
    if rename_result and rename_result.commits:
        current_sha = rename_result.commits[0].commit_id

    # Delete the renamed file
    delete_result = repo.delete_file(
        branch_name, renamed_path, "oop-smoke: delete file"
    )
    if delete_result and delete_result.commits:
        current_sha = delete_result.commits[0].commit_id

    # Tags
    tag_name = f"oop-smoke-tag-{uuid.uuid4().hex[:8]}"
    repo.create_tag(tag_name, current_sha)
    repo.delete_tag(tag_name, current_sha)
    annotated_tag_name = f"oop-smoke-atag-{uuid.uuid4().hex[:8]}"
    repo.create_annotated_tag(
        annotated_tag_name, "oop smoke test annotated tag", current_sha
    )

    # Cleanup branch
    repo.delete_branch(branch_name, current_sha)


def test_write_pr_complete(proj: Project, repo: Repository | None) -> None:
    """Create a branch, push a file, open a PR, then squash-merge it."""
    if repo is None:
        return
    del proj
    console.print("\n=== PullRequest.complete() (write) ===")

    if repo.default_branch is None:
        return

    head_commits = list(repo.iter_commits(top=1))
    if not head_commits:
        return

    head_sha = head_commits[0].sha
    branch_name = f"oop-smoke-merge-{uuid.uuid4().hex[:8]}"
    repo.create_branch(branch_name, head_sha)

    file_path = f"/oop_smoke_merge_{uuid.uuid4().hex[:10]}.txt"
    push_result = repo.commit(
        branch_name,
        "oop-smoke: pr.complete test",
        [AddFile(file_path, "pr.complete smoke test\n")],
    )
    new_sha = push_result.commits[0].commit_id if push_result.commits else head_sha
    target = repo.default_branch.removeprefix("refs/heads/")
    pr: PullRequest | None = repo.create_pull_request(
        f"[oop-smoke] pr.complete test {uuid.uuid4().hex[:6]}",
        branch_name,
        target,
        description="Created by smoke_test_oop.py — safe to squash-merge.",
    )
    if pr is None:
        repo.delete_branch(branch_name, new_sha)
        return

    pr_sha = (
        pr.info.last_merge_source_commit.commit_id
        if pr.info.last_merge_source_commit
        else new_sha
    )
    pr.complete(
        pr_sha, completion_options=PullRequestCompletionOptions(squash_merge=True)
    )


def test_write_pr_extra_scenarios(
    proj: Project,
    repo: Repository | None,
) -> None:
    """Exercise extra PR scenarios.

    Covers draft lifecycle, multi-iteration, and file-anchored thread
    scenarios.
    """
    if repo is None:
        return
    del proj
    console.print("\n=== PullRequest extra scenarios (write) ===")

    if repo.default_branch is None:
        return

    head_commits = list(repo.iter_commits(top=1))
    if not head_commits:
        return

    head_sha = head_commits[0].sha
    target = repo.default_branch.removeprefix("refs/heads/")

    _scenario_a_draft(repo, head_sha, target)
    _scenario_b_multi_iter(repo, head_sha, target)
    _scenario_c_anchored_thread(repo, head_sha, target)
