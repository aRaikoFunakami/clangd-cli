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


class ClangdSession:
    def __init__(self, project_root: str, index_file: str = None,
                 compile_commands_dir: str = None, clangd_path: str = "clangd",
                 timeout: float = 30.0, background_index: bool = True):
        self.project_root = str(Path(project_root).resolve())
        self.timeout = timeout
        self._opened_files = set()

        if not compile_commands_dir:
            compile_commands_dir = _find_compile_commands(self.project_root)

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
