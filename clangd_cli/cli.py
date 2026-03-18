import argparse
import json
import sys
from pathlib import Path

from .session import ClangdSession
from .commands import COMMAND_MAP
from .daemon import (daemon_start, daemon_stop, daemon_status, daemon_is_alive,
                     daemon_wait_ready, run_via_daemon)
from .install import install_instructions


def _add_pos(parser):
    parser.add_argument("--file", required=True, help="Absolute path to the source file")
    parser.add_argument("--line", type=int, required=True, help="Line number (0-indexed)")
    parser.add_argument("--col", type=int, required=True, dest="column",
                        help="Column number (0-indexed)")


def _add_file(parser):
    parser.add_argument("--file", required=True, help="Absolute path to the source file")


_DESCRIPTION = """\
CLI wrapper around clangd LSP capabilities.

Daemon lifecycle (daemon auto-starts when running commands):
  clangd-cli --project-root <dir> <command> --file <path> --line <n> --col <n>
  clangd-cli --project-root <dir> stop
  Or explicitly: clangd-cli --project-root <dir> start [--wait]

Named arguments (--file, --line, --col can be in any order):
  --file   absolute path to the source file
  --line   line number (0-indexed)
  --col    column number (0-indexed)

Configuration (optional):
  Place .clangd-cli.json in the project root to configure defaults:
  {
    "index_file": "index.idx",
    "compile_commands_dir": ".",
    "clangd_path": "clangd",
    "timeout": 30,
    "background_index": true,
    "index_timeout": 120
  }
  Priority: CLI arguments > .clangd-cli.json > auto-detection.
  Run 'clangd-cli install' to generate a sample config.

Example session:
  clangd-cli --project-root /home/user/proj start
  clangd-cli --project-root /home/user/proj hover --file /home/user/proj/src/main.cpp --line 10 --col 5
  clangd-cli --project-root /home/user/proj impact-analysis --file /home/user/proj/src/main.cpp --line 10 --col 5
  clangd-cli --project-root /home/user/proj stop
"""


