#!/usr/bin/env python3
"""PreToolUse hook: auto-approve clangd-cli read-only commands.

Decision logic for commands starting with 'clangd-cli':
  - allow: no pipes, or pipes only to SAFE_PIPE_TARGETS
  - deny:  dangerous operators (&&, ||, ;, $(), backticks),
           or pipes to DANGEROUS_COMMANDS
  - ask:   pipes to unknown commands (not safe, not dangerous)
"""

import json
import sys

SAFE_PIPE_TARGETS = frozenset(
    {"jq", "head", "grep", "wc", "sort", "tee", "cat", "less"}
)

DANGEROUS_COMMANDS = frozenset(
    {"sh", "bash", "zsh", "fish", "dash", "csh", "ksh",
     "rm", "rmdir", "mv", "dd", "mkfs", "fdisk",
     "python", "python3", "perl", "ruby", "node",
     "curl", "wget", "nc", "ncat", "exec", "eval", "xargs"}
)


def _split_pipes(command: str) -> list[str] | None:
    """Split command on unquoted pipe characters.

    Returns list of pipe segments, or None if dangerous operators are found.
    """
    segments: list[str] = []
    current: list[str] = []
    quote: str | None = None
    i = 0
    n = len(command)

    while i < n:
        c = command[i]

        if quote:
            current.append(c)
            if c == quote:
                quote = None
        elif c in ('"', "'"):
            current.append(c)
            quote = c
        elif c == "|":
            if i + 1 < n and command[i + 1] == "|":
                return None  # || operator
            segments.append("".join(current))
            current = []
        elif c == "&":
            if i + 1 < n and command[i + 1] == "&":
                return None  # && operator
            # Single & after > is redirect (2>&1), otherwise pass through
            current.append(c)
        elif c == ";":
            return None  # command separator
        elif c == "`":
            return None  # backtick substitution
        elif c == "$" and i + 1 < n and command[i + 1] == "(":
            return None  # $() substitution
        else:
            current.append(c)
        i += 1

    segments.append("".join(current))
    return segments


def _classify_clangd_command(command: str) -> tuple[str, str]:
    """Classify a clangd-cli command as allow/deny/ask.

    Returns (decision, reason) tuple.
    """
    segments = _split_pipes(command)

    # Dangerous operators detected (&&, ||, ;, $(), backticks)
    if segments is None:
        return ("deny", "dangerous shell operators in clangd-cli command")

    if not segments:
        return ("deny", "empty command")

    # First segment must start with 'clangd-cli'
    first = segments[0].strip()
    if not first.startswith("clangd-cli"):
        return ("deny", "first command is not clangd-cli")
    rest = first[len("clangd-cli"):]
    if rest and not rest[0].isspace():
        return ("deny", "first command is not clangd-cli")

    # No pipes — safe
    if len(segments) == 1:
        return ("allow", "clangd-cli read-only command")

    # Check each pipe target
    for seg in segments[1:]:
        words = seg.strip().split()
        if not words:
            return ("deny", "empty pipe segment")
        cmd = words[0]
        if cmd in SAFE_PIPE_TARGETS:
            continue
        if cmd in DANGEROUS_COMMANDS:
            return ("deny", f"dangerous pipe target: {cmd}")
        return ("ask", f"unknown pipe target: {cmd}")

    return ("allow", "clangd-cli read-only command")


def main() -> None:
    hook_input = json.load(sys.stdin)

    if hook_input.get("tool_name") != "Bash":
        return

    command = hook_input.get("tool_input", {}).get("command", "")

    # Only handle commands that start with clangd-cli
    stripped = command.lstrip()
    if not stripped.startswith("clangd-cli"):
        return
    rest = stripped[len("clangd-cli"):]
    if rest and not rest[0].isspace():
        return  # e.g. 'clangd-clix', not our concern

    decision, reason = _classify_clangd_command(command)

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
