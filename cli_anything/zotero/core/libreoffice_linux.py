from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_UNO_HOST = "127.0.0.1"
DEFAULT_UNO_PORT = 2002
DEFAULT_UNO_TIMEOUT = 20.0


def build_libreoffice_command(
    soffice: str | Path,
    path: str | Path,
    *,
    host: str = DEFAULT_UNO_HOST,
    port: int = DEFAULT_UNO_PORT,
) -> list[str]:
    return [
        str(soffice),
        "--nologo",
        "--nodefault",
        "--norestore",
        "--nolockcheck",
        f"--accept=socket,host={host},port={port};urp;StarOffice.ComponentContext",
        str(Path(path).expanduser()),
    ]


def run_uno_operation(
    operation: str,
    path: str | Path,
    *,
    host: str = DEFAULT_UNO_HOST,
    port: int = DEFAULT_UNO_PORT,
    timeout: float = DEFAULT_UNO_TIMEOUT,
    python: str | Path | None = None,
) -> dict[str, Any]:
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
        str(port),
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
    return {
        "attempted": True,
        "ok": completed.returncode == 0 and payload.get("ok") is True,
        "method": f"uno {operation}",
        "command": command,
        "uno_port": port,
        "operation": operation,
        "payload": payload,
        "stderr": completed.stderr.strip() or None,
        "error": error,
    }
