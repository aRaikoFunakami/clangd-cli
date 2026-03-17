# clangd-cli

CLI wrapper around clangd's LSP capabilities.

## Install

```bash
uv tool install clangd-cli
```

Or from source:

```bash
git clone https://github.com/aRaikoFunakami/clangd-cli.git
cd clangd-cli
uv tool install -e .
```

## Usage

```bash
# Start daemon (fast - clangd stays running)
clangd-cli --project-root /path/to/project start
clangd-cli --project-root /path/to/project hover --file /path/to/file.cpp --line 10 --col 5
clangd-cli --project-root /path/to/project stop

# One-shot mode (no setup needed)
clangd-cli --oneshot hover --file /path/to/file.cpp --line 10 --col 5
```

All `--line` / `--col` values are 0-indexed (matching LSP protocol).

## Install AI assistant instructions

Generate Claude Code and GitHub Copilot instruction files for a C++ project:

```bash
clangd-cli --project-root /path/to/project install
```
