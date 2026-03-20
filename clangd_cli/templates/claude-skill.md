---
name: change-impact
description: Analyze C++ code impact, trace callers, find virtual method overrides, and navigate symbols using clangd semantic analysis. Use when asked to understand call chains, analyze modification impact, find implementations of an interface, resolve type hierarchies, or conduct structured impact investigation (影響範囲調査) in C++ codebases.
allowed-tools: Bash(clangd-cli *), Bash(jq *), Bash(date *), Bash(cat *), Bash(echo *)
---

# C++ Semantic Navigation

`clangd-cli` is a **system-installed CLI tool** (not a script in this skill directory).
Invoke it directly: `clangd-cli <command> [options]`

Use this skill when asked to:
- Analyze impact of modifying a C++ function
- Trace call chains through the codebase
- Find all implementations of a virtual method
- Understand class hierarchies
- Conduct structured impact investigation for a C++ code change (影響範囲調査)
- Generate an impact analysis report (影響範囲調査報告書)

## Quick start

```bash
# 1. Find the symbol's exact location
clangd-cli workspace-symbols --query "HandleEvent"

# 2. Comprehensive investigation (callers, callees, virtual dispatch, type hierarchy)
clangd-cli investigate --file /abs/path/handler.cpp --line 42 --col 8

# 3. Or use targeted commands for specific needs
clangd-cli impact-analysis --file /abs/path/handler.cpp --line 42 --col 8
clangd-cli describe --file /abs/path/handler.cpp --line 42 --col 8 --only hover,callers

# 4. Find all overrides of a virtual method
clangd-cli goto-implementation --file /abs/path/handler.h --line 15 --col 16
```

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
- Comprehensive investigation (callers + callees + virtual dispatch + type hierarchy + caller details):
  `clangd-cli investigate --file F --line L --col C`
- Impact analysis / caller trace:
  `clangd-cli impact-analysis --file F --line L --col C`
- Symbol overview (type, callers, callees):
  `clangd-cli describe --file F --line L --col C`
- Override list for a virtual method:
  `clangd-cli goto-implementation --file F --line L --col C`
- Type info for auto/template:
  `clangd-cli hover --file F --line L --col C`
- Common names (draw, get, set) → clangd-cli avoids false positives that Grep would produce

### Performance tips
- **Parallel execution**: clangd-cli is daemon-based — independent commands can run concurrently. When multiple queries have no data dependency, issue them in parallel (e.g., multiple `workspace-symbols` lookups, or `hover` + `find-references` on different symbols).
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

**Before writing a `jq` filter**, run `clangd-cli schema --command <name>` to confirm field names and types. Do not assume fields exist based on other commands' output.

```bash
# caller の一覧（人間可読）
clangd-cli impact-analysis ... | jq -r '.callers[] | "\(.name) @ \(.location.file):\(.location.line)"'

# describe の hover テキストだけ
clangd-cli describe ... | jq -r '.hover'
```

#### `investigate` の大量出力を処理するパターン

`investigate` は全データを一括取得するため、出力が50KB以上になることがある。ファイルに保存してから `jq` で段階的に抽出する：

```bash
# ファイルに保存して規模を確認
clangd-cli investigate --file F --line L --col C > investigation-data.json
jq '.stats' investigation-data.json

# caller数を確認
jq '.callers | length' investigation-data.json

# depth=1のcallerだけ抽出
jq '[.callers[] | select(.depth == 1)]' investigation-data.json

# callerを1件ずつ取得
jq '.callers[0]' investigation-data.json

# caller_detailsを1件ずつ取得（hover + callees）
jq '.caller_details[0]' investigation-data.json
```

### 3. `--compact` で全体のサイズを半減

```bash
clangd-cli --compact impact-analysis --file F --line L --col C
```

**Do not use Read** to view large JSON output directly — pipe through `jq` or use `--only`.

## Structured impact investigation (影響範囲調査)

When asked to perform a structured impact analysis or generate an impact report:
→ Follow the workflow in [investigation-workflow.md](investigation-workflow.md)

Scope: 区分A (code dependency) + 区分B (C++ specific) only.
Out of scope: 区分C (non-code impact), report item 7 (retest targets).

## Examples

### Analyze function impact

```bash
# Find the function
clangd-cli workspace-symbols --query "ProcessRequest"
# Use the location from the result
clangd-cli impact-analysis --file /src/server.cpp --line 120 --col 6
# Extract just the caller names
clangd-cli impact-analysis --file /src/server.cpp --line 120 --col 6 --only callers \
  | jq -r '.callers[] | "\(.name) @ \(.location.file):\(.location.line)"'
```

### Investigate virtual method dispatch

```bash
# Find the virtual method
clangd-cli workspace-symbols --query "OnMessage"
# List all overrides
clangd-cli goto-implementation --file /src/handler.h --line 25 --col 18
# Analyze callers without following virtual dispatch (faster)
clangd-cli impact-analysis --file /src/handler.h --line 25 --col 18 --no-virtual --only callers
```

## Daemon lifecycle

- **Do NOT call `start` or `stop` unless the user explicitly asks.** The daemon auto-starts when any command is executed.
- If the user asks to start the daemon, use `clangd-cli start` (**without** `--wait`). The `--wait` flag blocks for up to 2 minutes and will cause the tool to hang.
- If a command returns incomplete results (e.g., empty callers), the index may not be ready yet. Suggest the user run `clangd-cli start --wait` in their terminal and retry.
