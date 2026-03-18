from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel

from .common import Range


class HoverSuccess(BaseModel):
    found: Literal[True]
    content: str
    contentKind: Optional[str] = None
    range: Optional[Range] = None


class Diagnostic(BaseModel):
    severity: str
    line: int
    column: int
    endLine: int
    endColumn: int
    message: str
    code: Optional[Union[str, int]] = None
    source: Optional[str] = None
    relatedInformation: Optional[list[DiagnosticRelatedInfo]] = None


class DiagnosticRelatedInfo(BaseModel):
    location: DiagnosticLocation
    message: str


class DiagnosticLocation(BaseModel):
    file: str
    line: int
    column: int


class DiagnosticsSuccess(BaseModel):
    found: Literal[True]
    count: int
    diagnostics: list[Diagnostic]


class InlayHint(BaseModel):
    line: int
    column: int
    label: str
    kind: Optional[str] = None
    paddingLeft: Optional[bool] = None
    paddingRight: Optional[bool] = None


class InlayHintsSuccess(BaseModel):
    found: Literal[True]
    count: int
    hints: list[InlayHint]


class SemanticToken(BaseModel):
    line: int
    column: int
    length: int
    type: int
    modifiers: int


class SemanticTokensSuccess(BaseModel):
    found: Literal[True]
    count: int
    tokens: list[SemanticToken]


class AstNode(BaseModel):
    role: Optional[str] = None
    kind: Optional[str] = None
    detail: Optional[str] = None
    arcana: Optional[str] = None
    range: Optional[Range] = None
    children: Optional[list[AstNode]] = None
    children_count: Optional[int] = None


class AstSuccess(BaseModel):
    found: Literal[True]
    node: AstNode
