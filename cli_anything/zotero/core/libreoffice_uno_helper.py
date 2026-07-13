from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Control one LibreOffice document through UNO.")
    parser.add_argument("operation", choices=("wait", "refresh", "store", "close"))
    parser.add_argument("--path", required=True, type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=2002, type=int)
    parser.add_argument("--timeout", default=20.0, type=float)
    return parser.parse_args()


def _connect(host: str, port: int) -> tuple[Any, Any]:
    import uno

    local_context = uno.getComponentContext()
    resolver = local_context.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver",
        local_context,
    )
    context = resolver.resolve(
        f"uno:socket,host={host},port={port};urp;StarOffice.ComponentContext"
    )
    desktop = context.ServiceManager.createInstanceWithContext(
        "com.sun.star.frame.Desktop",
        context,
    )
    return context, desktop


def _find_document(desktop: Any, target_url: str) -> Any | None:
    enumeration = desktop.getComponents().createEnumeration()
    while enumeration.hasMoreElements():
        component = enumeration.nextElement()
        try:
            component_url = component.getURL()
        except Exception:
            continue
        if component_url == target_url:
            return component
    return None


def _wait_for_document(host: str, port: int, path: Path, timeout: float) -> tuple[Any, Any, Any]:
    target_url = path.expanduser().resolve().as_uri()
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            context, desktop = _connect(host, port)
            document = _find_document(desktop, target_url)
            if document is not None:
                return context, desktop, document
        except Exception as exc:
            last_error = exc
        time.sleep(0.25)
    detail = f": {last_error}" if last_error else ""
    raise TimeoutError(f"LibreOffice did not expose the target document before timeout{detail}")


def run(operation: str, host: str, port: int, path: Path, timeout: float) -> dict[str, Any]:
    context, desktop, document = _wait_for_document(host, port, path, timeout)
    desktop_terminated = None
    if operation == "refresh":
        import uno

        transformer = context.ServiceManager.createInstanceWithContext(
            "com.sun.star.util.URLTransformer",
            context,
        )
        command_url = uno.createUnoStruct("com.sun.star.util.URL")
        command_url.Complete = "service:org.zotero.integration.ooo.ZoteroOpenOfficeIntegration?refresh"
        transformer.parseStrict(command_url)
        frame = document.getCurrentController().getFrame()
        dispatch = frame.queryDispatch(command_url, "_self", 0)
        if dispatch is None:
            raise RuntimeError("LibreOffice did not expose the Zotero Refresh dispatch command")
        dispatch.dispatch(command_url, ())
        time.sleep(1.0)
    elif operation == "store":
        document.store()
    elif operation == "close":
        try:
            document.close(True)
        except Exception:
            document.dispose()
        desktop_terminated = bool(desktop.terminate())
    return {
        "ok": desktop_terminated is not False,
        "operation": operation,
        "path": str(path.expanduser().resolve()),
        "url": path.expanduser().resolve().as_uri(),
        "port": port,
        "desktop_terminated": desktop_terminated,
    }


def main() -> None:
    args = parse_args()
    try:
        payload = run(args.operation, args.host, args.port, args.path, args.timeout)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1) from exc
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
