"""OOP wrapper for Azure DevOps work process resources."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from typing import TYPE_CHECKING

from pyado import raw
from pyado.raw import (
    ProcessBehaviorCreateRequest,
    ProcessBehaviorInfo,
    ProcessBehaviorUpdateRequest,
    ProcessDetail,
    ProcessId,
    ProcessUpdateRequest,
    ProcessWITInfo,
    ProcessWorkItemField,
    ProcessWorkItemRule,
    ProcessWorkItemState,
    ProcessWorkItemTypeCreateRequest,
    ProcessWorkItemTypeFieldAddRequest,
    ProcessWorkItemTypeFieldUpdateRequest,
    ProcessWorkItemTypeRuleCreateRequest,
    ProcessWorkItemTypeRuleId,
    ProcessWorkItemTypeRuleUpdateRequest,
    ProcessWorkItemTypeStateCreateRequest,
    ProcessWorkItemTypeStateId,
    ProcessWorkItemTypeStateUpdateRequest,
    ProcessWorkItemTypeUpdateRequest,
)

if TYPE_CHECKING:
    from pyado.oop.organization import Organization

__all__ = ["Process"]


class Process:
    """An ADO work process template at organisation scope.

    Wraps a single ADO work process, giving access to all mutation
    operations — work item type CRUD, state CRUD, field add/update/remove,
    rule CRUD, and behavior CRUD.

    Instances are obtained from :meth:`Organization.iter_processes`,
    :meth:`Organization.list_processes`, :meth:`Organization.get_process`,
    or :meth:`Organization.create_process`.

    Attributes:
        _org: The Organisation this process belongs to.
        _id: Process template UUID (always known).
        _info: Cached process data; ``None`` after :meth:`refresh`.
    """

    def __init__(self, org: "Organization", info: ProcessDetail) -> None:
        """Construct a Process wrapper.

        Args:
            org: The Organisation this process belongs to.
            info: ProcessDetail returned by the ADO process API.
        """
        self._org = org
        self._id: ProcessId = info.type_id
        self._info: ProcessDetail | None = info

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> ProcessId:
        """Process template UUID — always known, no API call."""
        return self._id

    @property
    def name(self) -> str:
        """Process template display name."""
        return self.info.name

    @property
    def description(self) -> str:
        """Process template description."""
        return self.info.description

    @property
    def info(self) -> ProcessDetail:
        """Full process data as returned by the API.

        Fetched lazily by re-querying the API if :meth:`refresh` was
        called since the last access.
        """
        if self._info is None:
            self._info = raw.get_process(self._org.api_call, self._id)
        return self._info

    @property
    def org(self) -> "Organization":
        """Organisation this process belongs to — zero-cost."""
        return self._org

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Discard cached process data.

        The next access to :attr:`info` re-fetches from the API.
        """
        self._info = None

    # ------------------------------------------------------------------
    # Process mutations
    # ------------------------------------------------------------------

    def update(self, request: ProcessUpdateRequest) -> None:
        """Update this process template.

        Args:
            request: Update request with fields to change.
        """
        self._info = raw.patch_process(self._org.api_call, self._id, request)

    def delete(self) -> None:
        """Delete this process template from the organisation."""
        raw.delete_process(self._org.api_call, self._id)
        self._info = None

    # ------------------------------------------------------------------
    # Work item type mutations
    # ------------------------------------------------------------------

    def create_work_item_type(
        self, request: ProcessWorkItemTypeCreateRequest
    ) -> ProcessWITInfo:
        """Create a work item type in this process.

        Args:
            request: Create request specifying name and optional fields.

        Returns:
            ProcessWITInfo for the newly created work item type.
        """
        return raw.post_work_item_type(self._org.api_call, self._id, request)

    def update_work_item_type(
        self,
        work_item_type_ref: str,
        request: ProcessWorkItemTypeUpdateRequest,
    ) -> ProcessWITInfo:
        """Update a work item type in this process.

        Args:
            work_item_type_ref: Reference name of the work item type.
            request: Update request with fields to change.

        Returns:
            Updated ProcessWITInfo.
        """
        return raw.patch_work_item_type(
            self._org.api_call, self._id, work_item_type_ref, request
        )

    def delete_work_item_type(self, work_item_type_ref: str) -> None:
        """Delete a work item type from this process.

        Args:
            work_item_type_ref: Reference name of the work item type to delete.
        """
        raw.delete_work_item_type(self._org.api_call, self._id, work_item_type_ref)

    # ------------------------------------------------------------------
    # State mutations
    # ------------------------------------------------------------------

    def create_work_item_type_state(
        self,
        work_item_type_ref: str,
        request: ProcessWorkItemTypeStateCreateRequest,
    ) -> ProcessWorkItemState:
        """Create a state on a work item type in this process.

        Args:
            work_item_type_ref: Reference name of the work item type.
            request: Create request for the new state.

        Returns:
            ProcessWorkItemState for the newly created state.
        """
        return raw.post_work_item_type_state(
            self._org.api_call, self._id, work_item_type_ref, request
        )

    def update_work_item_type_state(
        self,
        work_item_type_ref: str,
        state_id: ProcessWorkItemTypeStateId,
        request: ProcessWorkItemTypeStateUpdateRequest,
    ) -> ProcessWorkItemState:
        """Update a state on a work item type in this process.

        Args:
            work_item_type_ref: Reference name of the work item type.
            state_id: ID of the state to update.
            request: Update request with fields to change.

        Returns:
            Updated ProcessWorkItemState.
        """
        return raw.patch_work_item_type_state(
            self._org.api_call, self._id, work_item_type_ref, state_id, request
        )

    def delete_work_item_type_state(
        self,
        work_item_type_ref: str,
        state_id: ProcessWorkItemTypeStateId,
    ) -> None:
        """Delete a state from a work item type in this process.

        Args:
            work_item_type_ref: Reference name of the work item type.
            state_id: ID of the state to delete.
        """
        raw.delete_work_item_type_state(
            self._org.api_call, self._id, work_item_type_ref, state_id
        )

    # ------------------------------------------------------------------
    # Field mutations
    # ------------------------------------------------------------------

    def add_work_item_type_field(
        self,
        work_item_type_ref: str,
        request: ProcessWorkItemTypeFieldAddRequest,
    ) -> ProcessWorkItemField:
        """Add a field to a work item type in this process.

        Args:
            work_item_type_ref: Reference name of the work item type.
            request: Add request specifying field reference name and options.

        Returns:
            ProcessWorkItemField describing the field as it was added.
        """
        return raw.post_work_item_type_field(
            self._org.api_call, self._id, work_item_type_ref, request
        )

    def update_work_item_type_field(
        self,
        work_item_type_ref: str,
        field_ref: str,
        request: ProcessWorkItemTypeFieldUpdateRequest,
    ) -> ProcessWorkItemField:
        """Update a field on a work item type in this process.

        Args:
            work_item_type_ref: Reference name of the work item type.
            field_ref: Reference name of the field to update.
            request: Update request with fields to change.

        Returns:
            Updated ProcessWorkItemField.
        """
        return raw.patch_work_item_type_field(
            self._org.api_call, self._id, work_item_type_ref, field_ref, request
        )

    def remove_work_item_type_field(
        self,
        work_item_type_ref: str,
        field_ref: str,
    ) -> None:
        """Remove a field from a work item type in this process.

        Args:
            work_item_type_ref: Reference name of the work item type.
            field_ref: Reference name of the field to remove.
        """
        raw.delete_work_item_type_field(
            self._org.api_call, self._id, work_item_type_ref, field_ref
        )

    # ------------------------------------------------------------------
    # Rule mutations
    # ------------------------------------------------------------------

    def create_work_item_type_rule(
        self,
        work_item_type_ref: str,
        request: ProcessWorkItemTypeRuleCreateRequest,
    ) -> ProcessWorkItemRule:
        """Create a rule on a work item type in this process.

        Args:
            work_item_type_ref: Reference name of the work item type.
            request: Create request specifying conditions and actions.

        Returns:
            ProcessWorkItemRule for the newly created rule.
        """
        return raw.post_work_item_type_rule(
            self._org.api_call, self._id, work_item_type_ref, request
        )

    def update_work_item_type_rule(
        self,
        work_item_type_ref: str,
        rule_id: ProcessWorkItemTypeRuleId,
        request: ProcessWorkItemTypeRuleUpdateRequest,
    ) -> ProcessWorkItemRule:
        """Update a rule on a work item type in this process.

        Args:
            work_item_type_ref: Reference name of the work item type.
            rule_id: ID of the rule to update.
            request: Update request with fields to change.

        Returns:
            Updated ProcessWorkItemRule.
        """
        return raw.patch_work_item_type_rule(
            self._org.api_call, self._id, work_item_type_ref, rule_id, request
        )

    def delete_work_item_type_rule(
        self,
        work_item_type_ref: str,
        rule_id: ProcessWorkItemTypeRuleId,
    ) -> None:
        """Delete a rule from a work item type in this process.

        Args:
            work_item_type_ref: Reference name of the work item type.
            rule_id: ID of the rule to delete.
        """
        raw.delete_work_item_type_rule(
            self._org.api_call, self._id, work_item_type_ref, rule_id
        )

    # ------------------------------------------------------------------
    # Behavior mutations
    # ------------------------------------------------------------------

    def create_behavior(
        self, request: ProcessBehaviorCreateRequest
    ) -> ProcessBehaviorInfo:
        """Create a behavior in this process.

        Args:
            request: Create request specifying name and optional color.

        Returns:
            ProcessBehaviorInfo for the newly created behavior.
        """
        return raw.post_behavior(self._org.api_call, self._id, request)

    def update_behavior(
        self,
        behavior_ref: str,
        request: ProcessBehaviorUpdateRequest,
    ) -> ProcessBehaviorInfo:
        """Update a behavior in this process.

        Args:
            behavior_ref: Reference name of the behavior to update.
            request: Update request with fields to change.

        Returns:
            Updated ProcessBehaviorInfo.
        """
        return raw.patch_behavior(self._org.api_call, self._id, behavior_ref, request)

    def delete_behavior(self, behavior_ref: str) -> None:
        """Delete a behavior from this process.

        Args:
            behavior_ref: Reference name of the behavior to delete.
        """
        raw.delete_behavior(self._org.api_call, self._id, behavior_ref)
