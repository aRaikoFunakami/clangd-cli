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
clangd-cli start
clangd-cli hover FILE LINE COL
clangd-cli stop

# One-shot mode (no setup needed)
clangd-cli --oneshot hover FILE LINE COL
```

All line/column numbers are 0-indexed (matching LSP protocol).
