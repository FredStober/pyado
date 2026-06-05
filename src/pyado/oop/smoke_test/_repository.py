"""Smoke tests for Repository."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import datetime
import random
import uuid

from pyado.oop import (
    AddFile,
    DeleteFile,
    EditFile,
    Project,
    PullRequest,
    RenameFile,
    Repository,
    WorkItem,
)
from pyado.oop.smoke_test._runner import _skip, _take, console, run
from pyado.raw import (
    GitPushChange,
    GitPushChangeItem,
    GitPushCommit,
    GitPushNewContent,
    PullRequestCompletionOptions,
    PullRequestStatus,
    PullRequestStatusState,
    PullRequestThreadStatus,
    PullRequestVote,
    make_ref_update,
)


def _read_commits(repo: Repository, commits: list) -> None:
    """Exercise commit-related read methods."""
    head_commit = commits[0]
    run("repo.get_commit(sha)", lambda: repo.get_commit(head_commit.sha))
    run("commit.sha", lambda: head_commit.sha)
    run("commit.message", lambda: head_commit.message)
    run("commit.author_name", lambda: head_commit.author_name)
    run("commit.author_email", lambda: head_commit.author_email)
    run("commit.author_date", lambda: head_commit.author_date)
    run("commit.committer_name", lambda: head_commit.committer_name)
    run("commit.committer_email", lambda: head_commit.committer_email)
    run("commit.committer_date", lambda: head_commit.committer_date)
    run("commit.info", lambda: head_commit.info)
    run("commit.repo (back-nav)", lambda: head_commit.repo)
    run("commit.project (back-nav)", lambda: head_commit.project)
    run("commit.org (back-nav)", lambda: head_commit.org)

    if len(commits) >= 2:
        run(
            "repo.iter_commit_diff(base, target)",
            lambda: _take(repo.iter_commit_diff(commits[-1].sha, commits[0].sha), 10),
        )
        run(
            "repo.list_commit_diff(base, target)",
            lambda: repo.list_commit_diff(commits[-1].sha, commits[0].sha),
        )
    run(
        "repo.get_last_commit_touching_file()",
        lambda: repo.get_last_commit_touching_file("/", head_commit.sha),
    )


def _read_files(repo: Repository, commits: list, branch: str | None) -> None:
    """Exercise file and branch-scoped read methods."""
    if not branch:
        return
    run(
        "repo.iter_commits(branch=main, top=3)",
        lambda br=branch: list(repo.iter_commits(branch=br, top=3)),
    )
    if commits:
        run(
            "repo.get_file_at_branch()",
            lambda br=branch: repo.get_file_at_branch("/README.md", br),
        )
        run(
            "repo.get_file_bytes_at_branch()",
            lambda br=branch: repo.get_file_bytes_at_branch("/README.md", br),
        )
        run(
            "repo.get_file_at_commit()",
            lambda sha=commits[0].sha: repo.get_file_at_commit("/README.md", sha),
        )
        run(
            "repo.get_file_bytes_at_commit()",
            lambda sha=commits[0].sha: repo.get_file_bytes_at_commit("/README.md", sha),
        )
        run(
            "repo.get_statistics(branch)",
            lambda br=branch: repo.get_statistics(br),
        )


def _read_commit_extras(repo: Repository, commits: list) -> None:
    """Exercise commit.get_statuses, iter_changes and get_pr_for_commit."""
    run(
        "repo.get_pr_for_commit(sha)",
        lambda sha=commits[0].sha: repo.get_pr_for_commit(sha),
    )
    commit_obj = run(
        "repo.get_commit(sha) [for Commit read]",
        lambda sha=commits[0].sha: repo.get_commit(sha),
    )
    if commit_obj:
        run("commit.get_statuses()", lambda c=commit_obj: c.get_statuses())
        changes = list(_take(commit_obj.iter_changes(), 5))
        run("commit.iter_changes()", lambda c=commit_obj: _take(c.iter_changes(), 5))
        run("commit.list_changes()", lambda c=commit_obj: c.list_changes())
        if changes and changes[0].item and changes[0].item.path:
            run(
                "commit.get_file(path)",
                lambda c=commit_obj, p=changes[0].item.path: c.get_file(p),
            )


def _read_prs(repo: Repository, branch: str | None) -> None:
    """Exercise PR read methods on the repository."""
    run(
        "repo.iter_pull_requests(ACTIVE)",
        lambda: _take(repo.iter_pull_requests(status=PullRequestStatus.ACTIVE), 3),
    )
    run(
        "repo.iter_pull_requests(COMPLETED)",
        lambda: _take(repo.iter_pull_requests(status=PullRequestStatus.COMPLETED), 5),
    )
    run("repo.list_pull_requests()", repo.list_pull_requests)
    run(
        "repo.get_pr_for_branch(main)",
        lambda br=branch: repo.get_pr_for_branch(br) if br else None,
    )


def _test_repository_read(
    proj: Project,
    rng: random.Random,
) -> tuple[Repository | None, list]:
    del rng
    console.print("\n=== Repository (read) ===")
    repos = run("proj.iter_repositories()", lambda: list(proj.iter_repositories()))
    if not repos:
        _skip("proj.get_repository(name)", "no repos")
        return None, []

    repo: Repository = repos[0]
    run(
        "proj.get_repository(name)",
        lambda: proj.get_repository(repo.name),
    )

    # Properties
    run("repo.id", lambda: repo.id)
    run("repo.name", lambda: repo.name)
    run("repo.default_branch", lambda: repo.default_branch)
    run("repo.web_url", lambda: repo.web_url)
    run("repo.info", lambda: repo.info)
    run("repo.api_call", lambda: repo.api_call)
    run("repo.project (back-nav)", lambda: repo.project)
    run("repo.org (back-nav)", lambda: repo.org)
    run("repo.refresh()", repo.refresh)

    # File-change to_git_change helpers (pure in-memory, no API call)
    run("AddFile.to_git_change()", lambda: AddFile("/smoke.txt", "x").to_git_change())
    run("EditFile.to_git_change()", lambda: EditFile("/smoke.txt", "y").to_git_change())
    run("DeleteFile.to_git_change()", lambda: DeleteFile("/smoke.txt").to_git_change())
    run(
        "RenameFile.to_git_change()",
        lambda: RenameFile("/smoke.txt", "/smoke2.txt").to_git_change(),
    )

    # Refs
    run("repo.iter_refs()", lambda: _take(repo.iter_refs(), 5))
    run("repo.list_refs()", repo.list_refs)
    run(
        "repo.iter_refs(name_filter)",
        lambda: _take(repo.iter_refs(name_filter="heads/main"), 3),
    )
    run(
        "repo.iter_refs(name_contains)",
        lambda: _take(repo.iter_refs(name_contains="main"), 3),
    )

    # Commits
    commits = run("repo.iter_commits(top=5)", lambda: list(repo.iter_commits(top=5)))
    run("repo.list_commits(top=5)", lambda: repo.list_commits(top=5))
    if commits:
        _read_commits(repo, commits)

    # Branch filtering
    branch = None
    if repo.default_branch:
        short = repo.default_branch.removeprefix("refs/heads/")
        branch = short
        _read_files(repo, commits or [], branch)

    # ACL
    run("repo.get_acl()", repo.get_acl)

    # Additional read methods
    run("repo.iter_branches()", lambda: _take(repo.iter_branches(), 5))
    run("repo.list_branches()", repo.list_branches)
    run("repo.list_tags()", repo.list_tags)
    run("repo.get_default_branch_commit()", repo.get_default_branch_commit)

    if commits:
        _read_commit_extras(repo, commits)

    _read_prs(repo, branch)

    return repo, commits or []


def _exercise_pr_write(
    repo: Repository,
    pr: PullRequest,
    existing_wi: WorkItem | None,
    thread: object,
) -> None:
    """Exercise PullRequest write methods on an open PR."""
    del repo
    run(
        "pr.update(description)",
        lambda: pr.update(description="Updated by OOP smoke test."),
    )
    run(
        "pr.add_tag()",
        lambda: pr.add_tag("oop-smoke"),
    )
    run("pr.get_tags() after add", pr.get_tags)
    run("pr.remove_tag()", lambda: pr.remove_tag("oop-smoke"))

    if thread:
        tid = thread.id  # type: ignore[union-attr]
        run(
            "pr.reply_to_thread()",
            lambda t=tid: pr.reply_to_thread(t, "OOP smoke reply."),
        )
        run(
            "pr.update_thread_status(FIXED)",
            lambda t=tid: pr.update_thread_status(t, PullRequestThreadStatus.FIXED),
        )

    run(
        "pr.set_status(succeeded)",
        lambda: pr.set_status(
            PullRequestStatusState.SUCCEEDED,
            "oop-smoke-check",
            description="OOP smoke test status",
        ),
    )
    run("pr.iter_statuses()", lambda: list(pr.iter_statuses()))

    if existing_wi:
        run(
            "pr.link_work_item(wi)",
            lambda: pr.link_work_item(existing_wi),
        )
        run(
            "pr.set_work_item_refs([wi.id])",
            lambda: pr.set_work_item_refs([existing_wi.id]),
        )

    author_id = pr.info.created_by.id if pr.info.created_by else None
    if author_id:
        run(
            "pr.add_reviewer(reviewer_id)",
            lambda aid=str(author_id): pr.add_reviewer(aid, is_required=False),
        )
        run(
            "pr.vote(reviewer_id, APPROVED)",
            lambda aid=str(author_id): pr.vote(aid, PullRequestVote.APPROVED),
        )
        run(
            "pr.vote(reviewer_id, NO_VOTE) [reset]",
            lambda aid=str(author_id): pr.vote(aid, PullRequestVote.NO_VOTE),
        )
        run(
            "pr.remove_reviewer(reviewer_id)",
            lambda aid=str(author_id): pr.remove_reviewer(aid),
        )
    else:
        for label in (
            "pr.add_reviewer(reviewer_id)",
            "pr.vote(reviewer_id, APPROVED)",
            "pr.vote(reviewer_id, NO_VOTE) [reset]",
            "pr.remove_reviewer(reviewer_id)",
        ):
            _skip(label, "no reviewer ID available")

    run("pr.iter_threads()", lambda: list(pr.iter_threads()))
    run("pr.iter_commits()", lambda: list(pr.iter_commits()))
    run("pr.iter_iterations()", lambda: list(pr.iter_iterations()))
    run("pr.iter_work_item_ids()", lambda: list(pr.iter_work_item_ids()))
    run("pr.iter_files_changed()", lambda: _take(pr.iter_files_changed(), 5))
    pr_threads = list(pr.iter_threads())
    if pr_threads:
        run("pr.get_thread(id)", lambda tid=pr_threads[0].id: pr.get_thread(tid))

    run("pr.sync_tags({'oop-smoke-tag'})", lambda: pr.sync_tags({"oop-smoke-tag"}))
    run("pr.sync_tags({}) [clear]", lambda: pr.sync_tags(set()))

    auto_complete_id = pr.info.created_by.id if pr.info.created_by else None
    if auto_complete_id:
        run(
            "pr.enable_auto_complete(identity_id)",
            lambda aid=str(auto_complete_id): pr.enable_auto_complete(
                aid,
                completion_options=PullRequestCompletionOptions(squash_merge=True),
            ),
        )
        pr.refresh()
        if pr.status != PullRequestStatus.ACTIVE:
            _skip(
                "pr.disable_auto_complete()",
                "PR auto-completed after enable_auto_complete",
            )
        else:
            run("pr.disable_auto_complete()", pr.disable_auto_complete)

    run("pr.abandon()", pr.abandon)


def _test_write_branch_and_pr(
    proj: Project,
    repo: Repository,
    existing_wi: WorkItem | None,
) -> None:
    """Create a branch, commit a file, open a PR, exercise it, then abandon."""
    del proj
    console.print("\n=== Repository + PullRequest (write) ===")

    if repo.default_branch is None:
        _skip("branch+PR write tests", "repo has no default branch")
        return

    branch_name = f"oop-smoke-{uuid.uuid4().hex[:8]}"
    head_commits = list(repo.iter_commits(top=1))
    if not head_commits:
        _skip("branch+PR write tests", "repo has no commits")
        return

    head_sha = head_commits[0].sha

    run("repo.create_branch()", lambda: repo.create_branch(branch_name, head_sha))

    unique_file = f"/oop_smoke_{uuid.uuid4().hex[:12]}.txt"
    push_result = run(
        "repo.commit(branch, msg, [AddFile])",
        lambda: repo.commit(
            branch_name,
            "oop-smoke: add test file",
            [
                AddFile(
                    unique_file,
                    "OOP smoke test\nTimestamp: "
                    f"{datetime.datetime.now(datetime.UTC).isoformat()}\n",
                )
            ],
        ),
    )
    if push_result is None:
        run("repo.delete_branch()", lambda: repo.delete_branch(branch_name, head_sha))
        return

    new_sha = (
        push_result.commits[0].commit_id
        if (push_result and push_result.commits)
        else head_sha
    )
    run(
        "repo.make_ref_update(branch)",
        lambda br=branch_name: repo.make_ref_update(br),
    )

    target = repo.default_branch.removeprefix("refs/heads/")
    pr: PullRequest | None = run(
        "repo.create_pull_request()",
        lambda: repo.create_pull_request(
            f"[oop-smoke] OOP smoke test PR {uuid.uuid4().hex[:6]}",
            branch_name,
            target,
            description="Created by smoke_test_oop.py — safe to abandon.",
        ),
    )
    if pr is None:
        run(
            "repo.delete_branch() [cleanup]",
            lambda: repo.delete_branch(branch_name, new_sha),
        )
        return

    thread = run(
        "pr.add_thread()",
        lambda: pr.add_thread("OOP smoke test thread — safe to delete."),
    )
    _exercise_pr_write(repo, pr, existing_wi, thread)

    # Delete the test branch
    ref_updates = run(
        "repo.make_ref_update(branch) [for delete]",
        lambda: repo.make_ref_update(branch_name),
    )
    if ref_updates:
        run(
            "repo.delete_branch()",
            lambda br=branch_name, sha=new_sha: repo.delete_branch(br, sha),
        )


def _scenario_a_draft(
    repo: Repository,
    head_sha: str,
    target: str,
) -> None:
    """Scenario A: Draft PR lifecycle — create, publish, retitle, abandon."""
    branch_a = f"oop-smoke-draft-{uuid.uuid4().hex[:8]}"
    run(
        "repo.create_branch() [draft scenario]",
        lambda: repo.create_branch(branch_a, head_sha),
    )
    push_a = run(
        "repo.commit() [draft scenario]",
        lambda: repo.commit(
            branch_a,
            "oop-smoke: draft PR test",
            [AddFile(f"/oop_smoke_draft_{uuid.uuid4().hex[:10]}.txt", "draft smoke\n")],
        ),
    )
    sha_a = push_a.commits[0].commit_id if (push_a and push_a.commits) else head_sha
    pr_a = run(
        "repo.create_pull_request() [draft scenario]",
        lambda: repo.create_pull_request(
            f"[oop-smoke] draft PR {uuid.uuid4().hex[:6]}",
            branch_a,
            target,
            description="Draft lifecycle smoke test — safe to abandon.",
        ),
    )
    if pr_a is not None:
        run("pr.update(is_draft=True)", lambda: pr_a.update(is_draft=True))
        pr_a.refresh()
        run("pr.info.is_draft (True)", lambda: pr_a.info.is_draft)
        run(
            "pr.update(title=...)",
            lambda: pr_a.update(
                title=f"[oop-smoke] draft PR updated {uuid.uuid4().hex[:6]}"
            ),
        )
        run("pr.update(is_draft=False)", lambda: pr_a.update(is_draft=False))
        pr_a.refresh()
        run("pr.info.is_draft (False)", lambda: pr_a.info.is_draft)
        run("pr.abandon() [draft scenario]", pr_a.abandon)
    else:
        for label in (
            "pr.update(is_draft=True)",
            "pr.info.is_draft (True)",
            "pr.update(title=...)",
            "pr.update(is_draft=False)",
            "pr.info.is_draft (False)",
            "pr.abandon() [draft scenario]",
        ):
            _skip(label, "create_pull_request failed")
    run(
        "repo.delete_branch() [draft scenario]",
        lambda: repo.delete_branch(branch_a, sha_a),
    )


def _scenario_b_multi_iter(
    repo: Repository,
    head_sha: str,
    target: str,
) -> None:
    """Scenario B: Push a second commit after PR creation; verify two iterations."""
    branch_b = f"oop-smoke-iter-{uuid.uuid4().hex[:8]}"
    run(
        "repo.create_branch() [multi-iter scenario]",
        lambda: repo.create_branch(branch_b, head_sha),
    )
    push_b1 = run(
        "repo.commit() iteration 1 [multi-iter scenario]",
        lambda: repo.commit(
            branch_b,
            "oop-smoke: multi-iter iteration 1",
            [AddFile(f"/oop_smoke_iter_{uuid.uuid4().hex[:10]}.txt", "iteration 1\n")],
        ),
    )
    sha_b = push_b1.commits[0].commit_id if (push_b1 and push_b1.commits) else head_sha
    pr_b = run(
        "repo.create_pull_request() [multi-iter scenario]",
        lambda: repo.create_pull_request(
            f"[oop-smoke] multi-iter PR {uuid.uuid4().hex[:6]}",
            branch_b,
            target,
            description="Multi-iteration smoke test — safe to abandon.",
        ),
    )
    if pr_b is not None:
        push_b2 = run(
            "repo.commit() iteration 2 [multi-iter scenario]",
            lambda: repo.commit(
                branch_b,
                "oop-smoke: multi-iter iteration 2",
                [
                    AddFile(
                        f"/oop_smoke_iter2_{uuid.uuid4().hex[:10]}.txt",
                        "iteration 2\n",
                    )
                ],
            ),
        )
        if push_b2 and push_b2.commits:
            sha_b = push_b2.commits[0].commit_id
        pr_b.refresh()
        iterations_b = run(
            "pr.iter_iterations() ≥ 2 [multi-iter scenario]",
            lambda: list(pr_b.iter_iterations()),
        )
        if iterations_b and len(iterations_b) >= 2:
            second_iter_id = sorted(it.id for it in iterations_b)[1]
            run(
                "pr.get_iteration_changes(2) [multi-iter scenario]",
                lambda iid=second_iter_id: pr_b.get_iteration_changes(iid),
            )
        else:
            _skip(
                "pr.get_iteration_changes(2) [multi-iter scenario]",
                "fewer than 2 iterations visible",
            )
        run("pr.abandon() [multi-iter scenario]", pr_b.abandon)
    else:
        for label in (
            "repo.commit() iteration 2 [multi-iter scenario]",
            "pr.iter_iterations() ≥ 2 [multi-iter scenario]",
            "pr.get_iteration_changes(2) [multi-iter scenario]",
            "pr.abandon() [multi-iter scenario]",
        ):
            _skip(label, "create_pull_request failed")
    run(
        "repo.delete_branch() [multi-iter scenario]",
        lambda: repo.delete_branch(branch_b, sha_b),
    )


def _scenario_c_anchored_thread(
    repo: Repository,
    head_sha: str,
    target: str,
) -> None:
    """Scenario C: Add a review thread anchored to a specific file path."""
    branch_c = f"oop-smoke-anchor-{uuid.uuid4().hex[:8]}"
    run(
        "repo.create_branch() [anchored-thread scenario]",
        lambda: repo.create_branch(branch_c, head_sha),
    )
    anchor_file = f"/oop_smoke_anchor_{uuid.uuid4().hex[:10]}.txt"
    push_c = run(
        "repo.commit() [anchored-thread scenario]",
        lambda: repo.commit(
            branch_c,
            "oop-smoke: file-anchored thread test",
            [AddFile(anchor_file, "line 1\nline 2\nline 3\n")],
        ),
    )
    sha_c = push_c.commits[0].commit_id if (push_c and push_c.commits) else head_sha
    pr_c = run(
        "repo.create_pull_request() [anchored-thread scenario]",
        lambda: repo.create_pull_request(
            f"[oop-smoke] anchored thread PR {uuid.uuid4().hex[:6]}",
            branch_c,
            target,
            description="File-anchored thread smoke test — safe to abandon.",
        ),
    )
    if pr_c is not None:
        run(
            "pr.add_thread(file_path=...) [anchored-thread scenario]",
            lambda: pr_c.add_thread(
                "OOP smoke: file-anchored comment",
                file_path=anchor_file,
                line=1,
            ),
        )
        anchored_threads = list(pr_c.iter_threads())
        file_thread = next(
            (
                thr
                for thr in anchored_threads
                if thr.thread_context and thr.thread_context.file_path
            ),
            None,
        )
        run(
            "pr.iter_threads() has file-anchored thread",
            lambda t=file_thread: t,
        )
        if file_thread:
            run(
                "pr.get_thread(id) [anchored-thread scenario]",
                lambda tid=file_thread.id: pr_c.get_thread(tid),
            )
        else:
            _skip(
                "pr.get_thread(id) [anchored-thread scenario]",
                "no file-anchored thread found",
            )
        run("pr.abandon() [anchored-thread scenario]", pr_c.abandon)
    else:
        for label in (
            "pr.add_thread(file_path=...) [anchored-thread scenario]",
            "pr.iter_threads() has file-anchored thread",
            "pr.get_thread(id) [anchored-thread scenario]",
            "pr.abandon() [anchored-thread scenario]",
        ):
            _skip(label, "create_pull_request failed")
    run(
        "repo.delete_branch() [anchored-thread scenario]",
        lambda: repo.delete_branch(branch_c, sha_c),
    )


def _test_write_pr_extra_scenarios(proj: Project, repo: Repository) -> None:
    """Three additional PR write scenarios not covered by the main branch+PR test.

    Scenario A — Draft lifecycle: create a draft PR, publish it, update its
    title, then abandon it.

    Scenario B — Multi-iteration: push a second commit to the source branch
    after PR creation and verify that a second iteration is visible.

    Scenario C — File-anchored thread: add a review thread anchored to a
    specific file path and confirm the thread context round-trips correctly.
    """
    del proj
    console.print("\n=== PullRequest extra scenarios (write) ===")

    if repo.default_branch is None:
        for label in (
            "pr draft lifecycle",
            "pr multi-iteration",
            "pr file-anchored thread",
        ):
            _skip(label, "repo has no default branch")
        return

    head_commits = list(repo.iter_commits(top=1))
    if not head_commits:
        for label in (
            "pr draft lifecycle",
            "pr multi-iteration",
            "pr file-anchored thread",
        ):
            _skip(label, "repo has no commits")
        return

    head_sha = head_commits[0].sha
    target = repo.default_branch.removeprefix("refs/heads/")

    _scenario_a_draft(repo, head_sha, target)
    _scenario_b_multi_iter(repo, head_sha, target)
    _scenario_c_anchored_thread(repo, head_sha, target)


def _test_write_repo_extras(repo: Repository) -> None:
    """Exercise Repository methods not covered by _test_write_branch_and_pr."""
    console.print("\n=== Repository (write extras) ===")

    if repo.default_branch is None:
        _skip("repo write-extras tests", "repo has no default branch")
        return

    head_commits = list(repo.iter_commits(top=1))
    if not head_commits:
        _skip("repo write-extras tests", "repo has no commits")
        return

    head_sha = head_commits[0].sha
    branch_name = f"oop-smoke-extras-{uuid.uuid4().hex[:8]}"
    run(
        "repo.create_branch() [extras]",
        lambda: repo.create_branch(branch_name, head_sha),
    )

    # Push a file using push_commits
    file_path = f"/oop_smoke_extras_{uuid.uuid4().hex[:10]}.txt"
    push_result = run(
        "repo.push_commits()",
        lambda: repo.push_commits(
            ref_updates=[make_ref_update(f"refs/heads/{branch_name}", head_sha)],
            commits=[
                GitPushCommit(
                    comment="oop-smoke: push_commits test",
                    changes=[
                        GitPushChange(
                            change_type="add",
                            item=GitPushChangeItem(path=file_path),
                            new_content=GitPushNewContent(
                                content="push_commits smoke\n"
                            ),
                        )
                    ],
                )
            ],
        ),
    )
    current_sha = (
        push_result.commits[0].commit_id
        if (push_result and push_result.commits)
        else head_sha
    )

    # Rename the file
    renamed_path = file_path.replace(".txt", "_renamed.txt")
    rename_result = run(
        "repo.rename_file()",
        lambda: repo.rename_file(
            branch_name,
            file_path,
            renamed_path,
            "oop-smoke: rename file",
        ),
    )
    if rename_result and rename_result.commits:
        current_sha = rename_result.commits[0].commit_id

    # Delete the renamed file
    delete_result = run(
        "repo.delete_file()",
        lambda: repo.delete_file(
            branch_name,
            renamed_path,
            "oop-smoke: delete file",
        ),
    )
    if delete_result and delete_result.commits:
        current_sha = delete_result.commits[0].commit_id

    # Tags
    tag_name = f"oop-smoke-tag-{uuid.uuid4().hex[:8]}"
    run(
        "repo.create_tag()",
        lambda: repo.create_tag(tag_name, current_sha),
    )
    run(
        "repo.delete_tag()",
        lambda: repo.delete_tag(tag_name, current_sha),
    )

    # Cleanup branch
    run(
        "repo.delete_branch() [extras cleanup]",
        lambda: repo.delete_branch(branch_name, current_sha),
    )
