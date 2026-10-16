"""Bounded cross-platform stdio JSON-RPC client used only by protocol tests."""

import json
import queue
import subprocess
import sys
import threading
import time

from ocf_tools.paths import REPO_ROOT, workspace_environment


class Client:
    def __init__(self, root, stderr, *, command=None, settings=None, cwd=None):
        self.log = stderr.open("wb")
        self.root = root
        self.settings = settings
        self.server_requests = []
        self.writer_lock = threading.Lock()
        env = workspace_environment()
        env["PYTHONPATH"] = str(REPO_ROOT / "scripts")
        self.process = subprocess.Popen(
            command or [sys.executable, str(REPO_ROOT / "scripts/ocf.py"), "lsp", "--stdio"],
            cwd=cwd or REPO_ROOT,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.log,
        )
        self.messages = queue.Queue()
        self.notifications = []
        self.identifier = 0
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self):
        try:
            while self.process.stdout:
                headers = {}
                while line := self.process.stdout.readline():
                    if line in (b"\r\n", b"\n"):
                        break
                    key, value = line.decode("ascii").split(":", 1)
                    headers[key.lower()] = value.strip()
                if not headers:
                    return
                data = self.process.stdout.read(int(headers["content-length"]))
                message = json.loads(data)
                if self.settings is not None and "method" in message and "id" in message:
                    self.server_requests.append(message)
                    result = None
                    if message["method"] == "workspace/configuration":
                        result = []
                        for item in message["params"]["items"]:
                            value = self.settings
                            for part in item.get("section", "").split("."):
                                value = value.get(part) if isinstance(value, dict) else None
                            result.append(value)
                    elif message["method"] == "workspace/workspaceFolders":
                        result = [{"uri": self.root.as_uri(), "name": "test"}]
                    self._write({"jsonrpc": "2.0", "id": message["id"], "result": result})
                else:
                    self.messages.put(message)
        except BaseException as exc:
            self.messages.put(exc)

    def send(self, method, params=None, identifier=None):
        message = {"jsonrpc": "2.0", "method": method, "params": params}
        if identifier is not None:
            message["id"] = identifier
        self._write(message)

    def _write(self, message):
        data = json.dumps(message, ensure_ascii=False).encode("utf-8")
        with self.writer_lock:
            self.process.stdin.write(f"Content-Length: {len(data)}\r\n\r\n".encode("ascii") + data)
            self.process.stdin.flush()

    def receive(self, predicate, timeout=15):
        deadline = time.monotonic() + timeout
        for index, message in enumerate(self.notifications):
            if predicate(message):
                return self.notifications.pop(index)
        while time.monotonic() < deadline:
            try:
                message = self.messages.get(timeout=min(1, max(0.01, deadline - time.monotonic())))
            except queue.Empty:
                continue
            if isinstance(message, BaseException):
                raise message
            if predicate(message):
                return message
            self.notifications.append(message)
        raise AssertionError(
            f"LSP response timed out; process={self.process.poll()}, pending={self.notifications}"
        )

    def request(self, method, params=None):
        self.identifier += 1
        self.send(method, params, self.identifier)
        return self.receive(lambda message: message.get("id") == self.identifier)

    def close(self):
        try:
            if self.process.poll() is None:
                self.request("shutdown")
                self.send("exit")
                self.process.wait(timeout=10)
        finally:
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait(timeout=10)
            self.reader.join(timeout=2)
            self.log.close()
