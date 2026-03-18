---
applyTo: "**/*.{cpp,cc,h,hh}"
---

# clangd-cli for C++ Navigation

## Quick reference
```
clangd-cli <command> [args]
```

Composite: impact-analysis, describe
Navigation: hover, goto-definition, goto-declaration, goto-type-definition,
goto-implementation, find-references, switch-header-source
Symbols: file-symbols, workspace-symbols, call-hierarchy-in, call-hierarchy-out,
type-hierarchy-sub, type-hierarchy-super
Structure: highlight-symbol, document-links, ast, diagnostics, inlay-hints,
semantic-tokens

## Named arguments
All commands use named arguments (`--file`, `--line`, `--col`).
Line and column are 0-indexed.

## When to use (instead of grep)
- Locate a symbol: `clangd-cli workspace-symbols --query <name>` — find file/line/col by name
- Impact analysis: `clangd-cli impact-analysis --file <path> --line <n> --col <n>` — recursive caller trace + callees + virtual dispatch
- Override list: `clangd-cli goto-implementation --file <path> --line <n> --col <n>` — find all overrides of a virtual method
- Symbol overview: `clangd-cli describe --file <path> --line <n> --col <n>` — type + callers + callees
- Common names: draw, get, set, create, handle, update, etc.
- Type queries: what type is this auto variable?
- Class hierarchies: what implements this interface?

**Note**: Do not issue Grep in parallel as a fallback for structural queries that clangd-cli handles (overrides, callers, references).

## Command examples
```
clangd-cli impact-analysis --file /path/to/file.cpp --line 10 --col 5
clangd-cli describe --file /path/to/file.cpp --line 10 --col 5
clangd-cli goto-definition --file /path/to/file.cpp --line 10 --col 5
clangd-cli hover --file /path/to/file.cpp --line 10 --col 5
clangd-cli file-symbols --file /path/to/file.cpp
clangd-cli workspace-symbols --query MyClass
clangd-cli switch-header-source --file /path/to/file.cpp
```

## Prerequisites
`compile_commands.json` must exist in the project. Auto-detected in project root,
`build/`, `out/Default/`, `out/Release/`, `out/Debug/`, or `.build/`.
For other locations: `clangd-cli --compile-commands-dir <dir> ...`

## Configuration
Project settings in `.clangd-cli.json` (project root): index_file,
compile_commands_dir, clangd_path, timeout, background_index.
Priority: CLI args > .clangd-cli.json > auto-detection.
Run `clangd-cli install` to generate a sample config.

## Daemon lifecycle (IMPORTANT)
The daemon MUST be started before running any command, and stopped when done.

1. Start: `clangd-cli --project-root <project-root> start`
2. Run commands
3. Stop: `clangd-cli --project-root <project-root> stop`

Check the `start` response for `hint` field — it indicates missing index file.

Example session:
```
clangd-cli --project-root /home/user/myproject start
clangd-cli --project-root /home/user/myproject hover --file /home/user/myproject/src/main.cpp --line 10 --col 5
clangd-cli --project-root /home/user/myproject stop
```
