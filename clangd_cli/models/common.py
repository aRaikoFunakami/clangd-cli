from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, field_validator


class Position(BaseModel):
    line: int
    column: int


class Range(BaseModel):
    start: Position
    end: Position


class Location(BaseModel):
    file: str
    line: int
    column: int


class CallSite(BaseModel):
    line: int
    column: int


class HierarchyItem(BaseModel):
    name: str
    kind: str
    location: Location
    detail: Optional[str] = None

    @field_validator("detail", mode="before")
    @classmethod
    def _empty_to_none(cls, v: Any) -> Any:
        return v or None


class DocumentSymbol(BaseModel):
    name: str
    kind: str
    line: int
    column: int
    endLine: int
    endColumn: int
    detail: Optional[str] = None
    selectionRange: Optional[Range] = None
    children: Optional[list[DocumentSymbol]] = None

    @field_validator("detail", mode="before")
    @classmethod
    def _empty_to_none(cls, v: Any) -> Any:
        return v or None


class NotFound(BaseModel):
    found: Literal[False]
    message: str


class ErrorResponse(BaseModel):
    error: Literal[True]
    message: str
    code: Optional[int] = None
    data: Optional[Any] = None
    timeout: Optional[bool] = None
