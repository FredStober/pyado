"""Smoke tests for git repository read and write endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import random

from pyado import raw
from pyado.raw.smoke_test._runner import _DIM, _RESET, _skip, _take, console, run


def _read_file_content(
    repo_api_call: raw.ApiCall,
    repo: raw.RepositoryInfo,
    commits: list[raw.GitCommitRef],
    rng: random.Random,
) -> None:
    """Smoke-test get_repository_item_bytes for a few paths at commit and branch."""
    head_sha = commits[0].commit_id
    paths = ["/README.md", "/pyproject.toml", "/.gitignore", "/nonexistent.txt"]
    rng.shuffle(paths)
    for path in paths[:3]:
        run(
            f"get_repository_item_bytes [{path}, commit]",
            lambda p=path, sha=head_sha: raw.get_repository_item_bytes(
                repo_api_call, p, sha, "commit"
            ),
        )
    short_branch = (repo.default_branch or "refs/heads/main").removeprefix(
        "refs/heads/"
    )
    branch_paths = rng.sample(paths, min(2, len(paths)))
    for path in branch_paths:
        run(
            f"get_repository_item_bytes [{path}, branch={short_branch}]",
            lambda p=path, b=short_branch: raw.get_repository_item_bytes(
                repo_api_call, p, b, "branch"
            ),
        )


def _read_commit_diff(
    repo_api_call: raw.ApiCall,
    commits: list[raw.GitCommitRef],
    rng: random.Random,
) -> None:
    """Smoke-test get_commit_diff_page for two random commit pairs."""
    if len(commits) < 2:
        _skip("get_commit_diff_page", "fewer than 2 commits available")
        return
    top_sha = commits[0].commit_id
    base_idx = rng.randint(1, min(3, len(commits) - 1))
    base_sha = commits[base_idx].commit_id
    diff_variants: list[tuple[str, dict]] = [
        ("get_commit_diff_page [default]", {}),
        ("get_commit_diff_page [top=10]", {"top": 10}),
        ("get_commit_diff_page [skip=0, top=5]", {"skip": 0, "top": 5}),
    ]
    rng.shuffle(diff_variants)
    for label, kwargs in diff_variants[:2]:
        run(
            label,
            lambda b=base_sha, t=top_sha, k=kwargs: raw.get_commit_diff_page(
                repo_api_call, b, t, **k
            ),
        )


def _test_git_read(
    project_api_call: raw.ApiCall,
    rng: random.Random,
) -> tuple[raw.RepositoryInfo | None, raw.ApiCall | None, list[raw.GitCommitRef]]:
    """Return (first_repo, repo_api_call, commits)."""
    console.print("\n=== REPOSITORIES & GIT (read) ===")

    repos = run(
        "iter_repository_details",
        lambda: raw.list_repository_details(project_api_call),
    )
    if not repos:
        for label in (
            "iter_refs",
            "get_repository_commits",
            "get_repository_item_bytes",
            "get_commit_diff_page",
        ):
            _skip(label, "no repositories found")
        return None, None, []

    repo = repos[0]
    console.print(f"  {_DIM}repo: {repo.name}  id={repo.id}{_RESET}")

    repo_api_call = raw.get_repository_api_call(project_api_call, repo.id)

    # --- refs ---
    ref_variants: list[tuple[str, raw.GitRefFilter | None]] = [
        ("iter_refs [no filter]", None),
        (
            "iter_refs [name_filter=heads/main]",
            raw.GitRefFilter(name_filter="heads/main"),
        ),
        ("iter_refs [name_contains=main]", raw.GitRefFilter(name_contains="main")),
        (
            "iter_refs [name_filter=heads + name_contains=main]",
            raw.GitRefFilter(
                name_filter="heads",
                name_contains="main",
            ),
        ),
    ]
    rng.shuffle(ref_variants)
    for label, ref_filter in ref_variants[:3]:
        run(label, lambda f=ref_filter: _take(raw.list_refs(repo_api_call, f), 10))

    # --- commits ---
    commit_variants: list[tuple[str, raw.GitCommitSearchCriteria | None]] = [
        ("get_repository_commits [no filter]", None),
        ("get_repository_commits [top=1]", raw.GitCommitSearchCriteria(top=1)),
        ("get_repository_commits [top=10]", raw.GitCommitSearchCriteria(top=10)),
        (
            "get_repository_commits [item_path=/]",
            raw.GitCommitSearchCriteria(item_path="/", top=3),
        ),
        (
            "get_repository_commits [item_path=/README.md]",
            raw.GitCommitSearchCriteria(item_path="/README.md", top=2),
        ),
    ]
    rng.shuffle(commit_variants)
    commits: list[raw.GitCommitRef] = []
    for label, criteria in commit_variants[:3]:
        result = run(
            label,
            lambda sc=criteria: raw.get_repository_commits(repo_api_call, sc),
        )
        if result and not commits:
            commits = result

    if commits:
        head_sha_early = commits[0].commit_id
        run(
            "get_repository_commits [item_version=commit]",
            lambda sha=head_sha_early: raw.get_repository_commits(
                repo_api_call,
                raw.GitCommitSearchCriteria(
                    item_version=sha,
                    item_version_type="commit",
                    top=3,
                ),
            ),
        )
        _read_file_content(repo_api_call, repo, commits, rng)

    _read_commit_diff(repo_api_call, commits, rng)

    return repo, repo_api_call, commits


def _test_git_extras_read(
    project_api_call: raw.ApiCall,
    repo_api_call: raw.ApiCall | None,
    repo: raw.RepositoryInfo | None,
    commits: list[raw.GitCommitRef],
    rng: random.Random,
) -> None:
    del project_api_call, rng
    console.print("\n=== GIT EXTRAS (read) ===")
    if repo is None or repo_api_call is None:
        for label in (
            "get_repository_info",
            "get_repository_statistics",
            "iter_tags",
            "get_commit_by_id",
            "get_git_acl",
            "make_git_acl_token",
        ):
            _skip(label, "no repository found")
        return

    run("get_repository_info", lambda: raw.get_repository_info(repo_api_call))

    short_branch = (repo.default_branch or "refs/heads/main").removeprefix(
        "refs/heads/"
    )
    run(
        f"get_repository_statistics [branch={short_branch!r}]",
        lambda b=short_branch: raw.get_repository_statistics(repo_api_call, b),
    )

    # list_repository_items — root listing (default one-level), then
    # a branch-scoped call
    run(
        "list_repository_items [root, default branch]",
        lambda: raw.list_repository_items(repo_api_call),
    )
    run(
        f"list_repository_items [root, branch={short_branch!r}]",
        lambda b=short_branch: raw.list_repository_items(
            repo_api_call, branch=b, recursion_level=raw.RecursionLevel.ONE_LEVEL
        ),
    )

    run("list_tags", lambda: raw.list_tags(repo_api_call))

    if commits:
        run(
            "get_commit_by_id",
            lambda sha=commits[0].commit_id: raw.get_commit_by_id(repo_api_call, sha),
        )

    # ACL — get_git_acl needs an org-level ApiCall (no /_apis, no project segment)
    # repo_api_call.url is like https://dev.azure.com/{org}/{project}/_apis/git/...
    # Split at /_apis to get {org}/{project}, then strip the project segment.
    proj_with_org = repo_api_call.url.unicode_string().split("/_apis")[0]
    org_base = proj_with_org.rsplit("/", 1)[0]
    org_base_api_call = raw.ApiCall(
        access_token=repo_api_call.access_token,
        url=org_base,
    )
    run(
        "make_git_acl_token [project-level]",
        lambda: raw.make_git_acl_token(repo.project.id),
    )
    run(
        "make_git_acl_token [repo-level]",
        lambda: raw.make_git_acl_token(repo.project.id, repo.id),
    )
    run(
        "get_git_acl [project-level]",
        lambda api=org_base_api_call: raw.get_git_acl(api, repo.project.id),
    )
    run(
        "get_git_acl [repo-level]",
        lambda api=org_base_api_call: raw.get_git_acl(api, repo.project.id, repo.id),
    )

    # Commit.iter_changes
    if commits:
        run(
            "iter_pr_statuses [if any PRs]",
            lambda: None,  # exercised via pr section
        )


def _test_git_extras_write(
    project_api_call: raw.ApiCall,
    repo_api_call: raw.ApiCall | None,
    repo: raw.RepositoryInfo | None,
    commits: list[raw.GitCommitRef],
    rng: random.Random,
) -> None:
    del project_api_call
    console.print("\n=== GIT EXTRAS (write) ===")
    if repo is None or repo_api_call is None or not commits:
        for label in ("create_tag", "delete_tag"):
            _skip(label, "no repository or commits found")
        return

    tag_name = f"smoke-tag-{rng.randint(10000, 99999)}"
    head_sha = commits[0].commit_id
    run(
        f"create_tag [name={tag_name!r}]",
        lambda: raw.create_tag(repo_api_call, tag_name, head_sha),
    )
    run(
        f"delete_tag [name={tag_name!r}]",
        lambda: raw.delete_tag(repo_api_call, tag_name, head_sha),
    )
