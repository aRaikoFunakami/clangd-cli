import threading


class DiagnosticsCache:
    def __init__(self, client):
        self._cache = {}
        self._waiters = {}
        self._lock = threading.Lock()
        client.on_notification("textDocument/publishDiagnostics",
                               self._on_diagnostics)

    def _on_diagnostics(self, params: dict):
        uri = params.get("uri", "")
        diagnostics = params.get("diagnostics", [])
        with self._lock:
            self._cache[uri] = diagnostics
            for event in self._waiters.pop(uri, []):
                event.set()

    def get(self, uri: str, timeout: float = 5.0) -> list:
        with self._lock:
            if uri in self._cache:
                return self._cache[uri]
            event = threading.Event()
            self._waiters.setdefault(uri, []).append(event)
        event.wait(timeout=timeout)
        with self._lock:
            return self._cache.get(uri, [])

    def clear(self, uri: str):
        with self._lock:
            self._cache.pop(uri, None)
