---
paths:
  - "**/*.cpp"
  - "**/*.cc"
  - "**/*.h"
  - "**/*.hh"
---

# clangd-cli Usage Guide

**Always check `--help` before running a command you are unsure about.**

```
clangd-cli --help                        # list all commands and global options
clangd-cli <command> --help              # show command-specific arguments
clangd-cli schema --command <name>       # JSON Schema of command output
```

**Global options** (`--timeout`, `--project-root`, etc.) **must come before the subcommand**:
`clangd-cli [global-options] <command> [command-options]`

## When to use clangd-cli (instead of grep)
- Locating a symbol by name → `workspace-symbols`
- Tracing callers of a function (especially common names) → `impact-analysis`
- Finding all references to a specific symbol → `find-references`
- Understanding type hierarchies and virtual dispatch → `type-hierarchy-*`, `impact-analysis`
- Getting type information for auto variables or templates → `describe`, `hover`
- Impact analysis before modifying a function signature → `impact-analysis`

### Recommended workflow
1. **`workspace-symbols --query <name>`** — always the first step to get exact file/line/col for any known symbol name
2. `impact-analysis` or `goto-implementation` — use the exact location from step 1
3. Only if gaps remain, supplement with Grep

**Do NOT** use Grep to find a symbol's definition location — Grep lacks column info, leading to `--col 0` and slow fallback resolution.
**Do NOT** use Grep to duplicate information that clangd-cli provides (overrides, callers, references).

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
- If the user asks to start or stop the daemon, do so.
- If a command returns incomplete results (e.g., empty callers), the index may not be ready yet. Suggest the user run `clangd-cli start --wait` and retry.
