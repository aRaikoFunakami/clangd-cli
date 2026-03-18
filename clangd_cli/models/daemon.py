from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class DaemonStarted(BaseModel):
    status: Literal["started"]
    pid: int
    index_file: Optional[str] = None
    hint: Optional[str] = None
    compile_commands_dir: Optional[str] = None
    index_ready: Optional[bool] = None


class DaemonAlreadyRunning(BaseModel):
    status: Literal["already_running"]


class DaemonStartTimeout(BaseModel):
    status: Literal["start_timeout"]
    pid: int


class DaemonStopping(BaseModel):
    status: Literal["stopping"]


class DaemonNotRunning(BaseModel):
    status: Literal["not_running"]


class DaemonOk(BaseModel):
    status: Literal["ok"]
    pid: int
    clangd_args: list[str]
    opened_files: int
    index_file: Optional[str] = None
    index_ready: bool


class DaemonError(BaseModel):
    status: Literal["error"]
    message: str
