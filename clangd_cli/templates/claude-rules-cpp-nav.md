---
paths:
  - "**/*.cpp"
  - "**/*.cc"
  - "**/*.h"
  - "**/*.hh"
---

# clangd-cli Usage Guide

## When to use clangd-cli (instead of grep)
- Locating a symbol by name: `workspace-symbols --query <name>` returns file/line/col
  — use this instead of grep to find where a function or class is defined
- Tracing callers of a function with a common name (draw, get, set, etc.)
- Finding all references to a specific symbol (not just text matches)
- Understanding type hierarchies and virtual dispatch
- Getting type information for auto variables or templates
- Impact analysis before modifying a function signature

## When grep is sufficient
- Searching for text in comments, strings, or disabled code
- Pattern-based searches across the project (regex)
- **Do NOT** use Grep to duplicate information that clangd-cli provides (overrides, callers, references). If clangd-cli can answer the query, Grep should not be issued in parallel as a fallback.

### Recommended workflow
`workspace-symbols` → `impact-analysis` (or `goto-implementation`) → only if gaps remain, supplement with Grep

## Prerequisites
`compile_commands.json` must exist in the project. clangd-cli auto-detects it
in the project root, `build/`, `out/Default/`, `out/Release/`, `out/Debug/`,
or `.build/`. For other locations, add `--compile-commands-dir`:
`clangd-cli --project-root <project-root> --compile-commands-dir <dir> start`

## Configuration (.clangd-cli.json)
Project-level settings can be configured in `.clangd-cli.json` at the project root.
Run `clangd-cli install` to generate a sample config.

```json
{
  "index_file": "index.idx",
  "compile_commands_dir": ".",
  "clangd_path": "clangd",
  "timeout": 30,
  "background_index": true
}
```

- `index_file`: Path to pre-built clangd index (.idx) for faster symbol resolution
- `compile_commands_dir`: Directory containing compile_commands.json
- `clangd_path`: Path to clangd binary
- `timeout`: LSP request timeout in seconds
- `background_index`: Enable/disable background indexing

Priority: CLI arguments > .clangd-cli.json > auto-detection.
If configured, `clangd-cli --project-root <dir> start` is sufficient.

## Daemon lifecycle (IMPORTANT)
- **Do NOT call `start` or `stop` unless the user explicitly asks.** The daemon auto-starts when any command is executed.
- `start` should be run **beforehand** by the user or explicitly requested by the user, because index loading can take significant time.
- If the user asks to start or stop the daemon, do so.
- If a command returns incomplete results (e.g., empty callers), the index may not be ready yet. Suggest the user run `clangd-cli --project-root <dir> start --wait` and retry.
- Check if daemon is running: `clangd-cli --project-root <project-root> status`

Example session:
```
clangd-cli --project-root /home/user/myproject hover --file /home/user/myproject/src/main.cpp --line 10 --col 5
clangd-cli --project-root /home/user/myproject find-references --file /home/user/myproject/src/main.cpp --line 10 --col 5
```

## Named arguments
All commands use named arguments (`--file`, `--line`, `--col`).
Line and column are 0-indexed.

## Commands

### Composite commands (use these first)
- `clangd-cli impact-analysis --file <path> --line <n> --col <n> [--max-depth N] [--max-nodes N] [--no-virtual] [--no-callees]`
  — Recursive caller trace with BFS + callees + virtual dispatch + lambda detection (all enabled by default)
  Example: `clangd-cli impact-analysis --file /path/to/file.cpp --line 10 --col 5`
- `clangd-cli describe --file <path> --line <n> --col <n> [--no-callers] [--no-callees]`
  — Symbol overview: hover + definition + references + callers + callees
  Example: `clangd-cli describe --file /path/to/file.cpp --line 10 --col 5`

### Navigation
- `clangd-cli goto-definition --file <path> --line <n> --col <n>`
  Example: `clangd-cli goto-definition --file /path/to/file.cpp --line 10 --col 5`
- `clangd-cli goto-declaration --file <path> --line <n> --col <n>`
- `clangd-cli goto-type-definition --file <path> --line <n> --col <n>` — jump to the type of the symbol
- `clangd-cli goto-implementation --file <path> --line <n> --col <n>` — find overrides of a virtual method
- `clangd-cli switch-header-source --file <path>` — toggle .cc ↔ .hh
  Example: `clangd-cli switch-header-source --file /path/to/file.cpp`

### Understanding code
- `clangd-cli hover --file <path> --line <n> --col <n>` — type signature, including auto-deduced types
  Example: `clangd-cli hover --file /path/to/file.cpp --line 10 --col 5`
- `clangd-cli ast --file <path> --line <n> --col <n> --depth N` — AST structure at position
- `clangd-cli file-symbols --file <path>` — hierarchical symbol outline
  Example: `clangd-cli file-symbols --file /path/to/file.cpp`
- `clangd-cli workspace-symbols --query <name>` — search symbols by name
  Example: `clangd-cli workspace-symbols --query MyClass`

### Type hierarchies
- `clangd-cli type-hierarchy-sub --file <path> --line <n> --col <n>` — derived classes
- `clangd-cli type-hierarchy-super --file <path> --line <n> --col <n>` — base classes

### Low-level (use when composite commands don't fit)
- `clangd-cli call-hierarchy-in --file <path> --line <n> --col <n>` — direct callers (1 level only)
- `clangd-cli call-hierarchy-out --file <path> --line <n> --col <n>` — direct callees (1 level only)
- `clangd-cli find-references --file <path> --line <n> --col <n>` — all references to a symbol
- `clangd-cli highlight-symbol --file <path> --line <n> --col <n>` — all occurrences with Read/Write/Text kind
- `clangd-cli diagnostics --file <path>` — compiler errors/warnings
- `clangd-cli inlay-hints --file <path> --range START:END` — parameter names, deduced types
- `clangd-cli document-links --file <path>` — resolved #include paths

## Known limitations
- `call-hierarchy-in` misses calls from within lambdas.
  Use `impact-analysis` instead — it auto-detects uncovered references.
- Virtual dispatch: `impact-analysis` automatically explores base class callers and
  sibling overrides for virtual methods. Use `type-hierarchy-sub` for full class hierarchy.
