from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, field_validator

from .common import CallSite, HierarchyItem, Location


class CallerItem(BaseModel):
    name: str
    kind: str
    location: Location
    detail: Optional[str] = None
    depth: int
    call_sites: list[CallSite]

    @field_validator("detail", mode="before")
    @classmethod
    def _empty_to_none(cls, v: Any) -> Any:
        return v or None


class UncoveredRef(BaseModel):
    file: str
    line: int
    column: int
    note: str


class DispatchCaller(BaseModel):
    name: str
    kind: str
    location: Location
    detail: Optional[str] = None
    call_sites: list[CallSite]
    note: str

    @field_validator("detail", mode="before")
    @classmethod
    def _empty_to_none(cls, v: Any) -> Any:
        return v or None


class VirtualDispatch(BaseModel):
    base_method: Optional[Location] = None
    dispatch_callers: list[DispatchCaller]
    sibling_overrides: list[Location]


class ImpactStats(BaseModel):
    depth_reached: int
    total_callers: int
    total_callees: int
    total_references: int
    truncated: bool
    files_opened: int


class ImpactAnalysisSuccess(BaseModel):
    found: Literal[True]
    root: HierarchyItem
    callees: list[HierarchyItem]
    callers: list[CallerItem]
    uncovered_references: list[UncoveredRef]
    virtual_dispatch: VirtualDispatch
    stats: ImpactStats
    is_virtual_override: Optional[bool] = None


class ReferencesSummary(BaseModel):
    total: int
    by_file: dict[str, int]


class CallerWithSites(BaseModel):
    name: str
    kind: str
    location: Location
    detail: Optional[str] = None
    call_sites: list[CallSite]

    @field_validator("detail", mode="before")
    @classmethod
    def _empty_to_none(cls, v: Any) -> Any:
        return v or None


class DescribeSuccess(BaseModel):
    found: Literal[True]
    hover: Optional[str] = None
    definition: Optional[Location] = None
    references: Optional[ReferencesSummary] = None
    symbol: Optional[HierarchyItem] = None
    callers: Optional[list[CallerWithSites]] = None
    callees: Optional[list[HierarchyItem]] = None
