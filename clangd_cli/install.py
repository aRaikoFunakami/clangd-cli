"""Generate AI assistant instruction files for clangd-cli usage."""

import json
import os
import stat
import sys
from pathlib import Path

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _read_template(name: str) -> str:
    return (_TEMPLATES_DIR / name).read_text()


FILES = [
    (".claude/rules/cpp-navigation.md", "claude-rules-cpp-nav.md"),
    (".claude/skills/change-impact/SKILL.md", "claude-skill.md"),
    (".claude/skills/change-impact/reference.md", "claude-skill-reference.md"),
    (".claude/skills/change-impact/investigation-workflow.md", "claude-skill-investigation.md"),
    (".claude/hooks/clangd-cli-approve.py", "claude-hook-pretooluse.py"),
    (".github/instructions/cpp-navigation.instructions.md", "copilot-cpp-nav.md"),
]

# Hook script that needs executable permission
EXECUTABLE_FILES = [
    ".claude/hooks/clangd-cli-approve.py",
]

CREATE_IF_MISSING = [
    ("CLAUDE.md", "claude-md-section.md", True),
    (".github/copilot-instructions.md", "copilot-instructions.md", True),
    (".clangd-cli.json", "clangd-cli-config.json", False),
]

# Permissions to add to .claude/settings.local.json
# Note: clangd-cli Bash commands are auto-approved by the PreToolUse hook
# (.claude/hooks/clangd-cli-approve.py) instead of static permission patterns.
CLAUDE_PERMISSIONS = [
    "Bash(jq *)",
    "Bash(date *)",
    "Bash(cat *)",
    "Bash(echo *)",
    "Skill(change-impact)",
    "Skill(change-impact:*)",
]

# PreToolUse hook configuration for .claude/settings.local.json
CLAUDE_HOOK = {
    "matcher": "Bash",
    "hooks": [
        {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/clangd-cli-approve.py",
        }
    ],
}


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
    """Add clangd-cli permissions and hooks to .claude/settings.local.json.

    Returns dict with 'added' (list of new permissions) and 'existed' (already present).
    """
    settings_path = root / ".claude" / "settings.local.json"

    if settings_path.exists():
        settings = json.loads(settings_path.read_text())
    else:
        settings = {}

    dirty = False

    # --- permissions ---
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
        dirty = True

    # --- PreToolUse hook ---
    hooks = settings.setdefault("hooks", {})
    pre_tool_use = hooks.setdefault("PreToolUse", [])

    hook_command = CLAUDE_HOOK["hooks"][0]["command"]
    hook_exists = any(
        any(h.get("command") == hook_command for h in entry.get("hooks", []))
        for entry in pre_tool_use
    )
    if not hook_exists:
        pre_tool_use.append(CLAUDE_HOOK)
        dirty = True

    if dirty:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(settings, indent=2) + "\n")

    result = {"added": added, "existed": existed}
    result["hook_installed"] = not hook_exists
    return result


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
    for rel_path, template_name in FILES:
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_read_template(template_name))
        created.append(rel_path)

    # Make hook scripts executable
    for rel_path in EXECUTABLE_FILES:
        path = root / rel_path
        if path.exists():
            st = path.stat()
            path.chmod(st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # Files that are created only if they don't exist
    for rel_path, template_name, lstrip in CREATE_IF_MISSING:
        path = root / rel_path
        content = _read_template(template_name)
        if lstrip:
            content = content.lstrip()
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
    if settings_result.get("hook_installed"):
        result["hook_installed"] = True

    return result


def _check_claude_settings_needed(root: Path) -> bool:
    """Check if any CLAUDE_PERMISSIONS or hooks are missing from settings."""
    settings_path = root / ".claude" / "settings.local.json"
    if not settings_path.exists():
        return True
    try:
        settings = json.loads(settings_path.read_text())
    except (json.JSONDecodeError, OSError):
        return True

    # Check permissions
    allow_list = settings.get("permissions", {}).get("allow", [])
    if any(perm not in allow_list for perm in CLAUDE_PERMISSIONS):
        return True

    # Check hook
    hook_command = CLAUDE_HOOK["hooks"][0]["command"]
    pre_tool_use = settings.get("hooks", {}).get("PreToolUse", [])
    hook_exists = any(
        any(h.get("command") == hook_command for h in entry.get("hooks", []))
        for entry in pre_tool_use
    )
    return not hook_exists
