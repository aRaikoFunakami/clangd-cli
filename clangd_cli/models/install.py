from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class InstallResult(BaseModel):
    created: list[str]
    skipped: list[str]
    permissions_added: Optional[list[str]] = None
    permissions_existed: Optional[list[str]] = None
    permissions_skipped: Optional[list[str]] = None
