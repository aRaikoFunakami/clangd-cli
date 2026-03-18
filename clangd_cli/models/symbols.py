from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, field_validator

from .common import CallSite, DocumentSymbol, HierarchyItem, Location


class FileSymbolsSuccess(BaseModel):
    found: Literal[True]
    count: int
    symbols: list[DocumentSymbol]


class WorkspaceSymbol(BaseModel):
    name: str
    kind: str
    file: str
    line: int
    column: int
    container: Optional[str] = None


class WorkspaceSymbolsSuccess(BaseModel):
    found: Literal[True]
    count: int
    returned: int
    truncated: bool
    symbols: list[WorkspaceSymbol]


class IncomingCallItem(BaseModel):
    caller: str
    kind: str
    location: Location
    detail: Optional[str] = None
    call_sites: list[CallSite]

    @field_validator("detail", mode="before")
    @classmethod
    def _empty_to_none(cls, v: Any) -> Any:
        return v or None


class CallHierarchyInSuccess(BaseModel):
    found: Literal[True]
    symbol: HierarchyItem
    incoming_calls: list[IncomingCallItem]
    incoming_count: int
    all_symbols: Optional[list[HierarchyItem]] = None


class OutgoingCallItem(BaseModel):
    callee: str
    kind: str
    location: Location
    detail: Optional[str] = None
    call_sites: list[CallSite]

    @field_validator("detail", mode="before")
    @classmethod
    def _empty_to_none(cls, v: Any) -> Any:
        return v or None


class CallHierarchyOutSuccess(BaseModel):
    found: Literal[True]
    symbol: HierarchyItem
    outgoing_calls: list[OutgoingCallItem]
    outgoing_count: int
    all_symbols: Optional[list[HierarchyItem]] = None


class TypeHierarchySuperSuccess(BaseModel):
    found: Literal[True]
    type: HierarchyItem
    supertypes: list[HierarchyItem]
    supertypes_count: int
    all_types: Optional[list[HierarchyItem]] = None


class TypeHierarchySubSuccess(BaseModel):
    found: Literal[True]
    type: HierarchyItem
    subtypes: list[HierarchyItem]
    subtypes_count: int
    all_types: Optional[list[HierarchyItem]] = None
