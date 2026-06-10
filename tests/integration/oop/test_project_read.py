"""Integration tests for Project OOP class (read)."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado.oop import (
    BasePolicyModel,
    BuildPolicy,
    CommentRequirementsPolicy,
    CommitAuthorEmailPolicy,
    Dashboard,
    FileNamePolicy,
    FileSizeRestrictionPolicy,
    GitRepositoryPolicy,
    MergeStrategyPolicy,
    MinimumReviewersPolicy,
    PathLengthPolicy,
    PolicyConfiguration,
    Project,
    ProjectSettings,
    RepoPolicyScope,
    RequiredReviewersPolicy,
    ReservedNamesPolicy,
    SearchBranchesPolicy,
    StatusPolicy,
    Wiki,
    WorkItemLinkingPolicy,
    WorkItemType,
)
from pyado.raw import PipelineApprovalStatus
from tests.integration.raw._support import _take, console


def test_project_read(proj: Project) -> None:
    """Exercise Project properties, pipelines, boards, repos, and team lookups."""
    console.print("\n=== Project (properties & read) ===")
    _ = proj.name
    _ = proj.id
    _ = proj.info
    _ = proj.api_call
    _ = proj.org
    proj.refresh()
    _take(proj.pipelines.iter_pipelines(), 5)
    proj.pipelines.list_pipelines()
    proj.boards.get_query_tree()
    proj.boards.get_iteration_node(depth=2)
    proj.boards.get_area_node(depth=2)
    _take(proj.pipelines.iter_approvals(), 3)
    proj.pipelines.list_approvals()
    proj.pipelines.list_builds()
    proj.repos.list_repositories()
    proj.boards.list_teams()
    proj.pipelines.library.list_variable_groups()
    repos = proj.repos.list_repositories()
    if repos:
        proj.repos.get_repository_by_id(repos[0].id)
    teams = proj.boards.list_teams()
    if teams:
        proj.boards.get_team_by_id(teams[0].id)
        _take(proj.boards.iter_team_sprint_iterations(teams[0].name), 5)
        proj.boards.list_team_sprint_iterations(teams[0].name)
    approvals = proj.pipelines.list_approvals(PipelineApprovalStatus.PENDING)
    if approvals:
        approval_id = str(approvals[0].id)
        proj.pipelines.approve(approval_id, comment="oop-smoke")
        if len(approvals) >= 2:
            reject_id = str(approvals[1].id)
            proj.pipelines.reject(reject_id, comment="oop-smoke")


def test_project_active_prs(proj: Project) -> None:
    """Exercise Project.repos.iter_active_prs() and boards.list_work_items()."""
    console.print("\n=== Project.repos.iter_active_prs() ===")
    _take(proj.repos.iter_active_prs(), 5)
    proj.repos.list_active_prs()
    proj.repos.list_pull_requests()
    wiql = (
        "SELECT [System.Id] FROM WorkItems "
        "WHERE [System.TeamProject] = @project "
        "ORDER BY [System.Id] DESC"
    )
    proj.boards.list_work_items(wiql)


def test_project_settings(proj: Project) -> None:
    """Exercise ProjectSettings: policy configs, policy types, process info."""
    console.print("\n=== Project Settings ===")
    settings: ProjectSettings = proj.settings
    settings.get_project_info()
    configs = settings.list_policy_configurations()
    _take(settings.iter_policy_configurations(), 5)
    policy_types = settings.list_policy_types()
    _take(settings.iter_policy_types(), 3)
    if policy_types:
        settings.get_policy_type(policy_types[0].id)
    if configs:
        pc: PolicyConfiguration = configs[0]
        _ = pc.is_enabled
        _ = pc.is_blocking
        _ = pc.revision
        settings.get_policy_configuration(pc.id)
    settings.get_process_info()


def test_wikis_and_dashboards(proj: Project) -> None:
    """Exercise Project wiki/dashboard methods and Team dashboards."""
    console.print("\n=== Wikis & Dashboards ===")
    wikis = _take(proj.iter_wikis(), 3)
    proj.list_wikis()
    if wikis:
        wiki: Wiki = wikis[0]
        wiki.list_pages()

    dashboards = proj.list_dashboards()
    _take(proj.iter_dashboards(), 5)
    if dashboards:
        db: Dashboard = dashboards[0]
        _ = db.team
        _ = db.widgets

    proj.get_default_team()
    teams = proj.boards.list_teams()
    if teams:
        team = teams[0]
        _take(team.iter_dashboards(), 3)
        team_dashboards = team.list_dashboards()
        if team_dashboards:
            db_id = team_dashboards[0].id
            team.get_dashboard(db_id)


def test_policy_type_models(proj: Project) -> None:
    """Exercise typed OOP policy model round-trips via from_info()."""
    console.print("\n=== Typed policy models ===")
    type_map: dict[object, type[BasePolicyModel]] = {
        MinimumReviewersPolicy.POLICY_TYPE_ID: MinimumReviewersPolicy,
        CommentRequirementsPolicy.POLICY_TYPE_ID: CommentRequirementsPolicy,
        WorkItemLinkingPolicy.POLICY_TYPE_ID: WorkItemLinkingPolicy,
        GitRepositoryPolicy.POLICY_TYPE_ID: GitRepositoryPolicy,
        ReservedNamesPolicy.POLICY_TYPE_ID: ReservedNamesPolicy,
        PathLengthPolicy.POLICY_TYPE_ID: PathLengthPolicy,
        FileSizeRestrictionPolicy.POLICY_TYPE_ID: FileSizeRestrictionPolicy,
        FileNamePolicy.POLICY_TYPE_ID: FileNamePolicy,
        MergeStrategyPolicy.POLICY_TYPE_ID: MergeStrategyPolicy,
        CommitAuthorEmailPolicy.POLICY_TYPE_ID: CommitAuthorEmailPolicy,
        BuildPolicy.POLICY_TYPE_ID: BuildPolicy,
        SearchBranchesPolicy.POLICY_TYPE_ID: SearchBranchesPolicy,
        RequiredReviewersPolicy.POLICY_TYPE_ID: RequiredReviewersPolicy,
        StatusPolicy.POLICY_TYPE_ID: StatusPolicy,
    }
    configs = proj.settings.list_policy_configurations()
    for config in configs:
        cls = type_map.get(config.type.id)
        if cls is not None:
            cls.from_info(config.info)
    _ = RepoPolicyScope(repository_id=None)


def test_work_item_types(proj: Project) -> None:
    """Exercise ProjectBoards work item type methods and WorkItemType class."""
    console.print("\n=== Work Item Types ===")
    wits = _take(proj.boards.iter_work_item_types(), 3)
    proj.boards.list_work_item_types()
    _take(proj.boards.iter_work_item_type_categories(), 5)
    proj.boards.list_work_item_type_categories()
    if wits:
        wit: WorkItemType = wits[0]
        _ = wit.reference_name
        _ = wit.color
        _ = wit.icon
        _take(wit.iter_states(), 5)
        wit.list_states()
        _take(wit.iter_fields(), 5)
        wit.list_fields()
        proj.boards.get_work_item_type(wit.name)
