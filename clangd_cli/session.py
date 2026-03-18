import json
import os
import subprocess
from pathlib import Path

from .lsp_client import LSPClient
from .diagnostics_cache import DiagnosticsCache
from .uri import path_to_uri, get_language_id


def _find_compile_commands(project_root: str) -> str | None:
    candidates = [
        "compile_commands.json",
        "build/compile_commands.json",
        "out/Default/compile_commands.json",
        "out/Release/compile_commands.json",
        "out/Debug/compile_commands.json",
        ".build/compile_commands.json",
    ]
    for candidate in candidates:
        p = Path(project_root) / candidate
        if p.exists():
            return str(p.parent)
    return None


def _find_index_file(project_root: str) -> str | None:
    candidates = [
        "index.idx",
        ".clangd.idx",
        "clangd.idx",
        ".cache/clangd/index.idx",
        "build/index.idx",
    ]
    for candidate in candidates:
        p = Path(project_root) / candidate
        if p.is_file():
            return str(p)
    return None


def _load_config(project_root: str) -> dict:
    p = Path(project_root) / ".clangd-cli.json"
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


class ClangdSession:
    def __init__(self, project_root: str, index_file: str = None,
                 compile_commands_dir: str = None, clangd_path: str = "clangd",
                 timeout: float = 30.0, background_index: bool = True,
                 index_timeout: float = 120.0):
        self.project_root = str(Path(project_root).resolve())
        self._opened_files = set()
        self._index_ready = False

        # Load project config (.clangd-cli.json)
        config = _load_config(self.project_root)

        # 3-tier resolution: CLI arg > config > auto-detect
        if not index_file:
            index_file = config.get("index_file") or None
        if not index_file:
            index_file = _find_index_file(self.project_root)
        if index_file and not os.path.isabs(index_file):
            index_file = str(Path(self.project_root) / index_file)
        self.index_file = index_file

        if not compile_commands_dir:
            compile_commands_dir = config.get("compile_commands_dir") or None
        if not compile_commands_dir:
            compile_commands_dir = _find_compile_commands(self.project_root)
        if compile_commands_dir and not os.path.isabs(compile_commands_dir):
            compile_commands_dir = str(Path(self.project_root) / compile_commands_dir)
        if not compile_commands_dir:
            raise RuntimeError(
                f"compile_commands.json not found under '{self.project_root}'. "
                "Generate it for your build system (e.g. cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON, "
                "bear -- make) or specify --compile-commands-dir."
            )

        if clangd_path == "clangd":
            clangd_path = config.get("clangd_path", clangd_path)
        if timeout == 30.0:
            timeout = config.get("timeout", timeout)
        self.timeout = timeout
        if index_timeout == 120.0:
            index_timeout = config.get("index_timeout", index_timeout)
        self._index_timeout = index_timeout
        if background_index is True:
            background_index = config.get("background_index", background_index)

        args = [clangd_path]
        if index_file:
            args.append(f"--index-file={index_file}")
        if compile_commands_dir:
            args.append(f"--compile-commands-dir={compile_commands_dir}")
        if background_index:
            args.append("--background-index")
        else:
            args.append("--background-index=false")
        args += [
            "--limit-references=1000",
            "--limit-results=1000",
            "--pch-storage=memory",
            "--clang-tidy=false",
            "--log=error",
            "--malloc-trim",
        ]
        self._clangd_args = args

        self._proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.project_root,
        )
        self.client = LSPClient(self._proc)
        self.diagnostics = DiagnosticsCache(self.client)
        self._initialize()

    @property
    def clangd_args(self) -> list:
        return self._clangd_args

    @property
    def opened_files_count(self) -> int:
        return len(self._opened_files)

    @property
    def index_ready(self) -> bool:
        return self._index_ready

    def _initialize(self):
        self.client.request("initialize", {
            "processId": os.getpid(),
            "clientInfo": {"name": "clangd-cli", "version": "1.0.0"},
            "rootUri": path_to_uri(self.project_root),
            "capabilities": {
                "textDocument": {
                    "definition": {"linkSupport": True},
                    "declaration": {"linkSupport": True},
                    "implementation": {"linkSupport": True},
                    "typeDefinition": {"linkSupport": True},
                    "references": {},
                    "hover": {"contentFormat": ["markdown", "plaintext"]},
                    "documentSymbol": {"hierarchicalDocumentSymbolSupport": True},
                    "inlayHint": {},
                    "semanticTokens": {
                        "requests": {"full": True, "range": True},
                        "tokenTypes": [],
                        "tokenModifiers": [],
                    },
                },
                "workspace": {"symbol": {}},
            },
            "initializationOptions": {},
        }, timeout=self.timeout)
        self.client.notify("initialized", {})

    def open_file(self, file_path: str) -> str:
        uri = path_to_uri(file_path)
        if uri in self._opened_files:
            return uri
        content = Path(file_path).read_text(encoding="utf-8", errors="replace")
        lang_id = get_language_id(file_path)
        self.client.notify("textDocument/didOpen", {
            "textDocument": {
                "uri": uri, "languageId": lang_id,
                "version": 1, "text": content,
            }
        })
        self._opened_files.add(uri)
        return uri

    def ensure_index_ready(self):
        """Wait until the index is loaded, polling with workspace/symbol queries."""
        if self._index_ready:
            return
        if self.index_file is None:
            return

        import time
        import sys

        deadline = time.monotonic() + self._index_timeout
        poll_interval = 2.0
        sys.stderr.write("Waiting for index to be ready...\n")
        sys.stderr.flush()

        while time.monotonic() < deadline:
            try:
                result = self.client.request("workspace/symbol", {
                    "query": "_",
                }, timeout=min(10.0, self._index_timeout))
                if result and len(result) > 0:
                    self._index_ready = True
                    sys.stderr.write("Index ready.\n")
                    sys.stderr.flush()
                    return
            except Exception:
                pass
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(poll_interval, remaining))

        sys.stderr.write(
            f"Warning: index readiness timeout ({self._index_timeout}s). "
            "Proceeding anyway — results may be incomplete.\n"
        )
        sys.stderr.flush()

    def shutdown(self):
        try:
            self.client.request("shutdown", timeout=5.0)
            self.client.notify("exit")
        except Exception:
            pass
        try:
            self._proc.terminate()
            self._proc.wait(timeout=3)
        except Exception:
            self._proc.kill()
        if self.client._reader_thread.is_alive():
            self.client._reader_thread.join(timeout=2.0)
