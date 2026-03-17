import json
import threading

from .errors import LSPTimeoutError, LSPError


class LSPClient:
    def __init__(self, proc):
        self._proc = proc
        self._stdin = proc.stdin
        self._stdout = proc.stdout
        self._next_id = 1
        self._id_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._pending = {}
        self._pending_lock = threading.Lock()
        self._notification_handlers = {}
        self._notification_lock = threading.Lock()
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def _send(self, msg: dict):
        body = json.dumps(msg).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        with self._write_lock:
            self._stdin.write(header + body)
            self._stdin.flush()

    def _recv(self) -> dict:
        headers = {}
        while True:
            line = self._stdout.readline()
            if not line:
                raise ConnectionError("clangd stdout closed unexpectedly")
            line = line.decode("ascii", errors="replace").strip()
            if line == "":
                break
            if ":" in line:
                key, val = line.split(":", 1)
                headers[key.strip()] = val.strip()
        content_length = int(headers.get("Content-Length", 0))
        if content_length == 0:
            raise ConnectionError("Missing Content-Length header")
        body = b""
        while len(body) < content_length:
            chunk = self._stdout.read(content_length - len(body))
            if not chunk:
                raise ConnectionError("clangd stdout closed while reading body")
            body += chunk
        return json.loads(body.decode("utf-8"))

    def _reader_loop(self):
        try:
            while True:
                msg = self._recv()
                if "id" in msg and ("result" in msg or "error" in msg):
                    self._dispatch_response(msg)
                elif "method" in msg and "id" not in msg:
                    self._dispatch_notification(msg)
        except (ConnectionError, OSError):
            self._reject_all_pending("clangd connection closed")

    def _dispatch_response(self, msg: dict):
        req_id = msg["id"]
        with self._pending_lock:
            entry = self._pending.get(req_id)
        if entry is None:
            return
        if "error" in msg:
            entry["error"] = msg["error"]
        else:
            entry["result"] = msg.get("result")
        entry["event"].set()

    def _dispatch_notification(self, msg: dict):
        method = msg.get("method", "")
        params = msg.get("params")
        with self._notification_lock:
            handlers = list(self._notification_handlers.get(method, []))
        for handler in handlers:
            try:
                handler(params)
            except Exception:
                pass

    def _reject_all_pending(self, reason: str):
        with self._pending_lock:
            for entry in self._pending.values():
                entry["error"] = {"code": -1, "message": reason}
                entry["event"].set()

    def on_notification(self, method: str, handler):
        with self._notification_lock:
            self._notification_handlers.setdefault(method, []).append(handler)

    def request(self, method: str, params: dict = None, timeout: float = 30.0) -> dict:
        with self._id_lock:
            req_id = self._next_id
            self._next_id += 1
        msg = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            msg["params"] = params

        event = threading.Event()
        entry = {"event": event, "result": None, "error": None}
        with self._pending_lock:
            self._pending[req_id] = entry

        self._send(msg)

        if not event.wait(timeout=timeout):
            with self._pending_lock:
                self._pending.pop(req_id, None)
            raise LSPTimeoutError(
                f"LSP request '{method}' timed out after {timeout}s")

        with self._pending_lock:
            self._pending.pop(req_id, None)

        if entry["error"] is not None:
            err = entry["error"]
            raise LSPError(
                code=err.get("code"),
                message=err.get("message", "Unknown LSP error"),
                data=err.get("data"),
            )
        return entry["result"]

    def notify(self, method: str, params: dict = None):
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self._send(msg)
