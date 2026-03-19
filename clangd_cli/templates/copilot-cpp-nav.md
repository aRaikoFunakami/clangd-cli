---
applyTo: "**/*.{cpp,cc,h,hh}"
---

# clangd-cli for C++ Navigation

**Always check `--help` before running a command you are unsure about.**

```
clangd-cli --help                        # list all commands and global options
clangd-cli <command> --help              # show command-specific arguments
clangd-cli schema --command <name>       # JSON Schema of command output
```

**Global options** (`--timeout`, `--project-root`, etc.) **must come before the subcommand**:
`clangd-cli [global-options] <command> [command-options]`

## When to use (instead of grep)
- **Locate a symbol → always start with `workspace-symbols --query <name>`** to get exact file/line/col. Do NOT use Grep for this — Grep lacks column info, leading to `--col 0` and slow fallback resolution.
- Impact analysis: `impact-analysis` — recursive caller trace + callees + virtual dispatch
- Override list: `goto-implementation` — find all overrides of a virtual method
- Symbol overview: `describe` — type + callers + callees
- Common names: draw, get, set, create, handle, update, etc.
- Type queries: what type is this auto variable?
- Class hierarchies: what implements this interface?

**Do not issue Grep in parallel as a fallback** for structural queries that clangd-cli handles.

### Performance tips
- Virtual methods (override, common names like `HandleEvent`) → use `--max-depth 1` or `--no-virtual` initially, expand if needed
- Large codebases → use `--only callers` to skip unnecessary phases

## Prerequisites
`compile_commands.json` must exist in the project. Auto-detected in project root,
`build/`, `out/Default/`, `out/Release/`, `out/Debug/`, or `.build/`.
For other locations, use `--compile-commands-dir`.

## Configuration
Project settings in `.clangd-cli.json` (project root).
Run `clangd-cli install` to generate a sample config.
Priority: CLI args > .clangd-cli.json > auto-detection.

## Daemon lifecycle (IMPORTANT)
- **Do NOT call `start` or `stop` unless the user explicitly asks.** The daemon auto-starts when any command is executed.
- If the user asks to start or stop the daemon, do so.
- If a command returns incomplete results (e.g., empty callers), the index may not be ready yet. Suggest the user run `clangd-cli start --wait` and retry.
