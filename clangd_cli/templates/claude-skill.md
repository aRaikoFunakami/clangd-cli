---
name: clangd-nav
description: Analyze C++ code impact and navigate symbols using clangd semantic analysis
allowed-tools: Bash(clangd-cli *)
---

# C++ Semantic Navigation

`clangd-cli` is a **system-installed CLI tool** (not a script in this skill directory).
Invoke it directly: `clangd-cli <command> [options]`

Use this skill when asked to:
- Analyze impact of modifying a C++ function
- Trace call chains through the codebase
- Find all implementations of a virtual method
- Understand class hierarchies

## Invocation pattern

```
clangd-cli [global-options] <command> --file <absolute-path> --line <N> --col <N> [command-options]
```

- **Global options** (e.g. `--timeout`, `--project-root`) must come **before** the subcommand

- `--file` must be an **absolute path**
- `--line` and `--col` are **0-indexed**
- All arguments are **named** (no positional args)

## Command reference

For full argument details, see [reference.md](reference.md).
For output JSON Schema: `clangd-cli schema --command <name>`

**Before writing code to parse command output**, always run `clangd-cli schema --command <name>` first.
Different fields use different types (e.g. `base_method` is a bare `Location` with only `file`/`line`/`column`, not a full symbol object with `name`).

## Decision flow

### Locate a symbol
- Symbol name is known → **always start with `workspace-symbols --query <name>`** to get exact file/line/col
- Do NOT use Grep to find a symbol's definition location — Grep lacks column info, leading to `--col 0` and slow fallback resolution

### Structural / semantic queries (always use clangd-cli)
- Impact analysis / caller trace → `impact-analysis`
- Symbol overview (type, callers, callees) → `describe`
- Override list for a virtual method → `goto-implementation`
- Type info for auto/template → `describe` or `hover`
- Common names (draw, get, set) → clangd-cli avoids false positives

### Performance tips
- Virtual methods (override, common names like `HandleEvent`) → use `--max-depth 1` or `--no-virtual` initially, expand if needed
- Large codebases → use `--only callers` to skip unnecessary phases

### When to use Grep instead
- Searching text in comments, strings, or disabled code
- Regex pattern searches across the project
- Symbol name is unique and you only need the source text

**Do NOT use Grep as a parallel fallback** for structural queries that clangd-cli handles.
If clangd-cli can answer the question (overrides, callers, references), do not also issue Grep for the same information.
**Do NOT use Grep to locate a symbol's file/line/col** — use `workspace-symbols` instead.

## Handling large output

`impact-analysis` and `describe` can produce large JSON (40KB+).

### 1. `--only` で必要なセクションだけ取得（推奨）

```bash
clangd-cli impact-analysis --file F --line L --col C --only callers
clangd-cli describe --file F --line L --col C --only hover
```

### 2. `jq` で必要なフィールドだけ抽出

```bash
# caller の一覧（人間可読）
clangd-cli impact-analysis ... | jq -r '.callers[] | "\(.name) @ \(.location.file):\(.location.line)"'

# describe の hover テキストだけ
clangd-cli describe ... | jq -r '.hover'
```

### 3. `--compact` で全体のサイズを半減

```bash
clangd-cli --compact impact-analysis --file F --line L --col C
```

**Do not use Read** to view large JSON output directly — pipe through `jq` or use `--only`.

## Daemon lifecycle

- **Do NOT call `start` or `stop` unless the user explicitly asks.** The daemon auto-starts when any command is executed.
- If the user asks to start or stop the daemon, do so.
- If a command returns incomplete results (e.g., empty callers), the index may not be ready yet. Suggest the user run `clangd-cli start --wait` and retry.
