"""Private manifest-only listening server. No directory browsing or arbitrary reads."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import mimetypes
import os
import re
import signal
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

ROLES = {"audio", "master", "transcript", "subtitles"}
EXTENSIONS = {
    "audio": {".mp3", ".m4a"},
    "master": {".wav", ".flac"},
    "transcript": {".txt"},
    "subtitles": {".vtt", ".srt"},
}
PAGE = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Private listening</title>
<style>body{color:#e8eaf2;background:#10131c;font:17px system-ui;max-width:840px;margin:auto;padding:24px}article{background:#1c2231;padding:20px;border-radius:16px;margin:20px 0}audio,textarea{width:100%;margin:12px 0}textarea{box-sizing:border-box;background:#10131c;color:inherit;border:1px solid #56617b;padding:10px}a{color:#aecaff}button{background:#aac4ff;border:0;border-radius:8px;padding:12px}small{color:#bbc3d7}h1{font-size:30px}</style>
<h1>Private listening</h1><p>Verified completed editions. Technical verification and your listening approval are separate.</p><main id="library">Loading…</main>
<script>
const el=(tag,text)=>{let x=document.createElement(tag);if(text!==undefined)x.textContent=text;return x};
async function load(){let r=await fetch('/catalog');if(!r.ok)throw Error('Library unavailable');let rows=await r.json();let main=document.querySelector('main');main.replaceChildren();for(let t of rows){let a=el('article');a.append(el('h2',t.title),el('small',`${t.edition} · ${t.profile} · ${(t.duration_seconds/60).toFixed(1)} min`));let media=t.media.find(x=>x.role==='audio');if(media){let p=el('audio');p.controls=true;p.preload='metadata';p.src=media.url;a.append(p)}for(let m of t.media.filter(x=>x.role!=='audio')){let link=el('a',m.role+' ');link.href=m.url;a.append(link,el('br'))}let notes=el('textarea');notes.placeholder='Listening notes and edition comparisons';notes.value=t.notes||'';notes.maxLength=16000;let save=el('button','Save notes');save.onclick=async()=>{let res=await fetch('/notes/'+t.id,{method:'POST',headers:{'Content-Type':'application/json','X-OCF-Request':'notes'},body:JSON.stringify({notes:notes.value})});save.textContent=res.ok?'Saved':'Save failed'};a.append(notes,save);main.append(a)}if(!rows.length)main.textContent='No verified completed editions yet.'}
load().catch(()=>document.querySelector('main').textContent='Library unavailable.');
</script></html>"""


def regular_file(directory: Path, name: str):
    """Only plain direct children; callers never pass URL paths here."""
    if not isinstance(name, str) or not name or name in {".", ".."}:
        raise ValueError("invalid artifact name")
    if "/" in name or "\\" in name or "\x00" in name:
        raise ValueError("nested artifact path forbidden")
    if any(parent.is_symlink() for parent in (directory, *directory.parents)):
        raise ValueError("symlink directory forbidden")
    path = directory / name
    if path.is_symlink() or not path.is_file():
        raise ValueError("regular artifact required")
    return path


def open_regular(path):
    """Open each POSIX path component without following links."""
    path = Path(path).absolute()
    if os.open not in os.supports_dir_fd:
        regular_file(path.parent, path.name)
        return os.open(path, os.O_RDONLY)
    directory = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in path.parts[1:-1]:
            following = os.open(
                component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
            )
            os.close(directory)
            directory = following
        return os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    finally:
        os.close(directory)