def build_parser():
    parser = argparse.ArgumentParser(
        description=_DESCRIPTION,
        prog="clangd-cli",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--project-root", default=".",
                        help="Project root directory (default: cwd)")
    parser.add_argument("--index-file",
                        help="Path to clangd index file (.idx). "
                             "Also configurable in .clangd-cli.json or auto-detected.")
    parser.add_argument("--no-index", action="store_true",
                        help="Disable index file (skip auto-detection and config)")
    parser.add_argument("--compile-commands-dir",
                        help="Directory containing compile_commands.json")
    parser.add_argument("--clangd-path", default="clangd",
                        help="Path to clangd binary (default: clangd)")
    parser.add_argument("--timeout", type=float, default=30.0,
                        help="LSP request timeout in seconds (default: 30)")
    parser.add_argument("--index-timeout", type=float, default=120.0,
                        help="Timeout in seconds for index readiness (default: 120)")
    parser.add_argument("--oneshot", action="store_true",
                        help="Run without daemon (spawn clangd per command)")

    sub = parser.add_subparsers(dest="command", required=True)

    # Daemon lifecycle
    p = sub.add_parser("start", help="Start clangd daemon in background")
    p.add_argument("--wait", action="store_true",
                   help="Wait until index is ready before returning")
    sub.add_parser("stop", help="Stop clangd daemon")
    sub.add_parser("status", help="Check if daemon is running")

    # Install AI assistant instructions
    p = sub.add_parser("install",
                       help="Install Claude Code / GitHub Copilot instruction files")
    p.add_argument("-y", "--yes", action="store_true",
                   help="Skip confirmation prompts (non-interactive mode)")

    # Analysis
    p = sub.add_parser("hover", help="Get hover information")
    _add_pos(p)

    p = sub.add_parser("diagnostics", help="Get file diagnostics")
    _add_file(p)

    p = sub.add_parser("inlay-hints", help="Get inlay hints")
    _add_file(p)
    p.add_argument("--range", help="Line range START:END (0-indexed)")

    p = sub.add_parser("semantic-tokens", help="Get semantic tokens")
    _add_file(p)
    p.add_argument("--range", help="Line range START:END (0-indexed)")

    p = sub.add_parser("ast", help="Get AST node at position")
    _add_pos(p)
    p.add_argument("--depth", type=int, help="Max depth of AST children")

    # Navigation
    for name in ["goto-definition", "goto-declaration",
                  "goto-implementation", "goto-type-definition"]:
        p = sub.add_parser(name, help=f"{name.replace('-', ' ').title()}")
        _add_pos(p)

    p = sub.add_parser("find-references", help="Find all references")
    _add_pos(p)
    p.add_argument("--no-declaration", action="store_true",
                   help="Exclude declaration from results")

    p = sub.add_parser("switch-header-source",
                       help="Switch between header and source file")
    _add_file(p)

    # Symbols
    p = sub.add_parser("file-symbols", help="List document symbols")
    _add_file(p)

    p = sub.add_parser("workspace-symbols", help="Search workspace symbols")
    p.add_argument("--query", required=True, help="Symbol search query")
    p.add_argument("--limit", type=int, default=100)

    for name in ["call-hierarchy-in", "call-hierarchy-out",
                  "type-hierarchy-super", "type-hierarchy-sub"]:
        p = sub.add_parser(name, help=f"{name.replace('-', ' ').title()}")
        _add_pos(p)

    # Structure
    p = sub.add_parser("highlight-symbol", help="Get document highlights")
    _add_pos(p)

    p = sub.add_parser("document-links", help="Get document links")
    _add_file(p)

    # Composite
    p = sub.add_parser("impact-analysis",
                       help="Recursive caller trace with lambda detection")
    _add_pos(p)
    p.add_argument("--max-depth", type=int, default=5,
                   help="Maximum BFS depth (default: 5)")
    p.add_argument("--max-nodes", type=int, default=100,
                   help="Maximum number of caller nodes (default: 100)")
    p.add_argument("--no-virtual", action="store_true",
                   help="Skip virtual dispatch exploration (base callers, sibling overrides)")
    p.add_argument("--no-callees", action="store_true",
                   help="Skip outgoing callees from root")

    p = sub.add_parser("describe",
                       help="Symbol overview: type, references, callers, callees")
    _add_pos(p)
    p.add_argument("--no-callers", action="store_true",
                   help="Skip incoming callers")
    p.add_argument("--no-callees", action="store_true",
                   help="Skip outgoing callees")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    project_root = str(Path(args.project_root).resolve())

    # Daemon lifecycle commands
    if args.command == "start":
        result = daemon_start(project_root, args)
        if getattr(args, "wait", False) and result.get("status") in ("started", "already_running"):
            sys.stderr.write("Waiting for index to be ready...\n")
            sys.stderr.flush()
            wait_result = daemon_wait_ready(project_root, args.index_timeout)
            result["index_ready"] = wait_result.get("index_ready", False)
            if result["index_ready"]:
                sys.stderr.write("Index ready.\n")
                sys.stderr.flush()
            else:
                sys.stderr.write("Warning: index readiness timeout. Proceeding anyway.\n")
                sys.stderr.flush()
        print(json.dumps(result))
        return

    if args.command == "stop":
        result = daemon_stop(project_root)
        print(json.dumps(result))
        return

    if args.command == "status":
        result = daemon_status(project_root)
        print(json.dumps(result, indent=2))
        return

    if args.command == "install":
        interactive = not args.yes
        result = install_instructions(project_root, interactive=interactive)
        print(json.dumps(result, indent=2))
        return

    # LSP commands
    if args.oneshot:
        session = None
        try:
            session = ClangdSession(
                project_root=project_root,
                index_file=args.index_file,
                compile_commands_dir=args.compile_commands_dir,
                clangd_path=args.clangd_path,
                timeout=args.timeout,
                index_timeout=args.index_timeout,
                no_index=args.no_index,
            )
            session.ensure_index_ready()
            result = COMMAND_MAP[args.command](session, args)
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(json.dumps({"error": True, "message": str(e)}), file=sys.stderr)
            sys.exit(1)
        finally:
            if session:
                session.shutdown()
    else:
        # Auto-start daemon if not running
        if not daemon_is_alive(project_root):
            sys.stderr.write("Daemon not running. Starting automatically...\n")
            sys.stderr.flush()
            start_result = daemon_start(project_root, args)
            if start_result.get("status") not in ("started", "already_running"):
                print(json.dumps({"error": True,
                                   "message": f"Failed to auto-start daemon: {start_result}"}),
                      file=sys.stderr)
                sys.exit(1)
        try:
            result = run_via_daemon(project_root, args.command, args)
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(json.dumps({"error": True, "message": str(e)}), file=sys.stderr)
            sys.exit(1)
