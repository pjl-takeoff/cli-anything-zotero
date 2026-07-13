from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_UNO_HOST = "127.0.0.1"
DEFAULT_UNO_PORT = 2002
DEFAULT_UNO_TIMEOUT = 20.0


@dataclass
class LibreOfficeSession:
    path: Path
    port: int
    profile_dir: Path
    process: subprocess.Popen[Any]


_SESSIONS: dict[Path, LibreOfficeSession] = {}
_SESSIONS_LOCK = threading.Lock()


def _session_key(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _allocate_uno_port(host: str = DEFAULT_UNO_HOST) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((host, 0))
        return int(listener.getsockname()[1])


def _seed_user_installation(profile_dir: Path) -> None:
    source = Path(
        os.environ.get(
            "ZOTERO_CLI_LIBREOFFICE_PROFILE",
            str(Path.home() / ".config" / "libreoffice" / "4"),
        )
    ).expanduser()
    if not source.exists():
        raise RuntimeError(
            "LibreOffice user profile was not found. Install the Zotero LibreOffice integration before conversion."
        )
    shutil.copytree(source, profile_dir, dirs_exist_ok=True)
    for lock_file in profile_dir.glob(".*lock*"):
        lock_file.unlink(missing_ok=True)


def _dismiss_zotero_integration_dialog(timeout: float = 3.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            search = subprocess.run(
                ["xdotool", "search", "--name", "Zotero Integration"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"attempted": True, "ok": False, "error": str(exc)}
        window_ids = [line.strip() for line in search.stdout.splitlines() if line.strip()]
        if window_ids:
            window_id = window_ids[-1]
            dismiss = subprocess.run(
                ["xdotool", "windowfocus", window_id, "key", "Return"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            return {
                "attempted": True,
                "ok": dismiss.returncode == 0,
                "window_id": window_id,
                "stderr": dismiss.stderr.strip() or None,
            }
        time.sleep(0.1)
    return {"attempted": True, "ok": None, "reason": "No Zotero Integration dialog appeared."}


def build_libreoffice_command(
    soffice: str | Path,
    path: str | Path,
    *,
    host: str = DEFAULT_UNO_HOST,
    port: int = DEFAULT_UNO_PORT,
    user_installation: str | Path | None = None,
) -> list[str]:
    command = [
        str(soffice),
        "--nologo",
        "--nodefault",
        "--norestore",
        "--nolockcheck",
    ]
    if user_installation is not None:
        profile_uri = Path(user_installation).expanduser().resolve().as_uri()
        command.append(f"-env:UserInstallation={profile_uri}")
    command.extend(
        [
            f"--accept=socket,host={host},port={port};urp;StarOffice.ComponentContext",
            str(Path(path).expanduser()),
        ]
    )
    return command


def start_libreoffice_session(soffice: str | Path, path: str | Path) -> LibreOfficeSession:
    key = _session_key(path)
    with _SESSIONS_LOCK:
        if key in _SESSIONS:
            raise RuntimeError(f"LibreOffice session already exists for {key}")

    profile_dir = Path(tempfile.mkdtemp(prefix="zotero-cli-libreoffice-"))
    try:
        _seed_user_installation(profile_dir)
        port = _allocate_uno_port()
        command = build_libreoffice_command(
            soffice,
            path,
            port=port,
            user_installation=profile_dir,
        )
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        shutil.rmtree(profile_dir, ignore_errors=True)
        raise

    session = LibreOfficeSession(path=key, port=port, profile_dir=profile_dir, process=process)
    with _SESSIONS_LOCK:
        _SESSIONS[key] = session
    return session


def get_libreoffice_session(path: str | Path) -> LibreOfficeSession | None:
    with _SESSIONS_LOCK:
        return _SESSIONS.get(_session_key(path))


def _process_group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_for_process_group_exit(pgid: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _process_group_exists(pgid):
            return True
        time.sleep(0.05)
    return not _process_group_exists(pgid)


def finish_libreoffice_session(path: str | Path, *, timeout: float = 5.0) -> dict[str, Any]:
    with _SESSIONS_LOCK:
        session = _SESSIONS.pop(_session_key(path), None)
    if session is None:
        return {"attempted": False, "ok": None, "reason": "No isolated LibreOffice session was registered."}

    forced = False
    try:
        session.process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        pass

    process_group_exited = not _process_group_exists(session.process.pid)
    if not process_group_exited:
        forced = True
        try:
            os.killpg(session.process.pid, signal.SIGTERM)
        except ProcessLookupError:
            process_group_exited = True
        else:
            process_group_exited = _wait_for_process_group_exit(session.process.pid, 2.0)
        if not process_group_exited:
            try:
                os.killpg(session.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                process_group_exited = True
            else:
                process_group_exited = _wait_for_process_group_exit(session.process.pid, 2.0)

    if process_group_exited and session.process.poll() is None:
        try:
            session.process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            pass

    if process_group_exited:
        shutil.rmtree(session.profile_dir, ignore_errors=True)
    profile_removed = not session.profile_dir.exists()
    return {
        "attempted": True,
        "ok": session.process.poll() is not None and process_group_exited and profile_removed,
        "process_exited": session.process.poll() is not None,
        "process_group_exited": process_group_exited,
        "profile_removed": profile_removed,
        "forced": forced,
        "pid": session.process.pid,
        "uno_port": session.port,
    }


def run_uno_operation(
    operation: str,
    path: str | Path,
    *,
    host: str = DEFAULT_UNO_HOST,
    port: int | None = None,
    timeout: float = DEFAULT_UNO_TIMEOUT,
    python: str | Path | None = None,
) -> dict[str, Any]:
    session = get_libreoffice_session(path)
    effective_port = port if port is not None else (session.port if session is not None else DEFAULT_UNO_PORT)
    helper = Path(__file__).with_name("libreoffice_uno_helper.py")
    python_executable = str(python or os.environ.get("ZOTERO_CLI_UNO_PYTHON", "/usr/bin/python3"))
    command = [
        python_executable,
        str(helper),
        operation,
        "--path",
        str(Path(path).expanduser()),
        "--host",
        host,
        "--port",
        str(effective_port),
        "--timeout",
        str(timeout),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout + 5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "attempted": True,
            "ok": False,
            "method": f"uno {operation}",
            "command": command,
            "error": str(exc),
        }

    invalid_json = False
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {}
        invalid_json = True
    error = payload.get("error") or (completed.stderr.strip() or None)
    if invalid_json and error is None:
        error = "UNO helper returned invalid JSON"
    dialog = (
        _dismiss_zotero_integration_dialog()
        if operation == "refresh" and completed.returncode == 0 and payload.get("ok") is True
        else {"attempted": False, "ok": None}
    )
    helper_ok = completed.returncode == 0 and payload.get("ok") is True
    if dialog.get("ok") is False and error is None:
        error = dialog.get("error") or dialog.get("stderr") or "Zotero Integration dialog could not be dismissed."
    return {
        "attempted": True,
        "ok": helper_ok and dialog.get("ok") is not False,
        "method": f"uno {operation}",
        "command": command,
        "uno_port": effective_port,
        "operation": operation,
        "payload": payload,
        "dialog": dialog,
        "stderr": completed.stderr.strip() or None,
        "error": error,
    }
