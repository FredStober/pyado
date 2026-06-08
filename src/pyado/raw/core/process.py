"""Azure DevOps work process API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from enum import StrEnum
from typing import TypeAlias
from uuid import UUID

from pydantic import Field

from pyado.raw._core import AdoBaseModel, ApiCall
from pyado.raw.boards.work_item import WorkItemFieldType

__all__ = [
    "ProcessBehaviorField",
    "ProcessBehaviorInfo",
    "ProcessDetail",
    "ProcessId",
    "ProcessType",
    "ProcessWITField",
    "ProcessWITInfo",
    "ProcessWITRule",
    "ProcessWITState",
    "ProjectFieldInfo",
    "get_process_info",
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


class ProcessWITState(AdoBaseModel):
    """A work item type state as returned by the process states API."""

    name: str
    state_category: str | None = None
    id: str | None = None
    color: str | None = None
    url: str | None = None


class ProcessWITField(AdoBaseModel):
    """A field entry on a work item type in a process."""

    name: str | None = None
    reference_name: str | None = None
    field_type: WorkItemFieldType | None = None
    is_required: bool = False
    is_read_only: bool = False
    default_value: str | None = None
    help_text: str | None = None
    allowed_values: list[str] | None = None


class _ProcessWITRuleCondition(AdoBaseModel):
    """A condition clause in a work item type rule."""

    condition_type: str | None = None
    field: str | None = None
    value: str | None = None


class _ProcessWITRuleAction(AdoBaseModel):
    """An action clause in a work item type rule."""

    action_type: str | None = None
    target_field: str | None = None
    value: str | None = None


class ProcessWITRule(AdoBaseModel):
    """A workflow rule on a work item type in a process."""

    id: str | None = None
    name: str | None = None
    is_system: bool = False
    is_disabled: bool = False
    conditions: list[_ProcessWITRuleCondition] = Field(default_factory=list)
    actions: list[_ProcessWITRuleAction] = Field(default_factory=list)


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
    states: list[ProcessWITState] = Field(default_factory=list)
    rules: list[ProcessWITRule] = Field(default_factory=list)
    fields: list[ProcessWITField] = Field(default_factory=list)


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
    customization_type: str | None = None
    is_default: bool = False
    work_item_types: list[ProcessWITInfo] = Field(default_factory=list)
    behaviors: list[ProcessBehaviorInfo] = Field(default_factory=list)
    project_fields: list[ProjectFieldInfo] = Field(default_factory=list)


def _fetch_wit_sub_resources(
    org_api_call: ApiCall,
    process_id: UUID,
    wit_ref: str,
) -> tuple[list[ProcessWITState], list[ProcessWITRule], list[ProcessWITField]]:
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
        ProcessWITState.model_validate(item) for item in states_result.get("value", [])
    ]

    rules_result = base.get("rules", version=_PROCESS_API_VERSION)
    rules = [
        ProcessWITRule.model_validate(item) for item in rules_result.get("value", [])
    ]

    fields_result = base.get("fields", version=_PROCESS_API_VERSION)
    fields = [
        ProcessWITField.model_validate(item) for item in fields_result.get("value", [])
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
