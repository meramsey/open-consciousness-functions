"""Health-observed portal worker for the canonical OCF production supervisor."""

from __future__ import annotations

import argparse
import base64
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from .production_supervisor import process_identity, read_json, write_json


def reconcile(status):
    previous = read_json(status) if status.exists() else {}
    for key in ("owner_identity", "server_identity"):
        identity = previous.get(key)
        if identity and process_identity(identity["pid"]) == identity:
            return {"terminal": False, "safe_to_run": False, "reason": "live portal ownership"}
    return {"terminal": False, "safe_to_run": True}


def check_health(config):
    host = config.get("host", "127.0.0.1")
    scheme = "https" if config.get("certificate") else "http"
    context = (
        ssl.create_default_context(cafile=config["certificate"]) if scheme == "https" else None
    )
    request = urllib.request.Request(f"{scheme}://{host}:{config.get('port', 8766)}/health")
    if config.get("credentials_file"):
        credentials = Path(config["credentials_file"]).read_text().strip()
        request.add_header(
            "Authorization", "Basic " + base64.b64encode(credentials.encode()).decode()
        )
    # Local readiness must never be redirected through an HTTP proxy.
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context)
    )
    with opener.open(request, timeout=10) as response:
        return response.status == 200 and json.loads(response.read(1024)).get("status") == "ready"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["run", "reconcile"])
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--status", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "reconcile":
        print(json.dumps(reconcile(args.status)))
        return 0
    config = read_json(args.config)
    child = subprocess.Popen(
        [sys.executable, "-m", "ocf_tools.listening_portal", "--config", str(args.config)]
    )
    failures, checks = 0, 0
    try:
        while child.poll() is None:
            try:
                healthy = check_health(config)
            except (OSError, ValueError, urllib.error.URLError):
                healthy = False
            failures = 0 if healthy else failures + 1
            checks += 1
            write_json(
                args.status,
                {
                    "owner_pid": os.getpid(),
                    "owner_identity": process_identity(os.getpid()),
                    "server_identity": process_identity(child.pid),
                    "sessions": {
                        "portal": {
                            "state": "running",
                            "health": "ready" if healthy else "unavailable",
                            "checks": checks,
                        }
                    },
                },
            )
            if failures >= 3:
                return 1
            time.sleep(10)
        return child.returncode or 1
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=20)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
