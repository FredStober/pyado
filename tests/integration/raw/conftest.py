"""Session-scoped data fixtures for raw integration tests."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import random

import pytest

from pyado import raw
from tests.integration.raw._support import (
    _take,
    _test_profile,
    console,
)


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
        raw.get_repository_item_bytes(
            repo_api_call, path, head_sha, raw.VersionDescriptorType.COMMIT
        )
    short_branch = (repo.default_branch or "refs/heads/main").removeprefix(
        "refs/heads/"
    )
    branch_paths = rng.sample(paths, min(2, len(paths)))
    for path in branch_paths:
        raw.get_repository_item_bytes(
            repo_api_call, path, short_branch, raw.VersionDescriptorType.BRANCH
        )


def _read_commit_diff(
    repo_api_call: raw.ApiCall,
    commits: list[raw.GitCommitRef],
    rng: random.Random,
) -> None:
    """Smoke-test get_commit_diff_page for two random commit pairs."""
    if len(commits) < 2:
        return
    top_sha = commits[0].commit_id
    base_idx = rng.randint(1, min(3, len(commits) - 1))
    base_sha = commits[base_idx].commit_id
    diff_variants: list[tuple[str, dict[str, int]]] = [
        ("get_commit_diff_page [default]", {}),
        ("get_commit_diff_page [top=10]", {"top": 10}),
        ("get_commit_diff_page [skip=0, top=5]", {"skip": 0, "top": 5}),
    ]
    rng.shuffle(diff_variants)
    for _, kwargs in diff_variants[:2]:
        raw.get_commit_diff_page(repo_api_call, base_sha, top_sha, **kwargs)


def _find_wi_build(
    project_api_call: raw.ApiCall,
    build: raw.BuildDetails,
    builds: list[raw.BuildDetails],
    build_wi_ids: list[int],
) -> tuple[raw.BuildDetails, list[int]]:
    """Return (wi_build, wi_build_ids) — first build that has WI refs."""
    wi_build = build
    wi_build_ids = build_wi_ids
    if not wi_build_ids:
        for candidate in builds[1:]:
            capi = raw.get_build_api_call(project_api_call, candidate.id)
            crefs = list(raw.iter_build_work_item_ids(capi))
            if crefs:
                wi_build = candidate
                wi_build_ids = [r.id for r in crefs]
                break
    if not wi_build_ids:
        broader = raw.iter_builds(
            project_api_call,
            search_criteria=raw.BuildSearchCriteria(top=200),
        )
        for candidate in broader:
            if any(candidate.id == b.id for b in builds):
                continue
            capi = raw.get_build_api_call(project_api_call, candidate.id)
            crefs = list(raw.iter_build_work_item_ids(capi))
            if crefs:
                wi_build = candidate
                wi_build_ids = [r.id for r in crefs]
                break
    return wi_build, wi_build_ids


def _exercise_build_tags(build_api_call: raw.ApiCall, rng: random.Random) -> None:
    """Add three tags, delete two, leave one — exercises the tag write cycle."""
    smoke_tag_a = f"pyado-smoke-a-{rng.randint(10000, 99999)}"
    smoke_tag_b = f"pyado-smoke-b-{rng.randint(10000, 99999)}"
    smoke_tag_c = f"pyado-smoke-c-{rng.randint(10000, 99999)}"
    console.print(f"  tags: {smoke_tag_a!r}  {smoke_tag_b!r}  {smoke_tag_c!r}")
    raw.post_build_tag(build_api_call, smoke_tag_a)
    raw.post_build_tag(build_api_call, smoke_tag_b)
    raw.post_build_tag(build_api_call, smoke_tag_c)
    list(raw.iter_build_tags(build_api_call))
    raw.delete_build_tag(build_api_call, smoke_tag_a)
    raw.delete_build_tag(build_api_call, smoke_tag_b)
    list(raw.iter_build_tags(build_api_call))


def _exercise_single_build(
    project_api_call: raw.ApiCall,
    build: raw.BuildDetails,
    builds: list[raw.BuildDetails],
    rng: random.Random,
) -> None:
    """Exercise all single-build endpoints: timeline, WI, artifacts, tags."""
    console.print(
        f"  build: #{build.id}  ({build.build_number})"
        f"  definition={build.definition.name!r} (id={build.definition.id})"
    )
    build_api_call = raw.get_build_api_call(project_api_call, build.id)
    raw.get_build_details(build_api_call)
    _take(raw.list_timeline_records(build_api_call), 30)
    build_wi_refs = _take(raw.list_build_work_item_ids(build_api_call), 10)
    build_wi_ids = [ref.id for ref in (build_wi_refs or [])]
    wi_build, wi_build_ids = _find_wi_build(
        project_api_call, build, builds, build_wi_ids
    )

    def _check_wi_to_build_via_commit(
        _b: raw.BuildDetails = wi_build,
        _ids: list[int] = wi_build_ids,
    ) -> list[raw.WorkItemRelation]:
        sample_wi_id = _ids[0]
        console.print(
            f"  build #{_b.id} linked to work items: {_ids}"
            f"  (verifying #{sample_wi_id} back-link)"
        )
        sample_wi_api = raw.get_work_item_api_call(project_api_call, sample_wi_id)
        item = raw.get_work_item(sample_wi_api, expand=raw.WorkItemExpand.RELATIONS)
        commit_links = [
            r
            for r in item.relations
            if r.rel == raw.WorkItemRelationType.ARTIFACT_LINK
            and raw.WorkItemArtifactUrlPrefix.COMMIT in str(r.url)
        ]
        if not commit_links:
            msg = (
                f"work item #{item.id} (returned by build #{_b.id}) "
                f"has no git-commit ArtifactLink; "
                f"relations: {[r.rel for r in item.relations]}"
            )
            raise AssertionError(msg)
        console.print(
            f"  work item #{item.id} has {len(commit_links)} commit ArtifactLink(s)"
        )
        return commit_links

    if wi_build_ids:
        _check_wi_to_build_via_commit()

    artifacts = list(raw.iter_build_artifacts(build_api_call))
    assert artifacts == raw.list_build_artifacts(build_api_call)
    downloadable = next(
        (a for a in artifacts if a.resource.download_url is not None),
        None,
    )
    if downloadable is not None:
        raw.get_build_artifact_bytes(build_api_call, downloadable)
    raw.list_build_tags(build_api_call)
    _exercise_build_tags(build_api_call, rng)


def _collect_builds(
    project_api_call: raw.ApiCall,
    rng: random.Random,
    defs: list[raw.PipelineDefinitionInfo],
    default_branch: str | None,
) -> list[raw.BuildDetails]:
    """Build variant list, run each query, and return deduplicated builds."""
    status_filters: list[raw.BuildStatus | None] = [
        None,
        raw.BuildStatus.COMPLETED,
        raw.BuildStatus.IN_PROGRESS,
        raw.BuildStatus.ALL,
        raw.BuildStatus.NOT_STARTED,
    ]
    rng.shuffle(status_filters)

    build_variants: list[tuple[str, raw.BuildSearchCriteria | None]] = [
        ("iter_builds [no filter]", None),
        ("iter_builds [top=1]", raw.BuildSearchCriteria(top=1)),
        ("iter_builds [top=5]", raw.BuildSearchCriteria(top=5)),
        (
            f"iter_builds [status={status_filters[0]}]",
            raw.BuildSearchCriteria(status_filter=status_filters[0], top=3),
        ),
        (
            f"iter_builds [status={status_filters[1]}]",
            raw.BuildSearchCriteria(status_filter=status_filters[1], top=3),
        ),
    ]
    if defs:
        build_variants.append(
            (
                f"iter_builds [definition_id={defs[0].id}]",
                raw.BuildSearchCriteria(definition_id=defs[0].id, top=3),
            )
        )
        if len(defs) > 1:
            build_variants.append(
                (
                    f"iter_builds [definition_id={defs[1].id}]",
                    raw.BuildSearchCriteria(definition_id=defs[1].id, top=3),
                )
            )
    if default_branch:
        build_variants.append(
            (
                f"iter_builds [branch_name={default_branch}]",
                raw.BuildSearchCriteria(branch_name=default_branch, top=3),
            )
        )

    rng.shuffle(build_variants)
    builds: list[raw.BuildDetails] = []
    for idx, (_, criteria) in enumerate(build_variants[:4]):
        if idx == 0:
            result = list(raw.iter_builds(project_api_call, search_criteria=criteria))
            assert result == raw.list_builds(project_api_call, search_criteria=criteria)
        else:
            result = _take(
                raw.list_builds(project_api_call, search_criteria=criteria), 5
            )
        if result:
            for item in result:
                if item not in builds:
                    builds.append(item)
    return builds


@pytest.fixture(scope="session")
def profile_result(
    token: str,
    org_url: str,
) -> tuple[raw.UserProfile | None, raw.ApiCall | None]:
    """Run profile tests and return (profile, vssps_api_call)."""
    return _test_profile(token, org_url)


@pytest.fixture(scope="session")
def reviewer_id(
    profile_result: tuple[raw.UserProfile | None, raw.ApiCall | None],
    project_api_call: raw.ApiCall,
) -> str | None:
    """Return a reviewer user ID, falling back to scanning PR history."""
    profile, _ = profile_result
    if profile and profile.id:
        return profile.id

    for status in ("completed", "abandoned", "active"):
        for pr in raw.iter_pull_requests(
            project_api_call,
            search_criteria=raw.PullRequestSearchCriteria(status=status),
        ):
            if pr.created_by and pr.created_by.id:
                return str(pr.created_by.id)
    return None


@pytest.fixture(scope="session")
def projects(
    org_api_call: raw.ApiCall,
) -> list[raw.ProjectInfo]:
    """Run project list test and return list of projects."""
    return raw.list_projects(org_api_call)


@pytest.fixture(scope="session")
def git_read(
    project_api_call: raw.ApiCall,
    rng: random.Random,
) -> tuple[raw.RepositoryInfo | None, raw.ApiCall | None, list[raw.GitCommitRef]]:
    """Run git read tests and return (repo, repo_api_call, commits)."""
    console.print("\n=== REPOSITORIES & GIT (read) ===")

    repos = list(raw.iter_repository_details(project_api_call))
    assert repos == raw.list_repository_details(project_api_call)
    if not repos:
        return None, None, []

    repo = repos[0]
    console.print(f"  repo: {repo.name}  id={repo.id}")

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
    for _, ref_filter in ref_variants[:3]:
        _take(raw.list_refs(repo_api_call, ref_filter), 10)

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
    for _, criteria in commit_variants[:3]:
        result = raw.get_repository_commits(repo_api_call, criteria)
        if result and not commits:
            commits = result

    if commits:
        head_sha_early = commits[0].commit_id
        raw.get_repository_commits(
            repo_api_call,
            raw.GitCommitSearchCriteria(
                item_version=head_sha_early,
                item_version_type=raw.VersionDescriptorType.COMMIT,
                top=3,
            ),
        )
        _read_file_content(repo_api_call, repo, commits, rng)
        # A5 — get_repository_item (metadata only, no content)
        short_branch = (repo.default_branch or "refs/heads/main").removeprefix(
            "refs/heads/"
        )
        raw.get_repository_item(
            repo_api_call, "/README.md", short_branch, raw.VersionDescriptorType.BRANCH
        )
        raw.get_repository_item(
            repo_api_call,
            "/README.md",
            head_sha_early,
            raw.VersionDescriptorType.COMMIT,
        )
        raw.get_repository_item(
            repo_api_call,
            "/nonexistent_file_smoke_test.txt",
            head_sha_early,
            raw.VersionDescriptorType.COMMIT,
        )

    _read_commit_diff(repo_api_call, commits, rng)

    return repo, repo_api_call, commits


@pytest.fixture(scope="session")
def builds_read(
    project_api_call: raw.ApiCall,
    rng: random.Random,
    git_read: tuple[
        raw.RepositoryInfo | None, raw.ApiCall | None, list[raw.GitCommitRef]
    ],
) -> tuple[list[raw.PipelineDefinitionInfo], list[raw.BuildDetails]]:
    """Run build read tests and return (defs, builds)."""
    repo, _, _ = git_read
    default_branch = repo.default_branch if repo else None
    console.print("\n=== PIPELINE DEFINITIONS & BUILDS (read) ===")

    defs = _take(raw.list_pipeline_definitions(project_api_call), 10)
    if defs:
        name_fragment: str | None = rng.choice([None, defs[0].name[:3], defs[0].name])
        _take(
            raw.iter_pipeline_definitions(project_api_call, name_filter=name_fragment),
            5,
        )

    builds = _collect_builds(project_api_call, rng, defs or [], default_branch)

    if builds:
        _exercise_single_build(project_api_call, builds[0], builds, rng)

    # iter_works_items_between_builds requires two distinct build IDs
    if len(builds) >= 2:
        older_id = min(builds[0].id, builds[1].id)
        newer_id = max(builds[0].id, builds[1].id)
        wis = list(
            raw.iter_work_items_between_builds(
                project_api_call, older_id, newer_id, top=10
            )
        )
        assert wis == raw.list_work_items_between_builds(
            project_api_call, older_id, newer_id, top=10
        )

    return defs or [], builds


@pytest.fixture(scope="session")
def var_groups(
    project_api_call: raw.ApiCall,
) -> list[raw.VariableGroupInfo]:
    """Run variable group list test and return groups."""
    console.print("\n=== VARIABLE GROUPS (read) ===")
    groups = list(raw.iter_variable_group_details(project_api_call))
    assert groups == raw.list_variable_group_details(project_api_call)
    return groups or []


@pytest.fixture(scope="session")
def pipelines(
    project_api_call: raw.ApiCall,
    rng: random.Random,
) -> list[raw.PipelineInfo]:
    """Run pipeline read tests and return list of pipelines."""
    console.print("\n=== PIPELINES (read) ===")

    order_variants: list[str | None] = [None, "name asc", "name desc"]
    rng.shuffle(order_variants)

    result_pipelines: list[raw.PipelineInfo] = []
    for idx, order in enumerate(order_variants[:2]):
        if idx == 0:
            result = list(raw.iter_pipelines(project_api_call, order_by=order))
            assert result == raw.list_pipelines(project_api_call, order_by=order)
        else:
            result = raw.list_pipelines(project_api_call, order_by=order)
        if result and not result_pipelines:
            result_pipelines = result

    if result_pipelines:
        pipeline = result_pipelines[0]
        raw.get_pipeline(project_api_call, pipeline.id)
        # get_pipeline with pipeline_version parameter
        raw.get_pipeline(
            project_api_call, pipeline.id, pipeline_version=pipeline.revision
        )
        _take(raw.iter_pipeline_runs(project_api_call, pipeline.id), 5)
        runs = raw.list_pipeline_runs(project_api_call, pipeline.id)
        if runs:
            newest = runs[0]
            raw.get_pipeline_run(project_api_call, pipeline.id, newest.id)

    return result_pipelines
