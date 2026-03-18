from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .common import Location


class GotoSuccess(BaseModel):
    found: Literal[True]
    count: int
    locations: list[Location]


class FindReferencesSuccess(BaseModel):
    found: Literal[True]
    count: int
    locations: list[Location]


class SwitchHeaderSourceSuccess(BaseModel):
    found: Literal[True]
    file: str
