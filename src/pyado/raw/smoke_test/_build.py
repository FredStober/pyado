"""Smoke tests for build and pipeline-definition endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import random

from pyado import raw
from pyado.raw.smoke_test._runner import _DIM, _RESET, _skip, _take, console, run


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
    return wi_build, wi_build_ids


def _exercise_build_tags(build_api_call: raw.ApiCall, rng: random.Random) -> None:
    """Add three tags, delete two, leave one — exercises the tag write cycle."""
    smoke_tag_a = f"pyado-smoke-a-{rng.randint(10000, 99999)}"
    smoke_tag_b = f"pyado-smoke-b-{rng.randint(10000, 99999)}"
    smoke_tag_c = f"pyado-smoke-c-{rng.randint(10000, 99999)}"
    console.print(
        f"  {_DIM}tags: {smoke_tag_a!r}  {smoke_tag_b!r}  {smoke_tag_c!r}{_RESET}"
    )
    tag_a = run(
        "post_build_tag [tag A]",
        lambda t=smoke_tag_a: raw.post_build_tag(build_api_call, t),
    )
    tag_b = run(
        "post_build_tag [tag B]",
        lambda t=smoke_tag_b: raw.post_build_tag(build_api_call, t),
    )
    tag_c = run(
        "post_build_tag [tag C]",
        lambda t=smoke_tag_c: raw.post_build_tag(build_api_call, t),
    )
    if tag_a is not None and tag_b is not None and tag_c is not None:
        run(
            "iter_build_tags [after add 3]",
            lambda: list(raw.iter_build_tags(build_api_call)),
        )
        run(
            "delete_build_tag [tag A]",
            lambda t=smoke_tag_a: raw.delete_build_tag(build_api_call, t),
        )
        run(
            "delete_build_tag [tag B]",
            lambda t=smoke_tag_b: raw.delete_build_tag(build_api_call, t),
        )
        run(
            "iter_build_tags [tag C remains]",
            lambda: list(raw.iter_build_tags(build_api_call)),
        )
    elif tag_a is not None:
        run(
            "delete_build_tag [tag A only]",
            lambda t=smoke_tag_a: raw.delete_build_tag(build_api_call, t),
        )
        _skip("delete_build_tag [tag B]", "post_build_tag B failed")
        _skip("iter_build_tags [tag C remains]", "post_build_tag failed")
    else:
        _skip("iter_build_tags [after add 3]", "post_build_tag failed")
        _skip("delete_build_tag [tag A]", "post_build_tag A failed")
        _skip("delete_build_tag [tag B]", "post_build_tag B failed")
        _skip("iter_build_tags [tag C remains]", "post_build_tag failed")


def _exercise_single_build(
    project_api_call: raw.ApiCall,
    build: raw.BuildDetails,
    builds: list[raw.BuildDetails],
    rng: random.Random,
) -> None:
    """Exercise all single-build endpoints: timeline, WI, artifacts, tags."""
    console.print(
        f"  {_DIM}build: #{build.id}  ({build.build_number})"
        f"  definition={build.definition.name!r} (id={build.definition.id}){_RESET}"
    )
    build_api_call = raw.get_build_api_call(project_api_call, build.id)
    run("get_build_details", lambda: raw.get_build_details(build_api_call))
    run(
        "iter_timeline_records",
        lambda: _take(raw.list_timeline_records(build_api_call), 30),
    )
    build_wi_refs = run(
        "iter_build_work_item_ids [raw]",
        lambda: _take(raw.list_build_work_item_ids(build_api_call), 10),
    )
    build_wi_ids = [ref.id for ref in (build_wi_refs or [])]
    wi_build, wi_build_ids = _find_wi_build(
        project_api_call, build, builds, build_wi_ids
    )

    if not wi_build_ids:
        _skip(
            "get_work_item [verify WI→commit back-link]",
            f"none of the {len(builds)} collected builds have associated "
            "work items — need builds triggered from commits with #<id>",
        )
    else:

        def _check_wi_to_build_via_commit(
            _b: raw.BuildDetails = wi_build,
            _ids: list[int] = wi_build_ids,
        ) -> list:
            sample_wi_id = _ids[0]
            console.print(
                f"  {_DIM}build #{_b.id} linked to work items: {_ids}"
                f"  (verifying #{sample_wi_id} back-link){_RESET}"
            )
            sample_wi_api = raw.get_work_item_api_call(project_api_call, sample_wi_id)
            item = raw.get_work_item(sample_wi_api, expand=raw.WorkItemExpand.RELATIONS)
            commit_links = [
                r
                for r in item.relations
                if r.rel == "ArtifactLink" and "vstfs:///Git/Commit" in str(r.url)
            ]
            if not commit_links:
                msg = (
                    f"work item #{item.id} (returned by build #{_b.id}) "
                    f"has no git-commit ArtifactLink; "
                    f"relations: {[r.rel for r in item.relations]}"
                )
                raise AssertionError(msg)
            console.print(
                f"  {_DIM}work item #{item.id} has {len(commit_links)} "
                f"commit ArtifactLink(s){_RESET}"
            )
            return commit_links

        run(
            "get_work_item [verify WI→commit back-link]",
            _check_wi_to_build_via_commit,
        )

    artifacts = run(
        "iter_build_artifacts",
        lambda: _take(raw.list_build_artifacts(build_api_call), 10),
    )
    downloadable = next(
        (a for a in (artifacts or []) if a.resource.download_url is not None),
        None,
    )
    if downloadable is not None:
        run(
            f"get_build_artifact_bytes [name={downloadable.name!r}]",
            lambda a=downloadable: raw.get_build_artifact_bytes(build_api_call, a),
        )
    else:
        _skip(
            "get_build_artifact_bytes",
            "no artifacts with a downloadUrl found on this build",
        )
    run(
        "list_build_tags",
        lambda: raw.list_build_tags(build_api_call),
    )
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
        "completed",
        "inProgress",
        "all",
        "notStarted",
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
    for label, criteria in build_variants[:4]:
        result = run(
            label,
            lambda sc=criteria: _take(
                raw.list_builds(project_api_call, search_criteria=sc), 5
            ),
        )
        if result:
            for item in result:
                if item not in builds:
                    builds.append(item)
    return builds


def _test_builds_read(
    project_api_call: raw.ApiCall,
    rng: random.Random,
    default_branch: str | None = None,
) -> tuple[list[raw.PipelineDefinitionInfo], list[raw.BuildDetails]]:
    console.print("\n=== PIPELINE DEFINITIONS & BUILDS (read) ===")

    defs = run(
        "iter_pipeline_definitions [no filter]",
        lambda: _take(raw.list_pipeline_definitions(project_api_call), 10),
    )
    if defs:
        name_fragment: str | None = rng.choice([None, defs[0].name[:3], defs[0].name])
        run(
            f"iter_pipeline_definitions [name={name_fragment!r}]",
            lambda q=name_fragment: _take(
                raw.iter_pipeline_definitions(project_api_call, name_filter=q), 5
            ),
        )

    builds = _collect_builds(project_api_call, rng, defs or [], default_branch)

    if builds:
        _exercise_single_build(project_api_call, builds[0], builds, rng)
    else:
        for label in (
            "get_build_details",
            "iter_timeline_records",
            "iter_build_work_item_ids [raw]",
            "iter_build_artifacts",
            "get_build_artifact_bytes",
            "iter_build_tags",
            "post_build_tag [tag A]",
            "post_build_tag [tag B]",
            "post_build_tag [tag C]",
            "iter_build_tags [after add 3]",
            "delete_build_tag [tag A]",
            "delete_build_tag [tag B]",
            "iter_build_tags [tag C remains]",
        ):
            _skip(label, "no build found")

    # iter_works_items_between_builds requires two distinct build IDs
    if len(builds) >= 2:
        older_id = min(builds[0].id, builds[1].id)
        newer_id = max(builds[0].id, builds[1].id)
        run(
            "iter_work_items_between_builds",
            lambda f=older_id, t=newer_id: _take(
                raw.list_work_items_between_builds(project_api_call, f, t, top=10), 10
            ),
        )
    else:
        _skip("iter_work_items_between_builds", "fewer than 2 builds found")

    return defs or [], builds


def _test_build_logs_read(
    project_api_call: raw.ApiCall,
    builds: list[raw.BuildDetails],
) -> None:
    console.print("\n=== BUILD LOGS (read) ===")
    if not builds:
        for label in ("iter_build_logs", "get_build_log"):
            _skip(label, "no builds found")
        return

    build = builds[0]
    build_api_call = raw.get_build_api_call(project_api_call, build.id)
    logs = run("list_build_logs", lambda: raw.list_build_logs(build_api_call))
    if logs:
        run(
            f"get_build_log [id={logs[0].id}]",
            lambda lid=logs[0].id: raw.get_build_log(build_api_call, lid),
        )
    else:
        _skip("get_build_log", "no build logs found")
