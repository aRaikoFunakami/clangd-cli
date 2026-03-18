---
name: clangd-nav
description: Analyze C++ code impact and navigate symbols using clangd semantic analysis
allowed-tools: Bash(clangd-cli *)
---

# C++ Semantic Navigation

Use this skill when asked to:
- Analyze impact of modifying a C++ function
- Trace call chains through the codebase
- Find all implementations of a virtual method
- Understand class hierarchies

## Decision flow

### Locate a symbol
- Don't know the file/line/col? → `workspace-symbols --query <name>`

### Structural / semantic queries (always use clangd-cli)
- Impact analysis / caller trace → `impact-analysis` (includes callees, virtual dispatch, and lambda detection)
- Symbol overview (type, callers, callees) → `describe`
- Override list for a virtual method → `goto-implementation`
- Virtual method full analysis → `impact-analysis` (traces base class callers + sibling overrides)
- Type info for auto/template → `describe` or `hover`
- Common names (draw, get, set) → clangd-cli avoids false positives

### When to use Grep instead
- Searching text in comments, strings, or disabled code
- Regex pattern searches across the project
- Symbol name is unique and you only need the source text

**Do NOT use Grep as a parallel fallback** for structural queries that clangd-cli handles.
If clangd-cli can answer the question (overrides, callers, references), do not also issue Grep for the same information.

## Daemon lifecycle

- **Do NOT call `start` or `stop` unless the user explicitly asks.** The daemon auto-starts when any command is executed.
- `start` should be run **beforehand** by the user or explicitly requested by the user, because index loading can take significant time. If the daemon is already running, calling `start` again is harmless but wasteful.
- If the user asks to start or stop the daemon, do so.
- If a command returns incomplete results (e.g., empty callers), the index may not be ready yet. Suggest the user run `clangd-cli --project-root <dir> start --wait` and retry.

## Command syntax
All commands use named arguments: `--file <path> --line <n> --col <n>`

Example:
```
clangd-cli --project-root . workspace-symbols --query OnThemeChanged
clangd-cli --project-root . impact-analysis --file src/main.cpp --line 10 --col 5
```

$ARGUMENTS
