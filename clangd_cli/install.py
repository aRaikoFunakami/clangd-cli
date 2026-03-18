"""Generate AI assistant instruction files for clangd-cli usage."""

import json
import sys
from pathlib import Path

CLAUDE_MD_SECTION = """\

## C++ Code Navigation
When working with C++ files, use `clangd-cli` for semantic code navigation
instead of grep for ambiguous symbol names.
See `.claude/rules/cpp-navigation.md` for details.
"""

CLAUDE_RULES_CPP_NAV = """\
---
paths:
  - "**/*.cpp"
  - "**/*.cc"
  - "**/*.h"
  - "**/*.hh"
---

# clangd-cli Usage Guide

## When to use clangd-cli (instead of grep)
- Tracing callers of a function with a common name (draw, get, set, etc.)
- Finding all references to a specific symbol (not just text matches)
- Understanding type hierarchies and virtual dispatch
- Getting type information for auto variables or templates
- Impact analysis before modifying a function signature

## When grep is sufficient
- Searching for unique function/variable names
- Searching in comments, strings, or disabled code
- Pattern-based searches across the project

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
The daemon MUST be started before running any command, and stopped when done.

1. Start the daemon first:
   `clangd-cli --project-root <project-root> start`
2. Run commands (as many as needed):
   `clangd-cli --project-root <project-root> <command> ...`
3. Stop the daemon when finished:
   `clangd-cli --project-root <project-root> stop`

Check if daemon is running: `clangd-cli --project-root <project-root> status`

**Important**: Check the `start` response JSON. If it contains a `hint` field,
it means no index file was found — consider specifying one for better results.

Example session:
```
clangd-cli --project-root /home/user/myproject start
clangd-cli --project-root /home/user/myproject hover --file /home/user/myproject/src/main.cpp --line 10 --col 5
clangd-cli --project-root /home/user/myproject find-references --file /home/user/myproject/src/main.cpp --line 10 --col 5
clangd-cli --project-root /home/user/myproject stop
```

## Named arguments
All commands use named arguments (`--file`, `--line`, `--col`).
Line and column are 0-indexed.

## Commands

### Composite commands (use these first)
- `clangd-cli impact-analysis --file <path> --line <n> --col <n> [--max-depth N] [--max-nodes N] [--include-virtual]`
  — Recursive caller trace with BFS + lambda detection + virtual dispatch
  Example: `clangd-cli impact-analysis --file /path/to/file.cpp --line 10 --col 5 --max-depth 3`
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
- Virtual dispatch: use `impact-analysis --include-virtual` or `type-hierarchy-sub`.
"""

CLAUDE_SKILL = """\
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
1. Need impact analysis / caller trace? → `impact-analysis`
2. Need symbol overview (type, callers, callees)? → `describe`
3. Is the symbol name unique? → grep is faster
4. Is the name common (draw, get, set)? → use clangd-cli
5. Need type info for auto/template? → `describe` or `hover`
6. Need exhaustive caller list? → `impact-analysis`

## Command syntax
All commands use named arguments: `--file <path> --line <n> --col <n>`

Example:
```
clangd-cli --project-root . start
clangd-cli --project-root . impact-analysis --file src/main.cpp --line 10 --col 5
clangd-cli --project-root . describe --file src/main.cpp --line 10 --col 5
clangd-cli --project-root . stop
```

$ARGUMENTS
"""

COPILOT_INSTRUCTIONS = """\
# Project Instructions

## C++ Code Navigation
This project includes `clangd-cli` for semantic C++ code navigation.
Use it instead of grep when dealing with common symbol names or tracing
call hierarchies.

See `.github/instructions/cpp-navigation.instructions.md` for details.
"""

COPILOT_CPP_NAV = """\
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
- Impact analysis: `clangd-cli impact-analysis --file <path> --line <n> --col <n>` — recursive caller trace
- Symbol overview: `clangd-cli describe --file <path> --line <n> --col <n>` — type + callers + callees
- Common names: draw, get, set, create, handle, update, etc.
- Type queries: what type is this auto variable?
- Class hierarchies: what implements this interface?

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
"""

CLANGD_CLI_CONFIG_SAMPLE = """\
{
  "compile_commands_dir": ".",
  "index_file": "",
  "clangd_path": "clangd",
  "timeout": 30,
  "background_index": true
}
"""

