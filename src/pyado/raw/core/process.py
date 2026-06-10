"""Azure DevOps work process API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from enum import StrEnum
from typing import TypeAlias
from uuid import UUID

from pydantic import Field

from pyado.raw._core import AdoBaseModel, ApiCall
from pyado.raw.boards.work_item import WorkItemFieldType, WorkItemStateCategory

__all__ = [
    "ProcessBehaviorCreateRequest",
    "ProcessBehaviorField",
    "ProcessBehaviorInfo",
    "ProcessBehaviorUpdateRequest",
    "ProcessCreateRequest",
    "ProcessDetail",
    "ProcessId",
    "ProcessType",
    "ProcessUpdateRequest",
    "ProcessWITInfo",
    "ProcessWorkItemField",
    "ProcessWorkItemRule",
    "ProcessWorkItemState",
    "ProcessWorkItemTypeCreateRequest",
    "ProcessWorkItemTypeFieldAddRequest",
    "ProcessWorkItemTypeFieldUpdateRequest",
    "ProcessWorkItemTypeRuleAction",
    "ProcessWorkItemTypeRuleCondition",
    "ProcessWorkItemTypeRuleCreateRequest",
    "ProcessWorkItemTypeRuleId",
    "ProcessWorkItemTypeRuleUpdateRequest",
    "ProcessWorkItemTypeStateCreateRequest",
    "ProcessWorkItemTypeStateId",
    "ProcessWorkItemTypeStateUpdateRequest",
    "ProcessWorkItemTypeUpdateRequest",
    "ProjectFieldInfo",
    "delete_behavior",
    "delete_process",
    "delete_work_item_type",
    "delete_work_item_type_field",
    "delete_work_item_type_rule",
    "delete_work_item_type_state",
    "get_process",
    "get_process_info",
    "iter_processes",
    "list_processes",
    "patch_behavior",
    "patch_process",
    "patch_work_item_type",
    "patch_work_item_type_field",
    "patch_work_item_type_rule",
    "patch_work_item_type_state",
    "post_behavior",
    "post_process",
    "post_work_item_type",
    "post_work_item_type_field",
    "post_work_item_type_rule",
    "post_work_item_type_state",
]

ProcessId: TypeAlias = UUID


class ProcessType(StrEnum):
    """The origin type of an ADO work process template.

    ``SYSTEM`` processes are the built-in templates shipped by Microsoft
    (Agile, Scrum, CMMI, Basic).  ``INHERITED`` processes are copies
    derived from a system process that can be customised per organisation.
    """

    SYSTEM = "system"
    INHERITED = "inherited"


_PROCESS_API_VERSION = "7.1"


class ProcessWorkItemState(AdoBaseModel):
    """A work item type state as returned by the process states API."""

    name: str
    state_category: WorkItemStateCategory | None = None
    id: str | None = None
    color: str | None = None
    url: str | None = None


class ProcessWorkItemField(AdoBaseModel):
    """A field entry on a work item type in a process."""

    name: str | None = None
    reference_name: str | None = None
    field_type: WorkItemFieldType | None = None
    is_required: bool = False
    is_read_only: bool = False
    default_value: str | None = None
    help_text: str | None = None
    allowed_values: list[str] | None = None


class ProcessWorkItemTypeRuleCondition(AdoBaseModel):
    """A condition clause in a work item type rule."""

    condition_type: str | None = None
    field: str | None = None
    value: str | None = None


class ProcessWorkItemTypeRuleAction(AdoBaseModel):
    """An action clause in a work item type rule."""

    action_type: str | None = None
    target_field: str | None = None
    value: str | None = None


class ProcessWorkItemRule(AdoBaseModel):
    """A workflow rule on a work item type in a process."""

    id: str | None = None
    name: str | None = None
    is_system: bool = False
    is_disabled: bool = False
    conditions: list[ProcessWorkItemTypeRuleCondition] = Field(default_factory=list)
    actions: list[ProcessWorkItemTypeRuleAction] = Field(default_factory=list)


class ProcessBehaviorField(AdoBaseModel):
    """A field reference on a process behavior."""

    name: str | None = None
    reference_name: str | None = None
    default_value: str | None = None


class ProcessWITInfo(AdoBaseModel):
    """A work item type as returned by the process API."""

    reference_name: str
    name: str
    description: str = ""
    color: str | None = None
    icon: str | None = None
    is_disabled: bool = False
    states: list[ProcessWorkItemState] = Field(default_factory=list)
    rules: list[ProcessWorkItemRule] = Field(default_factory=list)
    fields: list[ProcessWorkItemField] = Field(default_factory=list)


class ProcessBehaviorInfo(AdoBaseModel):
    """A behavior (portfolio backlog level) defined in a process."""

    reference_name: str
    name: str
    color: str | None = None
    description: str = ""
    rank: int | None = None
    fields: list[ProcessBehaviorField] = Field(default_factory=list)


class ProjectFieldInfo(AdoBaseModel):
    """A field definition at project scope."""

    name: str
    reference_name: str
    field_type: WorkItemFieldType | None = None
    read_only: bool = False
    can_sort_by: bool = False
    is_queryable: bool = False
    is_identity: bool = False


class ProcessDetail(AdoBaseModel):
    """Composite process detail gathered from all process sub-resources.

    Attributes:
        type_id: Process template UUID.
        name: Human-readable process name.
        description: Optional process description.
        reference_name: Unique reference name for the process.
        parent_process_type_id: UUID of the parent (system) process this
            was derived from; ``None`` for system processes.
        is_enabled: Whether the process is enabled in the organisation.
        customization_type: Customisation origin (e.g. ``"system"`` or
            ``"inherited"``).
        is_default: Whether this is the default process for the org.
        work_item_types: WIT definitions with states, rules, and fields.
        behaviors: Portfolio backlog behaviors in this process.
        project_fields: All field definitions registered in the project.
    """

    type_id: ProcessId
    name: str
    description: str = ""
    reference_name: str | None = None
    parent_process_type_id: str | None = None
    is_enabled: bool = True
    customization_type: ProcessType | None = None
    is_default: bool = False
    work_item_types: list[ProcessWITInfo] = Field(default_factory=list)
    behaviors: list[ProcessBehaviorInfo] = Field(default_factory=list)
    project_fields: list[ProjectFieldInfo] = Field(default_factory=list)


ProcessWorkItemTypeStateId: TypeAlias = str
ProcessWorkItemTypeRuleId: TypeAlias = str


class ProcessCreateRequest(AdoBaseModel):
    """Request body for creating an inherited process template."""

    name: str
    parent_process_type_id: ProcessId
    description: str | None = None
    reference_name: str | None = None


class ProcessUpdateRequest(AdoBaseModel):
    """Request body for updating a process template."""

    name: str | None = None
    description: str | None = None
    is_default: bool | None = None
    is_enabled: bool | None = None


class ProcessWorkItemTypeCreateRequest(AdoBaseModel):
    """Request body for creating a work item type in a process."""

    name: str
    reference_name: str | None = None
    description: str | None = None
    color: str | None = None
    icon: str | None = None


class ProcessWorkItemTypeUpdateRequest(AdoBaseModel):
    """Request body for updating a work item type in a process."""

    name: str | None = None
    description: str | None = None
    color: str | None = None
    icon: str | None = None
    is_disabled: bool | None = None


class ProcessWorkItemTypeStateCreateRequest(AdoBaseModel):
    """Request body for creating a state on a work item type."""

    name: str
    color: str
    state_category: WorkItemStateCategory | None = None
    order: int | None = None


class ProcessWorkItemTypeStateUpdateRequest(AdoBaseModel):
    """Request body for updating a state on a work item type."""

    name: str | None = None
    color: str | None = None
    state_category: WorkItemStateCategory | None = None
    order: int | None = None


class ProcessWorkItemTypeFieldAddRequest(AdoBaseModel):
    """Request body for adding a field to a work item type in a process."""

    reference_name: str
    default_value: str | None = None
    is_required: bool = False
    is_read_only: bool = False
    allowed_values: list[str] = Field(default_factory=list)


class ProcessWorkItemTypeFieldUpdateRequest(AdoBaseModel):
    """Request body for updating a field on a work item type in a process."""

    default_value: str | None = None
    is_required: bool | None = None
    is_read_only: bool | None = None
    allowed_values: list[str] | None = None


class ProcessWorkItemTypeRuleCreateRequest(AdoBaseModel):
    """Request body for creating a rule on a work item type."""

    name: str
    conditions: list[ProcessWorkItemTypeRuleCondition] = Field(default_factory=list)
    actions: list[ProcessWorkItemTypeRuleAction] = Field(default_factory=list)
    is_disabled: bool = False


class ProcessWorkItemTypeRuleUpdateRequest(AdoBaseModel):
    """Request body for updating a rule on a work item type."""

    name: str | None = None
    conditions: list[ProcessWorkItemTypeRuleCondition] | None = None
    actions: list[ProcessWorkItemTypeRuleAction] | None = None
    is_disabled: bool | None = None


class ProcessBehaviorCreateRequest(AdoBaseModel):
    """Request body for creating a behavior in a process."""

    name: str
    reference_name: str | None = None
    color: str | None = None
    description: str | None = None


class ProcessBehaviorUpdateRequest(AdoBaseModel):
    """Request body for updating a behavior in a process."""

    name: str | None = None
    color: str | None = None
    description: str | None = None


def _fetch_wit_sub_resources(
    org_api_call: ApiCall,
    process_id: UUID,
    wit_ref: str,
) -> tuple[
    list[ProcessWorkItemState], list[ProcessWorkItemRule], list[ProcessWorkItemField]
]:
    """Fetch states, rules, and fields for one WIT in a process.

    Returns:
        Tuple of (states, rules, fields) as typed model lists.
    """
    base = org_api_call.build_call(
        "work",
        "processes",
        process_id,
        "workItemTypes",
        wit_ref,
    )
    states_result = base.get("states", version=_PROCESS_API_VERSION)
    states = [
        ProcessWorkItemState.model_validate(item)
        for item in states_result.get("value", [])
    ]

    rules_result = base.get("rules", version=_PROCESS_API_VERSION)
    rules = [
        ProcessWorkItemRule.model_validate(item)
        for item in rules_result.get("value", [])
    ]

    fields_result = base.get("fields", version=_PROCESS_API_VERSION)
    fields = [
        ProcessWorkItemField.model_validate(item)
        for item in fields_result.get("value", [])
    ]

    return states, rules, fields


def get_process_info(
    org_api_call: ApiCall,
    project_api_call: ApiCall,
    template_type_id: UUID,
) -> ProcessDetail:
    """Gather composite process information for a project.

    Calls five ADO endpoints in sequence:

    1. ``GET /_apis/work/processes/{templateTypeId}`` — process detail
    2. ``GET /_apis/work/processes/{id}/workitemtypes`` — WITs in process
    3. Per WIT: states, rules, and fields
    4. ``GET /_apis/work/processes/{id}/behaviors``
    5. ``GET /{project}/_apis/wit/fields`` — all project fields

    Args:
        org_api_call: Organisation-level ADO API call.
        project_api_call: Project-level ADO API call.
        template_type_id: UUID of the process template (available via
            ``ProjectInfo.capabilities.process_template.template_type_id``).

    Returns:
        ProcessDetail with all sub-resources populated.
    """
    # 1. Process detail
    process_raw = org_api_call.get(
        "work",
        "processes",
        template_type_id,
        version=_PROCESS_API_VERSION,
    )
    detail = ProcessDetail.model_validate(process_raw)

    # 2. Work item types in this process
    wits_raw = org_api_call.get(
        "work",
        "processes",
        template_type_id,
        "workItemTypes",
        version=_PROCESS_API_VERSION,
    )
    wit_items: list[ProcessWITInfo] = []
    for wit_raw in wits_raw.get("value", []):
        wit = ProcessWITInfo.model_validate(wit_raw)
        # 3. Per-WIT: states, rules, fields
        states, rules, fields = _fetch_wit_sub_resources(
            org_api_call, template_type_id, wit.reference_name
        )
        wit.states = states
        wit.rules = rules
        wit.fields = fields
        wit_items.append(wit)
    detail.work_item_types = wit_items

    # 4. Behaviors
    behaviors_raw = org_api_call.get(
        "work",
        "processes",
        template_type_id,
        "behaviors",
        version=_PROCESS_API_VERSION,
    )
    detail.behaviors = [
        ProcessBehaviorInfo.model_validate(item)
        for item in behaviors_raw.get("value", [])
    ]

    # 5. All project-level fields
    fields_raw = project_api_call.get("wit", "fields", version=_PROCESS_API_VERSION)
    detail.project_fields = [
        ProjectFieldInfo.model_validate(item) for item in fields_raw.get("value", [])
    ]

    return detail


def get_process(
    org_api_call: ApiCall,
    process_id: ProcessId,
) -> ProcessDetail:
    """Fetch a single process template by ID without sub-resources.

    Args:
        org_api_call: Organisation-level ADO API call.
        process_id: UUID of the process template.

    Returns:
        ProcessDetail for the requested process (WIT lists are empty).
    """
    result = org_api_call.get(
        "work",
        "processes",
        process_id,
        version=_PROCESS_API_VERSION,
    )
    return ProcessDetail.model_validate(result)


def iter_processes(org_api_call: ApiCall) -> Iterator[ProcessDetail]:
    """Iterate over all work process templates in the organisation.

    Args:
        org_api_call: Organisation-level ADO API call.

    Yields:
        ProcessDetail for each process template (WIT lists are empty).
    """
    result = org_api_call.get(
        "work",
        "processes",
        version=_PROCESS_API_VERSION,
    )
    for item in result.get("value", []):
        yield ProcessDetail.model_validate(item)


def list_processes(org_api_call: ApiCall) -> list[ProcessDetail]:
    """Return all work process templates in the organisation as a list.

    Args:
        org_api_call: Organisation-level ADO API call.

    Returns:
        List of ProcessDetail for each process template.
    """
    return list(iter_processes(org_api_call))


def post_process(
    org_api_call: ApiCall,
    request: ProcessCreateRequest,
) -> ProcessDetail:
    """Create a new inherited process template.

    Args:
        org_api_call: Organisation-level ADO API call.
        request: Create request specifying name and parent process.

    Returns:
        ProcessDetail for the newly created process.
    """
    result = org_api_call.post(
        "work",
        "processes",
        version=_PROCESS_API_VERSION,
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return ProcessDetail.model_validate(result)


def patch_process(
    org_api_call: ApiCall,
    process_id: ProcessId,
    request: ProcessUpdateRequest,
) -> ProcessDetail:
    """Update an existing process template.

    Args:
        org_api_call: Organisation-level ADO API call.
        process_id: UUID of the process template to update.
        request: Update request with fields to change.

    Returns:
        Updated ProcessDetail.
    """
    result = org_api_call.patch(
        "work",
        "processes",
        process_id,
        version=_PROCESS_API_VERSION,
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return ProcessDetail.model_validate(result)


def delete_process(
    org_api_call: ApiCall,
    process_id: ProcessId,
) -> None:
    """Delete a process template from the organisation.

    Args:
        org_api_call: Organisation-level ADO API call.
        process_id: UUID of the process template to delete.
    """
    org_api_call.delete(
        "work",
        "processes",
        process_id,
        version=_PROCESS_API_VERSION,
    )


def post_work_item_type(
    org_api_call: ApiCall,
    process_id: ProcessId,
    request: ProcessWorkItemTypeCreateRequest,
) -> ProcessWITInfo:
    """Create a work item type in a process.

    Args:
        org_api_call: Organisation-level ADO API call.
        process_id: UUID of the process template.
        request: Create request for the new work item type.

    Returns:
        ProcessWITInfo for the newly created work item type.
    """
    result = org_api_call.post(
        "work",
        "processes",
        process_id,
        "workItemTypes",
        version=_PROCESS_API_VERSION,
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return ProcessWITInfo.model_validate(result)


def patch_work_item_type(
    org_api_call: ApiCall,
    process_id: ProcessId,
    work_item_type_ref: str,
    request: ProcessWorkItemTypeUpdateRequest,
) -> ProcessWITInfo:
    """Update a work item type in a process.

    Args:
        org_api_call: Organisation-level ADO API call.
        process_id: UUID of the process template.
        work_item_type_ref: Reference name of the work item type
            (e.g. ``"Custom.MyType"``).
        request: Update request with fields to change.

    Returns:
        Updated ProcessWITInfo.
    """
    result = org_api_call.patch(
        "work",
        "processes",
        process_id,
        "workItemTypes",
        work_item_type_ref,
        version=_PROCESS_API_VERSION,
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return ProcessWITInfo.model_validate(result)


def delete_work_item_type(
    org_api_call: ApiCall,
    process_id: ProcessId,
    work_item_type_ref: str,
) -> None:
    """Delete a work item type from a process.

    Args:
        org_api_call: Organisation-level ADO API call.
        process_id: UUID of the process template.
        work_item_type_ref: Reference name of the work item type to delete.
    """
    org_api_call.delete(
        "work",
        "processes",
        process_id,
        "workItemTypes",
        work_item_type_ref,
        version=_PROCESS_API_VERSION,
    )


def post_work_item_type_state(
    org_api_call: ApiCall,
    process_id: ProcessId,
    work_item_type_ref: str,
    request: ProcessWorkItemTypeStateCreateRequest,
) -> ProcessWorkItemState:
    """Create a state on a work item type in a process.

    Args:
        org_api_call: Organisation-level ADO API call.
        process_id: UUID of the process template.
        work_item_type_ref: Reference name of the work item type.
        request: Create request for the new state.

    Returns:
        ProcessWorkItemState for the newly created state.
    """
    result = org_api_call.post(
        "work",
        "processes",
        process_id,
        "workItemTypes",
        work_item_type_ref,
        "states",
        version=_PROCESS_API_VERSION,
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return ProcessWorkItemState.model_validate(result)


def patch_work_item_type_state(
    org_api_call: ApiCall,
    process_id: ProcessId,
    work_item_type_ref: str,
    state_id: ProcessWorkItemTypeStateId,
    request: ProcessWorkItemTypeStateUpdateRequest,
) -> ProcessWorkItemState:
    """Update a state on a work item type in a process.

    Args:
        org_api_call: Organisation-level ADO API call.
        process_id: UUID of the process template.
        work_item_type_ref: Reference name of the work item type.
        state_id: ID of the state to update.
        request: Update request with fields to change.

    Returns:
        Updated ProcessWorkItemState.
    """
    result = org_api_call.patch(
        "work",
        "processes",
        process_id,
        "workItemTypes",
        work_item_type_ref,
        "states",
        state_id,
        version=_PROCESS_API_VERSION,
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return ProcessWorkItemState.model_validate(result)


def delete_work_item_type_state(
    org_api_call: ApiCall,
    process_id: ProcessId,
    work_item_type_ref: str,
    state_id: ProcessWorkItemTypeStateId,
) -> None:
    """Delete a state from a work item type in a process.

    Args:
        org_api_call: Organisation-level ADO API call.
        process_id: UUID of the process template.
        work_item_type_ref: Reference name of the work item type.
        state_id: ID of the state to delete.
    """
    org_api_call.delete(
        "work",
        "processes",
        process_id,
        "workItemTypes",
        work_item_type_ref,
        "states",
        state_id,
        version=_PROCESS_API_VERSION,
    )


def post_work_item_type_field(
    org_api_call: ApiCall,
    process_id: ProcessId,
    work_item_type_ref: str,
    request: ProcessWorkItemTypeFieldAddRequest,
) -> ProcessWorkItemField:
    """Add a field to a work item type in a process.

    Args:
        org_api_call: Organisation-level ADO API call.
        process_id: UUID of the process template.
        work_item_type_ref: Reference name of the work item type.
        request: Add request specifying the field reference name and options.

    Returns:
        ProcessWorkItemField describing the field as it was added.
    """
    result = org_api_call.post(
        "work",
        "processes",
        process_id,
        "workItemTypes",
        work_item_type_ref,
        "fields",
        version=_PROCESS_API_VERSION,
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return ProcessWorkItemField.model_validate(result)


def patch_work_item_type_field(
    org_api_call: ApiCall,
    process_id: ProcessId,
    work_item_type_ref: str,
    field_ref: str,
    request: ProcessWorkItemTypeFieldUpdateRequest,
) -> ProcessWorkItemField:
    """Update a field on a work item type in a process.

    Args:
        org_api_call: Organisation-level ADO API call.
        process_id: UUID of the process template.
        work_item_type_ref: Reference name of the work item type.
        field_ref: Reference name of the field to update
            (e.g. ``"System.Title"``).
        request: Update request with fields to change.

    Returns:
        Updated ProcessWorkItemField.
    """
    result = org_api_call.patch(
        "work",
        "processes",
        process_id,
        "workItemTypes",
        work_item_type_ref,
        "fields",
        field_ref,
        version=_PROCESS_API_VERSION,
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return ProcessWorkItemField.model_validate(result)


def delete_work_item_type_field(
    org_api_call: ApiCall,
    process_id: ProcessId,
    work_item_type_ref: str,
    field_ref: str,
) -> None:
    """Remove a field from a work item type in a process.

    Args:
        org_api_call: Organisation-level ADO API call.
        process_id: UUID of the process template.
        work_item_type_ref: Reference name of the work item type.
        field_ref: Reference name of the field to remove.
    """
    org_api_call.delete(
        "work",
        "processes",
        process_id,
        "workItemTypes",
        work_item_type_ref,
        "fields",
        field_ref,
        version=_PROCESS_API_VERSION,
    )


def post_work_item_type_rule(
    org_api_call: ApiCall,
    process_id: ProcessId,
    work_item_type_ref: str,
    request: ProcessWorkItemTypeRuleCreateRequest,
) -> ProcessWorkItemRule:
    """Create a rule on a work item type in a process.

    Args:
        org_api_call: Organisation-level ADO API call.
        process_id: UUID of the process template.
        work_item_type_ref: Reference name of the work item type.
        request: Create request specifying conditions and actions.

    Returns:
        ProcessWorkItemRule for the newly created rule.
    """
    result = org_api_call.post(
        "work",
        "processes",
        process_id,
        "workItemTypes",
        work_item_type_ref,
        "rules",
        version=_PROCESS_API_VERSION,
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return ProcessWorkItemRule.model_validate(result)


def patch_work_item_type_rule(
    org_api_call: ApiCall,
    process_id: ProcessId,
    work_item_type_ref: str,
    rule_id: ProcessWorkItemTypeRuleId,
    request: ProcessWorkItemTypeRuleUpdateRequest,
) -> ProcessWorkItemRule:
    """Update a rule on a work item type in a process.

    Args:
        org_api_call: Organisation-level ADO API call.
        process_id: UUID of the process template.
        work_item_type_ref: Reference name of the work item type.
        rule_id: ID of the rule to update.
        request: Update request with fields to change.

    Returns:
        Updated ProcessWorkItemRule.
    """
    result = org_api_call.patch(
        "work",
        "processes",
        process_id,
        "workItemTypes",
        work_item_type_ref,
        "rules",
        rule_id,
        version=_PROCESS_API_VERSION,
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return ProcessWorkItemRule.model_validate(result)


def delete_work_item_type_rule(
    org_api_call: ApiCall,
    process_id: ProcessId,
    work_item_type_ref: str,
    rule_id: ProcessWorkItemTypeRuleId,
) -> None:
    """Delete a rule from a work item type in a process.

    Args:
        org_api_call: Organisation-level ADO API call.
        process_id: UUID of the process template.
        work_item_type_ref: Reference name of the work item type.
        rule_id: ID of the rule to delete.
    """
    org_api_call.delete(
        "work",
        "processes",
        process_id,
        "workItemTypes",
        work_item_type_ref,
        "rules",
        rule_id,
        version=_PROCESS_API_VERSION,
    )


def post_behavior(
    org_api_call: ApiCall,
    process_id: ProcessId,
    request: ProcessBehaviorCreateRequest,
) -> ProcessBehaviorInfo:
    """Create a behavior in a process.

    Args:
        org_api_call: Organisation-level ADO API call.
        process_id: UUID of the process template.
        request: Create request specifying name and optional color.

    Returns:
        ProcessBehaviorInfo for the newly created behavior.
    """
    result = org_api_call.post(
        "work",
        "processes",
        process_id,
        "behaviors",
        version=_PROCESS_API_VERSION,
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return ProcessBehaviorInfo.model_validate(result)


def patch_behavior(
    org_api_call: ApiCall,
    process_id: ProcessId,
    behavior_ref: str,
    request: ProcessBehaviorUpdateRequest,
) -> ProcessBehaviorInfo:
    """Update a behavior in a process.

    Args:
        org_api_call: Organisation-level ADO API call.
        process_id: UUID of the process template.
        behavior_ref: Reference name of the behavior to update
            (e.g. ``"System.RequirementBacklogBehavior"``).
        request: Update request with fields to change.

    Returns:
        Updated ProcessBehaviorInfo.
    """
    result = org_api_call.patch(
        "work",
        "processes",
        process_id,
        "behaviors",
        behavior_ref,
        version=_PROCESS_API_VERSION,
        json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
    return ProcessBehaviorInfo.model_validate(result)


def delete_behavior(
    org_api_call: ApiCall,
    process_id: ProcessId,
    behavior_ref: str,
) -> None:
    """Delete a behavior from a process.

    Args:
        org_api_call: Organisation-level ADO API call.
        process_id: UUID of the process template.
        behavior_ref: Reference name of the behavior to delete.
    """
    org_api_call.delete(
        "work",
        "processes",
        process_id,
        "behaviors",
        behavior_ref,
        version=_PROCESS_API_VERSION,
    )
