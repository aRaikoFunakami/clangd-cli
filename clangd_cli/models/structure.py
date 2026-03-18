from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class Highlight(BaseModel):
    line: int
    column: int
    endLine: int
    endColumn: int
    kind: Optional[str] = None


class HighlightSuccess(BaseModel):
    found: Literal[True]
    count: int
    highlights: list[Highlight]


class DocumentLink(BaseModel):
    line: int
    column: int
    endLine: int
    endColumn: int
    target: Optional[str] = None


class DocumentLinksSuccess(BaseModel):
    found: Literal[True]
    count: int
    links: list[DocumentLink]
