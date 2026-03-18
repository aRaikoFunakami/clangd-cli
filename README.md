# clangd-cli

CLI wrapper around clangd's LSP capabilities.

## Install

```bash
git clone https://github.com/aRaikoFunakami/clangd-cli.git
cd clangd-cli
uv tool install -e .
```

## Prerequisites

clangd-cli requires `compile_commands.json` in your project. Generate it for your build system:

```bash
# CMake
cmake -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
# → creates build/compile_commands.json

# Make (using Bear)
bear -- make
# → creates compile_commands.json

# Meson
meson setup build
# → creates build/compile_commands.json
```

clangd-cli auto-detects `compile_commands.json` in the project root, `build/`, `out/Default/`, `out/Release/`, `out/Debug/`, or `.build/`. For other locations, use `--compile-commands`:

```bash
clangd-cli --project-root /path/to/project --compile-commands /path/to/compile_commands.json start
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

## Documentation

- [compile_commands.json 技術資料](docs/compile_commands_json_guide.md)