def read_object(path, limit):
    with os.fdopen(open_regular(path), "rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("oversized metadata")
    return json.loads(data)


def file_hash(path):
    result = hashlib.sha256()
    with os.fdopen(open_regular(path), "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def byte_range(value, size):
    if value is None:
        return 0, size - 1, 200
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", value)
    if not match or not any(match.groups()):
        raise ValueError("invalid range")
    first, last = match.groups()
    if not first:
        if int(last) <= 0:
            raise ValueError("invalid suffix range")
        start, end = max(0, size - int(last)), size - 1
    else:
        start, end = int(first), min(int(last), size - 1) if last else size - 1
    if start >= size or start > end:
        raise ValueError("unsatisfiable range")
    return start, end, 206


class PrivateServer(ThreadingHTTPServer):
    """Bound request reads; TLS handshakes run outside the accept loop."""

    tls_context = None
    daemon_threads = True
    block_on_close = False

    def get_request(self):
        request, address = super().get_request()
        request.settimeout(10)
        return request, address

    def finish_request(self, request, client_address):
        if self.tls_context is not None:
            with self.tls_context.wrap_socket(request, server_side=True) as secure:
                super().finish_request(secure, client_address)
        else:
            super().finish_request(request, client_address)

    def handle_error(self, request, client_address):
        pass  # Network errors must not reveal request or client details.


class Library:
    def __init__(self, root):
        self.root = Path(root).absolute()
        if any(parent.is_symlink() for parent in (self.root, *self.root.parents)):
            raise ValueError("symlink library forbidden")
        self.cache = {}
        self.guard = threading.RLock()

    def discover(self):
        """Recheck completed manifests; never promote partial or corrupt artifacts."""
        catalog, files = [], {}
        with self.guard:
            for folder in sorted(self.root.iterdir()):
                if folder.is_symlink() or not folder.is_dir():
                    continue
                try:
                    manifest = regular_file(folder, "listening.json")
                    if manifest.stat().st_size > 65536:
                        continue
                    data = read_object(manifest, 65536)
                    if not isinstance(data, dict):
                        continue
                    if (
                        data.get("status") != "completed"
                        or data.get("technical_verified") is not True
                    ):
                        continue
                    if (
                        not isinstance(data["duration_seconds"], (int, float))
                        or not 0 < data["duration_seconds"] < 86400
                    ):
                        continue
                    identity = hashlib.sha256(folder.name.encode()).hexdigest()
                    media, pending = [], {}
                    roles = set()
                    for number, item in enumerate(data["media"]):
                        role = item["role"]
                        if role not in ROLES:
                            raise ValueError("unsupported role")
                        path = regular_file(folder, item["file"])
                        if path.suffix.lower() not in EXTENSIONS[role]:
                            raise ValueError("unsupported media")
                        info = path.stat()
                        signature = (
                            info.st_dev,
                            info.st_ino,
                            info.st_size,
                            info.st_mtime_ns,
                            info.st_ctime_ns,
                        )
                        key = (path, signature, item["sha256"])
                        if info.st_size != item["size_bytes"]:
                            raise ValueError("size mismatch")
                        if key not in self.cache:
                            if file_hash(path) != item["sha256"]:
                                raise ValueError("hash mismatch")
                            self.cache[key] = True
                        url = "/media/" + identity + "/" + str(number)
                        pending[url] = (path, signature)
                        media.append({"role": role, "url": url})
                        roles.add(role)
                    if not {"audio", "master", "transcript"} <= roles:
                        continue
                    notes = ""
                    note_path = self.root / ("notes-" + identity + ".json")
                    if note_path.exists():
                        note_path = regular_file(self.root, note_path.name)
                        if note_path.stat().st_size <= 100000:
                            note_data = read_object(note_path, 100000)
                            notes = (
                                note_data.get("notes", "") if isinstance(note_data, dict) else ""
                            )
                    catalog.append(
                        {
                            "id": identity,
                            "title": str(data["title"]),
                            "edition": str(data["edition"]),
                            "profile": str(data["profile"]),
                            "duration_seconds": data["duration_seconds"],
                            "media": media,
                            "notes": notes,
                        }
                    )
                    files.update(pending)
                except (OSError, ValueError, KeyError, TypeError):
                    continue
        return catalog, files

    def save_notes(self, identity, notes):
        if not isinstance(notes, str) or len(notes) > 16000:
            raise ValueError("invalid notes")
        with self.guard:
            catalog, _ = self.discover()
            if identity not in {row["id"] for row in catalog}:
                raise ValueError("unknown edition")
            path = self.root / ("notes-" + identity + ".json")
            temporary = self.root / ("notes-" + identity + "-" + uuid4().hex + ".tmp")
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            fd = os.open(temporary, flags, 0o600)
            with os.fdopen(fd, "w") as stream:
                json.dump({"notes": notes}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)


def handler(library, authorization):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # Request paths and credentials do not belong in service logs.

        def authorized(self):
            if authorization and not hmac.compare_digest(
                self.headers.get("Authorization", ""), authorization
            ):
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="Private listening"')
                self.send_header("Content-Length", "0")
                self.end_headers()
                return False
            return True

        def reply(self, payload, mime="application/json", status=200):
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; frame-ancestors 'none'",
            )
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            if not self.authorized():
                return
            path = urlsplit(self.path).path
            if path == "/":
                return self.reply(PAGE.encode(), "text/html; charset=utf-8")
            catalog, files = library.discover()
            if path == "/health":
                return self.reply(b'{"status":"ready"}')
            if path == "/catalog":
                return self.reply(json.dumps(catalog).encode())
            if path not in files:
                return self.reply(b"Not found", "text/plain", 404)
            file, signature = files[path]
            try:
                regular_file(file.parent, file.name)
                fd = open_regular(file)
                with os.fdopen(fd, "rb") as stream:
                    info = os.fstat(stream.fileno())
                    if signature != (
                        info.st_dev,
                        info.st_ino,
                        info.st_size,
                        info.st_mtime_ns,
                        info.st_ctime_ns,
                    ):
                        raise ValueError("artifact changed")
                    start, end, status = byte_range(self.headers.get("Range"), info.st_size)
                    self.send_response(status)
                    self.send_header(
                        "Content-Type",
                        mimetypes.guess_type(file.name)[0] or "application/octet-stream",
                    )
                    self.send_header("Content-Length", str(end - start + 1))
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Cache-Control", "private, no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    if status == 206:
                        self.send_header("Content-Range", f"bytes {start}-{end}/{info.st_size}")
                    self.end_headers()
                    if self.command == "HEAD":
                        return
                    stream.seek(start)
                    remaining = end - start + 1
                    while remaining:
                        block = stream.read(min(remaining, 65536))
                        if not block:
                            break
                        self.wfile.write(block)
                        remaining -= len(block)
            except (OSError, ValueError):
                self.reply(b"Unavailable range or artifact", "text/plain", 416)

        def do_POST(self):
            if not self.authorized():
                return
            try:
                path = urlsplit(self.path).path
                if not re.fullmatch(r"/notes/[0-9a-f]{64}", path):
                    raise ValueError("unknown endpoint")
                if self.headers.get("X-OCF-Request") != "notes":
                    raise ValueError("missing request intent")
                size = int(self.headers.get("Content-Length", "-1"))
                if not 0 <= size <= 100000:
                    raise ValueError("invalid body size")
                data = json.loads(self.rfile.read(size))
                library.save_notes(path.split("/")[-1], data["notes"])
                self.reply(b'{"saved":true}')
            except (OSError, ValueError, KeyError, TypeError):
                self.reply(b"Invalid notes", "text/plain", 400)

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    config = json.loads(parser.parse_args().config.read_text())
    host = config.get("host", "127.0.0.1")
    credentials = config.get("credentials_file")
    authorization = None
    if credentials:
        raw = Path(credentials).read_text().strip()
        if ":" not in raw or len(raw.split(":", 1)[1]) < 24:
            raise ValueError("a strong pre-provisioned credential is required")
        authorization = "Basic " + base64.b64encode(raw.encode()).decode()
    if host not in ("127.0.0.1", "::1") and not (
        authorization and config.get("certificate") and config.get("private_key")
    ):
        raise ValueError("LAN listening requires explicit credentials and TLS")
    server = PrivateServer(
        (host, config.get("port", 8766)), handler(Library(config["library"]), authorization)
    )
    if config.get("certificate"):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(config["certificate"], config["private_key"])
        server.tls_context = context
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: threading.Thread(target=server.shutdown, daemon=True).start())
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
