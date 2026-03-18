import argparse
import hashlib
import json
import os
import signal
import socket
import sys
import threading
import time
from pathlib import Path

from .session import ClangdSession, _find_compile_commands, _find_index_file, _load_config
from .errors import LSPError, LSPTimeoutError
from .commands import COMMAND_MAP


def _tmp_path(project_root: str, suffix: str) -> str:
    h = hashlib.sha256(str(Path(project_root).resolve()).encode()).hexdigest()[:12]
    return f"/tmp/clangd-cli-{h}.{suffix}"


def _socket_path(project_root: str) -> str:
    return _tmp_path(project_root, "sock")


def _pid_path(project_root: str) -> str:
    return _tmp_path(project_root, "pid")


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Socket closed")
        buf += chunk
    return buf


def _send_to_socket(sock_path: str, request: dict) -> dict:
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(300)
    client.connect(sock_path)
    try:
        payload = json.dumps(request).encode("utf-8")
        client.sendall(len(payload).to_bytes(4, "big") + payload)
        length_bytes = _recv_exact(client, 4)
        resp_length = int.from_bytes(length_bytes, "big")
        resp_bytes = _recv_exact(client, resp_length)
        return json.loads(resp_bytes.decode("utf-8"))
    finally:
        client.close()


def _handle_connection(conn: socket.socket, session: ClangdSession,
                       shutdown_flag: threading.Event):
    conn.settimeout(300)
    length_bytes = _recv_exact(conn, 4)
    req_length = int.from_bytes(length_bytes, "big")
    req_bytes = _recv_exact(conn, req_length)
    request = json.loads(req_bytes.decode("utf-8"))

    cmd = request.get("command")
    if cmd == "stop":
        response = {"status": "stopping"}
        shutdown_flag.set()
    elif cmd == "ping":
        response = {
            "status": "ok", "pid": os.getpid(),
            "clangd_args": session.clangd_args,
            "opened_files": session.opened_files_count,
            "index_file": session.index_file,
            "index_ready": session.index_ready,
        }
    elif cmd in COMMAND_MAP:
        session.ensure_index_ready()
        cmd_args = argparse.Namespace(**request.get("args", {}))
        try:
            handler = COMMAND_MAP[cmd]
            response = handler(session, cmd_args)
        except LSPError as e:
            response = {"error": True, "message": str(e), "code": e.code}
            if e.data is not None:
                response["data"] = e.data
        except LSPTimeoutError as e:
            response = {"error": True, "message": str(e), "timeout": True}
        except Exception as e:
            response = {"error": True, "message": str(e)}
    else:
        response = {"error": True, "message": f"Unknown command: {cmd}"}

    payload = json.dumps(response).encode("utf-8")
    conn.sendall(len(payload).to_bytes(4, "big") + payload)


def daemon_main(project_root: str, index_file: str, compile_commands_dir: str,
                clangd_path: str, timeout: float, index_timeout: float = 120.0,
                no_index: bool = False):
    sock_path = _socket_path(project_root)
    pid_path = _pid_path(project_root)

    if os.path.exists(sock_path):
        os.unlink(sock_path)

    session = ClangdSession(
        project_root=project_root,
        index_file=index_file,
        compile_commands_dir=compile_commands_dir,
        clangd_path=clangd_path,
        timeout=timeout,
        background_index=True,
        index_timeout=index_timeout,
        no_index=no_index,
    )

    sys.stderr.write(f"clangd args: {' '.join(session.clangd_args)}\n")
    sys.stderr.flush()

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(sock_path)
    server.listen(5)
    server.settimeout(1.0)

    with open(pid_path, "w") as f:
        f.write(str(os.getpid()))

    shutdown_flag = threading.Event()

    def handle_signal(signum, frame):
        shutdown_flag.set()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    sys.stderr.write(f"clangd-cli daemon started (pid={os.getpid()}, socket={sock_path})\n")
    sys.stderr.flush()

    while not shutdown_flag.is_set():
        try:
            conn, _ = server.accept()
        except socket.timeout:
            continue
        except OSError:
            break

        try:
            _handle_connection(conn, session, shutdown_flag)
        except Exception as e:
            sys.stderr.write(f"Connection error: {e}\n")
            sys.stderr.flush()
        finally:
            conn.close()

    session.shutdown()
    server.close()
    if os.path.exists(sock_path):
        os.unlink(sock_path)
    if os.path.exists(pid_path):
        os.unlink(pid_path)
    sys.stderr.write("clangd-cli daemon stopped\n")
    sys.stderr.flush()


