# clangd-cli Command Reference

All position-based commands take `--file <abs-path> --line <N> --col <N>` (0-indexed).

## Global options

Global options **must be placed before the subcommand** (e.g. `clangd-cli --timeout 60 impact-analysis ...`).

| Option | Description |
|--------|-------------|
| `--project-root DIR` | Project root directory (default: cwd) |
| `--index-file PATH` | Path to clangd index file (.idx) |
| `--no-index` | Disable index file |
| `--compile-commands-dir DIR` | Directory containing compile_commands.json |
| `--clangd-path PATH` | Path to clangd binary (default: clangd) |
| `--timeout N` | LSP request timeout in seconds (default: 30) |
| `--index-timeout N` | Timeout for index readiness in seconds (default: 120) |
| `--oneshot` | Run without daemon (spawn clangd per command) |
| `--compact` | Compact JSON output (no indentation) |

## Core analysis commands

### impact-analysis
Recursive caller trace with lambda detection.
```
clangd-cli impact-analysis --file F --line L --col C [options]
```
| Option | Description |
|--------|-------------|
| `--max-depth N` | Maximum BFS depth (default: 5) |
| `--max-nodes N` | Maximum number of caller nodes (default: 100) |
| `--no-virtual` | Skip virtual dispatch exploration (base callers, sibling overrides) |
| `--no-callees` | Skip outgoing callees from root |
| `--only SECTION` | Output only specified section (`callers`\|`callees`\|`virtual-dispatch`). Cannot combine with `--no-*` |

### describe
Symbol overview: type, references, callers, callees.
```
clangd-cli describe --file F --line L --col C [options]
```
| Option | Description |
|--------|-------------|
| `--no-callers` | Skip incoming callers |
| `--no-callees` | Skip outgoing callees |
| `--only SECTIONS` | Output only specified sections (comma-separated: `hover`,`callers`,`callees`,`references`). Cannot combine with `--no-*` |

### workspace-symbols
Search workspace symbols by name. No file/line/col needed.
```
clangd-cli workspace-symbols --query NAME [--limit N]
```

## Navigation commands

All take `--file F --line L --col C` with no extra options (unless noted).

| Command | Description |
|---------|-------------|
| `hover` | Get hover information (type signature, docs) |
| `goto-definition` | Jump to definition |
| `goto-declaration` | Jump to declaration |
| `goto-implementation` | Jump to implementation (virtual method overrides) |
| `goto-type-definition` | Jump to type definition |
| `find-references` | Find all references. Option: `--no-declaration` to exclude declaration |
| `call-hierarchy-in` | Incoming callers (1 level) |
| `call-hierarchy-out` | Outgoing callees (1 level) |
| `type-hierarchy-super` | Supertypes (base classes) |
| `type-hierarchy-sub` | Subtypes (derived classes) |

## File-level commands

| Command | Args | Description |
|---------|------|-------------|
| `file-symbols` | `--file F` | List all symbols in a file (no line/col) |
| `diagnostics` | `--file F --line L --col C` | Get file diagnostics |
| `switch-header-source` | `--file F --line L --col C` | Switch between .h and .cpp |

## Daemon management

| Command | Description |
|---------|-------------|
| `start [--wait]` | Start daemon. `--wait` blocks until index is ready |
| `stop` | Stop daemon |
| `status` | Check if daemon is running |

## Introspection

| Command | Description |
|---------|-------------|
| `schema --command NAME` | Print JSON Schema for a command's output format |
