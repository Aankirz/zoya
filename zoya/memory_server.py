"""Supermemory local (production P2, D105): Zoya starts and stops the self-hosted server.

It runs when a license key is set and SUPERMEMORY_API_KEY is not. Memory extraction goes through
the relay on ROUTER_MODEL with the user's license, so no provider key reaches the Mac and the
relay meters every call. Telemetry is always off: without SUPERMEMORY_DISABLE_TELEMETRY=1 the
0.0.8 binary opened connections to PostHog's ingest during an add (measured, prod-2 report).

Docs: https://supermemory.ai/docs/self-hosting/overview, /configuration, /embeddings.
"""

from __future__ import annotations

import atexit
import contextlib
import logging
import os
import re
import signal
import socket
import subprocess
import threading
import time
from pathlib import Path

from zoya.config import (
    MEMORY_EMBEDDING_DIMENSIONS,
    MEMORY_EMBEDDING_MODEL,
    MEMORY_SERVER_BIN,
    MEMORY_SERVER_DATA_DIR,
    MEMORY_SERVER_LOG,
    MEMORY_SERVER_PID_FILE,
    MEMORY_SERVER_PORT,
    MEMORY_SERVER_READY_POLL_S,
    MEMORY_SERVER_READY_WAIT_S,
    MEMORY_SERVER_STOP_TIMEOUT_S,
    license_key,
    relay_url,
)

log = logging.getLogger(__name__)

SECRET = re.compile(r"\b(?:sm|zoya)_[A-Za-z0-9_-]+")
PASSED_THROUGH = ("HOME", "PATH", "TMPDIR", "LANG")

_lock = threading.Lock()
_process: subprocess.Popen[bytes] | None = None
_ready = threading.Event()


def wanted() -> bool:
    """Local memory is for license users; a Supermemory key keeps the cloud path (D78)."""
    return bool(license_key() and relay_url() and not os.environ.get("SUPERMEMORY_API_KEY"))


def base_url(port: int = MEMORY_SERVER_PORT) -> str:
    return f"http://127.0.0.1:{port}"


def server_env(
    port: int = MEMORY_SERVER_PORT,
    data_dir: Path = MEMORY_SERVER_DATA_DIR,
    embedding: tuple[str, int] = (MEMORY_EMBEDDING_MODEL, MEMORY_EMBEDDING_DIMENSIONS),
) -> dict[str, str]:
    """Only what the server needs: bring-your-own provider keys in Zoya's env never reach it."""
    model, dimensions = embedding
    return {
        **{name: os.environ[name] for name in PASSED_THROUGH if name in os.environ},
        "OPENAI_BASE_URL": f"{relay_url()}/v1",
        "OPENAI_API_KEY": license_key(),
        "OPENAI_MODEL": os.environ.get("ROUTER_MODEL", ""),
        "SUPERMEMORY_DATA_DIR": str(data_dir),
        "PORT": str(port),
        "SUPERMEMORY_EMBEDDING_PROVIDER": "local",
        "SUPERMEMORY_EMBEDDING_MODEL": model,
        "SUPERMEMORY_EMBEDDING_DIMENSIONS": str(dimensions),
        "SUPERMEMORY_DISABLE_TELEMETRY": "1",
        "SUPERMEMORY_NO_UPDATE_CHECK": "1",
        "SUPERMEMORY_NO_OPEN": "1",
        "SUPERMEMORY_NO_STARTUP_ANIMATION": "1",
        "SUPERMEMORY_NO_COLOR": "1",
    }


def _copy_redacted(stream, path: Path) -> None:  # noqa: ANN001 — the child's stdout pipe
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as out:
        for raw in stream:
            out.write(SECRET.sub("<redacted>", raw.decode("utf-8", "replace")))
            out.flush()


def spawn(env: dict[str, str], log_path: Path = MEMORY_SERVER_LOG) -> subprocess.Popen[bytes]:
    """The server in its own process group, its output copied to `log_path` minus any key."""
    Path(env["SUPERMEMORY_DATA_DIR"]).mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(  # noqa: S603 — pinned binary, no shell
        [str(MEMORY_SERVER_BIN)],
        env=env,
        cwd=env["SUPERMEMORY_DATA_DIR"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    threading.Thread(
        target=_copy_redacted, args=(process.stdout, log_path), name="zoya-memory-log", daemon=True
    ).start()
    return process


def terminate(process: subprocess.Popen[bytes]) -> None:
    """SIGTERM the server's process group, SIGKILL it if it lingers. By PID, never by name."""
    if process.poll() is not None:
        return
    _signal_group(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=MEMORY_SERVER_STOP_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        _signal_group(process.pid, signal.SIGKILL)
        process.wait(timeout=MEMORY_SERVER_STOP_TIMEOUT_S)


def _signal_group(pid: int, sig: signal.Signals) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pid, sig)


def _is_our_server(pid: int) -> bool:
    try:
        result = subprocess.run(
            ["ps", "-o", "comm=", "-p", str(pid)], capture_output=True, text=True, timeout=2
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.stdout.strip() == str(MEMORY_SERVER_BIN)


def reap_stale() -> None:
    """A server left behind by a Zoya that was killed outright (SIGKILL, power loss)."""
    try:
        pid = int(MEMORY_SERVER_PID_FILE.read_text().strip())
    except (OSError, ValueError):
        return
    if _is_our_server(pid):
        log.warning("stopping a Supermemory server left by an earlier run (pid %d)", pid)
        _signal_group(pid, signal.SIGTERM)
        time.sleep(1)
    MEMORY_SERVER_PID_FILE.unlink(missing_ok=True)


def wait_ready(timeout_s: float = MEMORY_SERVER_READY_WAIT_S) -> bool:
    """A memory call in the first seconds after launch waits for the server's port, once."""
    if _ready.is_set():
        return True
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline and _process is not None and _process.poll() is None:
        try:
            socket.create_connection(("127.0.0.1", MEMORY_SERVER_PORT), timeout=1).close()
            _ready.set()
            return True
        except OSError:
            time.sleep(MEMORY_SERVER_READY_POLL_S)
    return False


def start() -> str:
    """Start the local server if this Mac should have one. Returns what happened, for the log."""
    global _process
    if not wanted():
        return "not needed"
    if not MEMORY_SERVER_BIN.exists():
        return "not installed — run: .venv/bin/python -m zoya.setup_models"
    with _lock:
        if _process is not None and _process.poll() is None:
            return f"running (pid {_process.pid})"
        reap_stale()
        _process = spawn(server_env())
        MEMORY_SERVER_PID_FILE.write_text(str(_process.pid))
        atexit.register(stop)
    return f"starting on {base_url()} (pid {_process.pid})"


def stop() -> None:
    global _process
    _ready.clear()
    with _lock:
        process, _process = _process, None
    if process is None:
        return
    terminate(process)
    MEMORY_SERVER_PID_FILE.unlink(missing_ok=True)
    log.info("Supermemory server stopped (pid %d)", process.pid)
