from __future__ import annotations

from typing import Union

from pydantic import TypeAdapter

from .common import (
    Position, Range, Location, CallSite, HierarchyItem,
    DocumentSymbol, NotFound, ErrorResponse,
)
from .analysis import (
    HoverSuccess, DiagnosticsSuccess, InlayHintsSuccess,
    SemanticTokensSuccess, AstSuccess,
    Diagnostic, DiagnosticRelatedInfo, DiagnosticLocation,
    InlayHint, SemanticToken, AstNode,
)
from .navigation import (
    GotoSuccess, FindReferencesSuccess, SwitchHeaderSourceSuccess,
)
from .symbols import (
    FileSymbolsSuccess, WorkspaceSymbolsSuccess,
    CallHierarchyInSuccess, CallHierarchyOutSuccess,
    TypeHierarchySuperSuccess, TypeHierarchySubSuccess,
    WorkspaceSymbol, IncomingCallItem, OutgoingCallItem,
)
from .structure import HighlightSuccess, DocumentLinksSuccess, Highlight, DocumentLink
from .composite import (
    ImpactAnalysisSuccess, DescribeSuccess, InvestigateSuccess,
    CallerItem, UncoveredRef, DispatchCaller, VirtualDispatch,
    ImpactStats, ReferencesSummary, CallerWithSites,
    CallerDetail, TypeHierarchyInfo, InvestigateStats,
)
from .daemon import (
    DaemonStarted, DaemonAlreadyRunning, DaemonStartTimeout,
    DaemonStopping, DaemonNotRunning, DaemonOk, DaemonError,
)
from .install import InstallResult

__all__ = [
    # common
    "Position", "Range", "Location", "CallSite", "HierarchyItem",
    "DocumentSymbol", "NotFound", "ErrorResponse",
    # analysis
    "HoverSuccess", "DiagnosticsSuccess", "InlayHintsSuccess",
    "SemanticTokensSuccess", "AstSuccess",
    "Diagnostic", "DiagnosticRelatedInfo", "DiagnosticLocation",
    "InlayHint", "SemanticToken", "AstNode",
    # navigation
    "GotoSuccess", "FindReferencesSuccess", "SwitchHeaderSourceSuccess",
    # symbols
    "FileSymbolsSuccess", "WorkspaceSymbolsSuccess",
    "CallHierarchyInSuccess", "CallHierarchyOutSuccess",
    "TypeHierarchySuperSuccess", "TypeHierarchySubSuccess",
    "WorkspaceSymbol", "IncomingCallItem", "OutgoingCallItem",
    # structure
    "HighlightSuccess", "DocumentLinksSuccess", "Highlight", "DocumentLink",
    # composite
    "ImpactAnalysisSuccess", "DescribeSuccess", "InvestigateSuccess",
    "CallerItem", "UncoveredRef", "DispatchCaller", "VirtualDispatch",
    "ImpactStats", "ReferencesSummary", "CallerWithSites",
    "CallerDetail", "TypeHierarchyInfo", "InvestigateStats",
    # daemon
    "DaemonStarted", "DaemonAlreadyRunning", "DaemonStartTimeout",
    "DaemonStopping", "DaemonNotRunning", "DaemonOk", "DaemonError",
    # install
    "InstallResult",
    # schema
    "get_command_schemas",
]

_COMMAND_RESPONSE_TYPES = {
    "hover": Union[HoverSuccess, NotFound, ErrorResponse],
    "diagnostics": Union[DiagnosticsSuccess, NotFound, ErrorResponse],
    "inlay-hints": Union[InlayHintsSuccess, NotFound, ErrorResponse],
    "semantic-tokens": Union[SemanticTokensSuccess, NotFound, ErrorResponse],
    "ast": Union[AstSuccess, NotFound, ErrorResponse],
    "goto-definition": Union[GotoSuccess, NotFound, ErrorResponse],
    "goto-declaration": Union[GotoSuccess, NotFound, ErrorResponse],
    "goto-implementation": Union[GotoSuccess, NotFound, ErrorResponse],
    "goto-type-definition": Union[GotoSuccess, NotFound, ErrorResponse],
    "find-references": Union[FindReferencesSuccess, NotFound, ErrorResponse],
    "switch-header-source": Union[SwitchHeaderSourceSuccess, NotFound, ErrorResponse],
    "file-symbols": Union[FileSymbolsSuccess, NotFound, ErrorResponse],
    "workspace-symbols": Union[WorkspaceSymbolsSuccess, NotFound, ErrorResponse],
    "call-hierarchy-in": Union[CallHierarchyInSuccess, NotFound, ErrorResponse],
    "call-hierarchy-out": Union[CallHierarchyOutSuccess, NotFound, ErrorResponse],
    "type-hierarchy-super": Union[TypeHierarchySuperSuccess, NotFound, ErrorResponse],
    "type-hierarchy-sub": Union[TypeHierarchySubSuccess, NotFound, ErrorResponse],
    "highlight-symbol": Union[HighlightSuccess, NotFound, ErrorResponse],
    "document-links": Union[DocumentLinksSuccess, NotFound, ErrorResponse],
    "impact-analysis": Union[ImpactAnalysisSuccess, NotFound, ErrorResponse],
    "describe": Union[DescribeSuccess, NotFound, ErrorResponse],
    "investigate": Union[InvestigateSuccess, NotFound, ErrorResponse],
    "start": Union[DaemonStarted, DaemonAlreadyRunning, DaemonStartTimeout, DaemonError],
    "stop": Union[DaemonStopping, DaemonNotRunning, DaemonError],
    "status": Union[DaemonOk, DaemonNotRunning],
    "install": InstallResult,
}


def get_command_schemas() -> dict[str, dict]:
    """Return a mapping of command name to JSON Schema."""
    schemas = {}
    for name, response_type in _COMMAND_RESPONSE_TYPES.items():
        adapter = TypeAdapter(response_type)
        schemas[name] = adapter.json_schema()
    return schemas