def daemon_is_alive(project_root: str) -> bool:
    sock_path = _socket_path(project_root)
    if not os.path.exists(sock_path):
        return False
    try:
        resp = _send_to_socket(sock_path, {"command": "ping"})
        return resp.get("status") == "ok"
    except Exception:
        return False


def run_via_daemon(project_root: str, command: str, args) -> dict:
    sock_path = _socket_path(project_root)
    GLOBAL_KEYS = {"project_root", "index_file", "compile_commands_dir",
                   "clangd_path", "timeout", "index_timeout", "oneshot",
                   "no_index", "command"}
    cmd_args = {k: v for k, v in vars(args).items()
                if k not in GLOBAL_KEYS and v is not None}
    return _send_to_socket(sock_path, {"command": command, "args": cmd_args})


def _error_path(project_root: str) -> str:
    return _tmp_path(project_root, "err")


def daemon_start(project_root: str, args):
    if daemon_is_alive(project_root):
        return {"status": "already_running"}

    # Resolve config for response (mirrors session.py logic)
    config = _load_config(project_root)
    no_index = getattr(args, "no_index", False) or config.get("no_index", False)
    if no_index:
        resolved_index = None
    else:
        resolved_index = (args.index_file
                          or config.get("index_file") or None
                          or _find_index_file(project_root))
    resolved_ccd = (args.compile_commands_dir
                    or config.get("compile_commands_dir") or None
                    or _find_compile_commands(project_root))

    err_path = _error_path(project_root)
    if os.path.exists(err_path):
        os.unlink(err_path)

    pid = os.fork()
    if pid > 0:
        for _ in range(50):
            time.sleep(0.1)
            if daemon_is_alive(project_root):
                result = {"status": "started", "pid": pid}
                if resolved_index:
                    result["index_file"] = resolved_index
                else:
                    result["hint"] = (
                        "No index file (.idx) detected. If you have a pre-built index, "
                        "stop the daemon and restart with: "
                        "clangd-cli --project-root <dir> --index-file <path> start  "
                        "Or add it to .clangd-cli.json: {\"index_file\": \"<path>\"}"
                    )
                if resolved_ccd:
                    result["compile_commands_dir"] = resolved_ccd
                return result
        # Check if child wrote an error
        if os.path.exists(err_path):
            error_msg = Path(err_path).read_text().strip()
            os.unlink(err_path)
            return {"status": "error", "message": error_msg}
        return {"status": "start_timeout", "pid": pid}
    else:
        os.setsid()
        devnull = os.open(os.devnull, os.O_RDWR)
        os.dup2(devnull, 0)
        os.dup2(devnull, 1)
        try:
            daemon_main(
                project_root=project_root,
                index_file=args.index_file,
                compile_commands_dir=args.compile_commands_dir,
                clangd_path=args.clangd_path,
                timeout=args.timeout,
                index_timeout=getattr(args, "index_timeout", 120.0) or 120.0,
                no_index=no_index,
            )
        except Exception as e:
            Path(_error_path(project_root)).write_text(str(e))
        os._exit(0)


def daemon_stop(project_root: str):
    if not daemon_is_alive(project_root):
        return {"status": "not_running"}
    try:
        return _send_to_socket(_socket_path(project_root), {"command": "stop"})
    except Exception as e:
        return {"status": "error", "message": str(e)}


def daemon_wait_ready(project_root: str, index_timeout: float = 120.0):
    """Poll daemon until index_ready is True or timeout."""
    sock_path = _socket_path(project_root)
    deadline = time.monotonic() + index_timeout
    poll_interval = 2.0

    while time.monotonic() < deadline:
        try:
            resp = _send_to_socket(sock_path, {"command": "ping"})
            if resp.get("index_ready"):
                return resp
        except Exception:
            pass
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(poll_interval, remaining))

    # Final check
    try:
        return _send_to_socket(sock_path, {"command": "ping"})
    except Exception:
        return {"status": "error", "message": "Daemon not responding"}


def daemon_status(project_root: str):
    if daemon_is_alive(project_root):
        return _send_to_socket(_socket_path(project_root), {"command": "ping"})
    return {"status": "not_running"}