_MARKER = "clangd-cli"

FILES = [
    (".claude/rules/cpp-navigation.md", CLAUDE_RULES_CPP_NAV),
    (".claude/skills/clangd-nav/SKILL.md", CLAUDE_SKILL),
    (".github/instructions/cpp-navigation.instructions.md", COPILOT_CPP_NAV),
]

CREATE_IF_MISSING = [
    ("CLAUDE.md", CLAUDE_MD_SECTION.lstrip()),
    (".github/copilot-instructions.md", COPILOT_INSTRUCTIONS.lstrip()),
    (".clangd-cli.json", CLANGD_CLI_CONFIG_SAMPLE),
]

# Permissions to add to .claude/settings.local.json
CLAUDE_PERMISSIONS = [
    "Bash(clangd-cli *)",
    "Skill(clangd-nav)",
    "Skill(clangd-nav:*)",
]


def _indent(text: str, prefix: str) -> str:
    """Add prefix to each line of text."""
    return "\n".join(prefix + line for line in text.splitlines())


def _confirm(prompt: str, default: bool = True) -> bool:
    """Ask user for y/n confirmation. Returns default if non-interactive."""
    suffix = " [Y/n] " if default else " [y/N] "
    if not sys.stdin.isatty():
        return default
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def _update_claude_settings(root: Path) -> dict:
    """Add clangd-cli permissions to .claude/settings.local.json.

    Returns dict with 'added' (list of new permissions) and 'existed' (already present).
    """
    settings_path = root / ".claude" / "settings.local.json"

    if settings_path.exists():
        settings = json.loads(settings_path.read_text())
    else:
        settings = {}

    permissions = settings.setdefault("permissions", {})
    allow_list = permissions.setdefault("allow", [])

    added = []
    existed = []
    for perm in CLAUDE_PERMISSIONS:
        if perm in allow_list:
            existed.append(perm)
        else:
            allow_list.append(perm)
            added.append(perm)

    if added:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(settings, indent=2) + "\n")

    return {"added": added, "existed": existed}


def install_instructions(project_root: str, interactive: bool = False) -> dict:
    """Install AI assistant instruction files into the project.

    Args:
        project_root: Path to the project root directory.
        interactive: If True, prompt user before modifying settings files.
    """
    root = Path(project_root)
    created = []
    skipped = []
    settings_result = {}

    # Files that are always written (overwrite)
    for rel_path, content in FILES:
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        created.append(rel_path)

    # Files that are created only if they don't exist
    for rel_path, content in CREATE_IF_MISSING:
        path = root / rel_path
        if path.exists():
            skipped.append(rel_path)
        else:
            if interactive:
                preview = _indent(content.strip(), "  | ")
                if not _confirm(f"Create {rel_path}?\n{preview}\n"):
                    skipped.append(rel_path)
                    continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            created.append(rel_path)

    # Add permissions to .claude/settings.local.json
    needs_update = _check_claude_settings_needed(root)
    if needs_update:
        do_update = True
        if interactive:
            perms_list = "\n".join(f"  + {p}" for p in CLAUDE_PERMISSIONS)
            do_update = _confirm(
                f"Add to .claude/settings.local.json permissions.allow:\n{perms_list}\n"
            )
        if do_update:
            settings_result = _update_claude_settings(root)
        else:
            settings_result = {"added": [], "skipped": CLAUDE_PERMISSIONS[:]}
    else:
        settings_result = {"added": [], "existed": CLAUDE_PERMISSIONS[:]}

    result = {
        "created": created,
        "skipped": skipped,
    }
    if settings_result.get("added"):
        result["permissions_added"] = settings_result["added"]
    if settings_result.get("existed"):
        result["permissions_existed"] = settings_result["existed"]
    if settings_result.get("skipped"):
        result["permissions_skipped"] = settings_result["skipped"]

    return result


def _check_claude_settings_needed(root: Path) -> bool:
    """Check if any CLAUDE_PERMISSIONS are missing from settings."""
    settings_path = root / ".claude" / "settings.local.json"
    if not settings_path.exists():
        return True
    try:
        settings = json.loads(settings_path.read_text())
    except (json.JSONDecodeError, OSError):
        return True
    allow_list = settings.get("permissions", {}).get("allow", [])
    return any(perm not in allow_list for perm in CLAUDE_PERMISSIONS)
