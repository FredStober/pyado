"""Azure DevOps dashboard API wrappers."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from collections.abc import Iterator
from typing import TypeAlias
from uuid import UUID

from pydantic import Field

from pyado.raw._core import AdoBaseModel, ApiCall

__all__ = [
    "DashboardId",
    "DashboardInfo",
    "WidgetId",
    "WidgetInfo",
    "get_dashboard",
    "get_dashboard_api_call",
    "iter_dashboards",
    "list_dashboards",
]

DashboardId: TypeAlias = UUID
#: UUID identifier for a dashboard widget.
WidgetId: TypeAlias = UUID

_DASHBOARD_API_VERSION = "7.1-preview.3"


class _WidgetPosition(AdoBaseModel):
    """Position of a widget on a dashboard grid."""

    row: int = 0
    column: int = 0


class _WidgetSize(AdoBaseModel):
    """Size of a widget on a dashboard grid."""

    row_span: int = 0
    column_span: int = 0


class WidgetInfo(AdoBaseModel):
    """A widget on an ADO dashboard."""

    id: WidgetId
    name: str
    type_id: str = ""
    position: _WidgetPosition | None = None
    size: _WidgetSize | None = None


class DashboardInfo(AdoBaseModel):
    """Minimal representation of an ADO team dashboard."""

    id: DashboardId
    name: str
    description: str = ""
    etag: str | None = None
    widgets: list[WidgetInfo] = Field(default_factory=list)


class _DashboardResults(AdoBaseModel):
    """Internal: container for dashboard list results."""

    value: list[DashboardInfo]


def get_dashboard_api_call(
    team_api_call: ApiCall,
    dashboard_id: DashboardId,
) -> ApiCall:
    """Build a dashboard-scoped API call.

    Args:
        team_api_call: Team-level ADO API call
            (from ``make_team_api_call``).
        dashboard_id: UUID of the dashboard.

    Returns:
        An ApiCall pointing at the dashboard resource.
    """
    return team_api_call.build_call(
        "dashboard",
        "dashboards",
        dashboard_id,
        version=_DASHBOARD_API_VERSION,
    )


def iter_dashboards(
    team_api_call: ApiCall,
) -> Iterator[DashboardInfo]:
    """Iterate over all dashboards for a team.

    Args:
        team_api_call: Team-level ADO API call
            (from ``make_team_api_call``).

    Yields:
        DashboardInfo for each dashboard (without widgets — widgets are
        only present in the detail response, see ``get_dashboard``).
    """
    result = team_api_call.get(
        "dashboard",
        "dashboards",
        version=_DASHBOARD_API_VERSION,
    )
    for item in result.get("value", []):
        yield DashboardInfo.model_validate(item)


def list_dashboards(
    team_api_call: ApiCall,
) -> list[DashboardInfo]:
    """Return all dashboards for a team as a list."""
    return list(iter_dashboards(team_api_call))


def get_dashboard(
    dashboard_api_call: ApiCall,
) -> DashboardInfo:
    """Return the detail for a single dashboard, including its widgets.

    Args:
        dashboard_api_call: Dashboard-level ADO API call (from
            ``get_dashboard_api_call``).

    Returns:
        DashboardInfo with the full widget list populated.
    """
    result = dashboard_api_call.get()
    return DashboardInfo.model_validate(result)
