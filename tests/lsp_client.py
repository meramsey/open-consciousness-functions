"""Bounded cross-platform stdio JSON-RPC client used only by protocol tests."""

import json
import queue
import subprocess
import sys
import threading
import time

from ocf_tools.paths import REPO_ROOT, workspace_environment


class Client:
    def __init__(self, root, stderr):
        self.log = stderr.open("wb")
        env = workspace_environment()
        env["PYTHONPATH"] = str(REPO_ROOT / "scripts")
        self.process = subprocess.Popen(
            [sys.executable, str(REPO_ROOT / "scripts/ocf.py"), "lsp", "--stdio"],
            cwd=REPO_ROOT,
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
                self.messages.put(json.loads(data))
        except BaseException as exc:
            self.messages.put(exc)

    def send(self, method, params=None, identifier=None):
        message = {"jsonrpc": "2.0", "method": method, "params": params}
        if identifier is not None:
            message["id"] = identifier
        data = json.dumps(message, ensure_ascii=False).encode("utf-8")
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
