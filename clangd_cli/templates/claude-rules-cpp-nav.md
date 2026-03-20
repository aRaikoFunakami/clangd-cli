---
paths:
  - "**/*.cpp"
  - "**/*.cc"
  - "**/*.h"
  - "**/*.hh"
---

# clangd-cli Usage Guide

## Required workflow for C++ symbol investigation

```
1. clangd-cli workspace-symbols --query "Name"          # ALWAYS start here
2. clangd-cli impact-analysis --file F --line L --col C  # trace callers/callees
3. Only if gaps remain, supplement with Grep              # text/comment search only
```

**Do NOT start with Grep** to locate symbols — Grep lacks column info, leading to `--col 0` and slow fallback resolution.
**Do NOT use Grep** to duplicate information that clangd-cli provides (overrides, callers, references).

**Always check `--help` before running a command you are unsure about.**

```
clangd-cli --help                        # list all commands and global options
clangd-cli <command> --help              # show command-specific arguments
clangd-cli schema --command <name>       # JSON Schema of command output
```

**Global options** (`--timeout`, `--project-root`, etc.) **must come before the subcommand**:
`clangd-cli [global-options] <command> [command-options]`

## When to use clangd-cli (instead of grep)
- Tracing callers of a function (especially common names) → `impact-analysis`
- Finding all references to a specific symbol → `find-references`
- Understanding type hierarchies and virtual dispatch → `type-hierarchy-*`, `impact-analysis`
- Getting type information for auto variables or templates → `describe`, `hover`
- Impact analysis before modifying a function signature → `impact-analysis`
- Structured impact investigation (影響範囲調査) → invoke change-impact skill, follow investigation-workflow.md

### Performance tips
- Virtual methods (override, common names like `HandleEvent`) → use `--max-depth 1` or `--no-virtual` initially, expand if needed
- Large codebases → use `--only callers` to skip unnecessary phases

## Prerequisites
`compile_commands.json` must exist in the project. clangd-cli auto-detects it
in the project root, `build/`, `out/Default/`, `out/Release/`, `out/Debug/`,
or `.build/`. For other locations, use `--compile-commands-dir`.

## Configuration (.clangd-cli.json)
Project-level settings can be configured in `.clangd-cli.json` at the project root.
Run `clangd-cli install` to generate a sample config.
Priority: CLI arguments > .clangd-cli.json > auto-detection.

## Daemon lifecycle (IMPORTANT)
- **Do NOT call `start` or `stop` unless the user explicitly asks.** The daemon auto-starts when any command is executed.
- If the user asks to start the daemon, use `clangd-cli start` (**without** `--wait`). The `--wait` flag blocks for up to 2 minutes and will cause the tool to hang.
- If a command returns incomplete results (e.g., empty callers), the index may not be ready yet. Suggest the user run `clangd-cli start --wait` in their terminal and retry.
