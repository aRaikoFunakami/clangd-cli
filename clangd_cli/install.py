"""Generate AI assistant instruction files for clangd-cli usage."""

import json
import sys
from pathlib import Path

_TEMPLATES_DIR = Path(__file__).parent / "templates"

_SKILL_SCHEMA_COMMANDS: list[str] = []


def _read_template(name: str) -> str:
    return (_TEMPLATES_DIR / name).read_text()


def _generate_schema_doc() -> str:
    """Generate output schema documentation for embedding in skill files."""
    from .models import get_command_schemas

    schemas = get_command_schemas()
    lines = [
        "## Output schemas",
        "",
        "Get JSON Schema for all commands: `clangd-cli schema`",
        "Get schema for a specific command: `clangd-cli schema --command <name>`",
    ]
    for cmd_name in _SKILL_SCHEMA_COMMANDS:
        if cmd_name in schemas:
            lines.append("")
            lines.append(f"### `{cmd_name}`")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(schemas[cmd_name], indent=2))
            lines.append("```")
    lines.append("")
    return "\n".join(lines)


FILES = [
    (".claude/rules/cpp-navigation.md", "claude-rules-cpp-nav.md"),
    (".claude/skills/clangd-nav/SKILL.md", "claude-skill.md"),
    (".github/instructions/cpp-navigation.instructions.md", "copilot-cpp-nav.md"),
]

CREATE_IF_MISSING = [
    ("CLAUDE.md", "claude-md-section.md", True),
    (".github/copilot-instructions.md", "copilot-instructions.md", True),
    (".clangd-cli.json", "clangd-cli-config.json", False),
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

    # Generate schema documentation for $ARGUMENTS substitution
    schema_doc = _generate_schema_doc()

    # Files that are always written (overwrite)
    for rel_path, template_name in FILES:
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        content = _read_template(template_name)
        content = content.replace("$ARGUMENTS", schema_doc)
        path.write_text(content)
        created.append(rel_path)

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
