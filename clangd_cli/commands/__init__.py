from .analysis import cmd_hover, cmd_diagnostics, cmd_inlay_hints, cmd_semantic_tokens, cmd_ast
from .navigation import (cmd_goto_definition, cmd_goto_declaration, cmd_goto_implementation,
                          cmd_goto_type_definition, cmd_find_references, cmd_switch_header_source)
from .symbols import (cmd_file_symbols, cmd_workspace_symbols,
                       cmd_call_hierarchy_in, cmd_call_hierarchy_out,
                       cmd_type_hierarchy_super, cmd_type_hierarchy_sub)
from .structure import cmd_highlight_symbol, cmd_document_links
from .composite import cmd_impact_analysis, cmd_describe, cmd_investigate

COMMAND_MAP = {
    "hover": cmd_hover,
    "diagnostics": cmd_diagnostics,
    "inlay-hints": cmd_inlay_hints,
    "semantic-tokens": cmd_semantic_tokens,
    "ast": cmd_ast,
    "goto-definition": cmd_goto_definition,
    "goto-declaration": cmd_goto_declaration,
    "goto-implementation": cmd_goto_implementation,
    "goto-type-definition": cmd_goto_type_definition,
    "find-references": cmd_find_references,
    "switch-header-source": cmd_switch_header_source,
    "file-symbols": cmd_file_symbols,
    "workspace-symbols": cmd_workspace_symbols,
    "call-hierarchy-in": cmd_call_hierarchy_in,
    "call-hierarchy-out": cmd_call_hierarchy_out,
    "type-hierarchy-super": cmd_type_hierarchy_super,
    "type-hierarchy-sub": cmd_type_hierarchy_sub,
    "highlight-symbol": cmd_highlight_symbol,
    "document-links": cmd_document_links,
    "impact-analysis": cmd_impact_analysis,
    "describe": cmd_describe,
    "investigate": cmd_investigate,
}
